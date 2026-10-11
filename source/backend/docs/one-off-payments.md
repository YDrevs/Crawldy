# One-off payments: the provider-neutral lifecycle and the Paddle adapter

Companion to `payment-provider-readiness.md`, which stays as it is. That
document was a read-only gap analysis written before any adapter existed;
its findings were correct and this one records what was built in answer to
them. Where it says "absent" or "must decide", the decision is here.

## The one sentence everything else follows from

**Entitlement comes from a verified provider event reconciled against a
purchase we created ourselves, and from nothing else.** Not from a browser
returning from checkout, not from a transaction id the browser reports, not
from an email, not from a session cookie, and not from custom data the
provider hands back.

## Lifecycle

```
guest audits a URL      →  free short result
click "Get the full audit"
  POST /v1/public/audits/{id}/checkout
    ├─ OneOffPurchase created  status=PENDING  external_id = its own uuid
    └─ provider.create_checkout(CheckoutRequest)   ← the only network call
         └─ provider_ref = provider's transaction id, stored beside it
browser opens the provider checkout (overlay or hosted URL)
  ⋯ nothing about entitlement happens here ⋯
provider POSTs to /v1/webhooks/paddle
    ├─ signature verified inside the adapter, over the raw body
    ├─ translated into a VerifiedBillingEvent (domain vocabulary only)
    ├─ journalled in billing_events, unique on (provider, event id)
    ├─ correlated: payload["purchase_ref"] → our PENDING row
    ├─ PENDING → PAID, credits issued once
    └─ AuditUnlock created for purchase.audit_id  ← from OUR row
GET /v1/public/audits/{id}/full  now returns the full report
```

The order matters and is not an implementation detail. The purchase exists
**before** the checkout because it is the correlation authority: the
identifier we hand the provider must already name a row of ours, or the
event would be free to name anything.

### Where each fact lives

| Fact | Source of truth | Never |
|---|---|---|
| Which audit was bought | `OneOffPurchase.audit_id` | the event payload |
| Which organization | `OneOffPurchase.organization_id` | the customer email |
| Whether it was paid | `OneOffPurchase.status` + a verified event | the return URL |
| Whether access is live | `guest.is_unlocked` (unlock history AND a PAID purchase) | the unlock row alone |
| The price | the provider's price catalogue | our code |
| Event ordering | `occurred_at`, the provider's clock | arrival order |

## Purchase kind → provider price

The domain knows one purchase kind, `PurchaseKind.ONE_OFF_FULL_AUDIT`. It
never sees a `pri_…`. `catalog.price_ref_for()` resolves the kind against
configuration for the active provider, and an unconfigured price raises
rather than defaulting — an empty configuration is a misconfiguration, not
a free sale. A test walks `app/` and fails on any hardcoded `pri_…`.

Pricing itself is a product decision recorded nowhere in this repository.
The sandbox price is test configuration.

## Provider selection

`BILLING_PROVIDER` names the adapter that opens the till (`fake` by
default, so a developer without Paddle keys sees a working funnel). The
webhook route accepts any *registered* provider, not just the active one —
otherwise switching providers would drop events already in flight.

The fake provider accepts any request carrying `x-fake-signature: valid`.
In production that is not a test tool but a way to obtain a paid report
with one `curl`, so at `APP_ENV=prod` it is not registered at all:
`provider_for("fake")` returns `None` and the webhook answers exactly as it
does for an unknown provider. The gate is in the registry rather than the
route, because the registry is what every path goes through.

## Paddle adapter

`app/billing/providers/paddle.py`. Everything Paddle-specific is inside it
and nothing crosses out: API hosts, event names, signature format,
transaction and price identifiers, statuses.

**Verified against the sandbox on 2026-08-25** (read-only `GET`s, no state
created):

- authentication `Authorization: Bearer <key>`;
- `https://sandbox-api.paddle.com` answers with the configured key;
- all four mapped event types exist in the current event model.

| Paddle event | Domain meaning |
|---|---|
| `transaction.completed` | `ONE_OFF_PURCHASED` |
| `transaction.payment_failed` | `PAYMENT_FAILED` |
| `adjustment.created` with `action == "refund"` | `ONE_OFF_REFUNDED` |
| `transaction.canceled` | *deliberately unmapped* |
| `subscription.*` | *deliberately unmapped* |

A deliberately unmapped event raises `UnhandledEvent`, which is **not** an
`InvalidWebhook`. The two require opposite answers: a rejected signature
must fail the request, while an event we simply do not listen to must be
acknowledged, or the provider retries it forever. The route answers 200
with `{"outcome": "ignored"}`.

### Checkout

`POST /transactions` with `items: [{price_id, quantity: 1}]`,
`collection_mode: "automatic"`, and exactly one piece of custom data:

```json
{"crawldy_purchase_id": "<our own uuid>"}
```

Nothing else. Whatever we send there comes back from the other side, so the
volume we send is the volume that can be forged. The audit, organization
and findings already live in the purchase.

**`checkout.url` is deliberately not sent.** In Paddle that field is the
address of the payment page itself, not a post-payment return
destination. While we put our "return URL" there, every transaction
silently overrode the account default payment link with a page that does
not exist — no error, just a link leading nowhere. Omitting it lets
Paddle use the configured default payment link. Where to send the buyer
*after* payment is `successUrl` in Paddle.js settings, i.e. the browser;
Paddle has no server-side field for it, which is why `CheckoutRequest`
has no `return_url` to misplace.

### The default payment link page

`/checkout` is the page registered in Paddle as the default payment
link. Paddle builds `<default payment link>?_ptxn=<transaction id>` and
sends the buyer there — possibly from an email, another browser, or a
day later, so the page assumes no guest capability and no audit id.

It loads Paddle.js **on page load**, calls `Environment.set` then
`Initialize`, and stops. Paddle.js opens the checkout itself once it
sees `_ptxn`; calling `Checkout.open` as well would open it twice. A
page that initializes the provider inside a click handler looks correct
and does nothing for this path.

Its two public inputs come from `GET /v1/public/checkout-config`
(`environment`, `client_token`) rather than `NEXT_PUBLIC_*`, so provider
configuration stays in one place. That endpoint needs no capability:
the buyer arriving on `?_ptxn=` has none, and both values are public.

`create_customer` is implemented and deliberately never called for guest
one-off checkout: an anonymous funnel has no account and no email, and a
synthetic address would be a fabricated person created to satisfy a
function signature. Paddle collects the buyer on its own page.

### Webhook signature

Header `Paddle-Signature: ts=<unix>;h1=<hex>`; HMAC-SHA256 over
`ts + ":" + raw body` keyed with the destination secret; compared with
`hmac.compare_digest`. The body is taken as raw bytes — parsing and
re-serialising breaks the signature — and the signature is verified
**before** the body is parsed at all.

Replay window is `PADDLE_SIGNATURE_TOLERANCE_S`, default 300 s. Wider than
the 5 s Paddle SDKs default to, on purpose: server clock drift is a real
failure mode and it presents as "signature mismatch", i.e. as an attack. A
wider window separates the two while remaining replay protection.

Until `PADDLE_WEBHOOK_SECRET` is set, the endpoint accepts nothing. There
is no "not configured yet, so allow" branch.

## Secret boundaries

| Value | Server | Browser |
|---|---|---|
| `PADDLE_API_KEY` | yes — signs every server call | **never** |
| `PADDLE_WEBHOOK_SECRET` | yes — verifies every event | **never** |
| `PADDLE_CLIENT_TOKEN` | yes | yes — Paddle designed it for this |
| price id, transaction id | yes | yes — identifiers, not capabilities |

The client token is not compiled into the frontend and is not read from
`NEXT_PUBLIC_*`. The backend returns it in the checkout response, together
with the environment, so the frontend holds no provider configuration of
its own and has nothing to mix up.

Enforced by tests, not by convention: `tests/test_payment_security.py`
greps the frontend sources for the two server-only names, checks the
checkout response schema for secret-shaped fields, and feeds
secret-shaped strings through the log redactor.

## Environment separation

`PADDLE_ENV` is explicit and checked against the key's own prefix. A live
key under `sandbox` and a sandbox key under `live` both refuse to work
before any request is made. Production is not a default anywhere: the
environment defaults to `sandbox`, and both secrets default to unset.

## Refunds

A refund arrives as `adjustment.created` with `action == "refund"`,
naming a **transaction**, not our purchase — which is why `provider_ref`
exists as a column separate from `external_id`.

The invariant is unchanged: paid access exists while at least one PAID
purchase for that audit remains effective. Refund one of two, access
stays; refund the last, every paid path closes at once — on-screen full
view, durable report link, and downloads. Nothing is deleted: the purchase
becomes `REFUNDED` and keeps its history.

## Failure modes we keep visible

**Paid but not provisioned.** Payment confirmed, entitlement creation
failed. The purchase stays PAID, `guest.unprovisioned_purchases()` finds
it, and re-running the unlock is idempotent. Payment is never re-labelled
unpaid because provisioning failed.

**Failed payment.** The purchase stays PENDING; the failure lives in the
event journal. A declined card must not become a terminal state, or the
buyer would need us to act before they could try again.

**Abandoned checkout.** No event at all. The pending row survives, and the
next attempt reuses it. Cancellation is a browser fact, which is why the
frontend owns that state and the backend never claims it.

**Two tabs, two payments.** One intent, two provider transactions, both
completed. The second becomes its own PAID purchase against the same
audit, so it can be refunded independently. Swallowing it silently would
mean the buyer paid twice with one row to refund, and refunding that row
would remove access that was paid for twice.

**Event naming a purchase we do not have.** Rejected, journalled as
`failed`, replayable. Creating a purchase from the event would let anyone
with a valid signature invent a sale for us.

## Manual steps that remain

The integration is complete except for one value that does not exist yet.

1. Paddle Sandbox → Developer Tools → Notifications → New destination.
2. URL: `https://<host>/v1/webhooks/paddle`.
3. Events: `transaction.completed`, `transaction.payment_failed`,
   `adjustment.created`. (`transaction.canceled` optional — it is
   acknowledged and ignored.)
4. Copy the signing secret into `PADDLE_WEBHOOK_SECRET`.
5. Copy the client-side token into `PADDLE_CLIENT_TOKEN`.
6. Set `BILLING_PROVIDER=paddle`.

Adding the webhook secret is the only missing webhook configuration step.
