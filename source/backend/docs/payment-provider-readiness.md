# Payment provider readiness — read-only gap analysis

> **Historical. Superseded, not corrected.** Written during the overnight
> sweep, before any adapter existed. Everything below was true when
> written and its two real gaps were both genuine; they were closed by
> the Paddle work on 2026-08-25. What was built, and which of the
> options below were chosen, is in `one-off-payments.md`. This file is
> kept as the evidence of what the core looked like beforehand — the
> analysis is why the adapter took the shape it did.

Written during the overnight sweep. **No Paddle code was written, no
Paddle call was made, no Paddle environment variable was added.** This
maps what the provider-neutral core already does against what any
adapter will have to supply, so the Paddle session tomorrow starts from
facts rather than from a survey.

Legend:

- **A** — already supported by core, adapter supplies nothing new
- **B** — adapter work required
- **C** — product decision required before code
- **D** — provider-specific fact that must be verified in sandbox/docs

Everything marked **D** is deliberately left blank. Guessing event names
from memory is how integrations acquire silent bugs, and the repository
contains no Paddle documentation to read.

## What the core already owns

The whole surface the domain sees is `app/billing/providers/base.py`:

```
BillingProvider
    create_customer(organization_id, email) -> ProviderRef
    create_checkout(customer, price_ref, organization_id) -> CheckoutSession
    verify_webhook(headers, body) -> VerifiedBillingEvent
```

Three methods. Everything else — subscription state, entitlements,
periods, credits — the domain derives from events it has already
verified. That is deliberate: asking the provider "what is the current
subscription" would create a second source of truth.

`fake.py` is the only implementation today, and the entire billing test
suite runs through it. That is the strongest readiness signal in this
analysis: the domain has never seen a real provider and does not depend
on one.

## Concept mapping

| Crawldy concept | Provider-neutral form | What a Paddle adapter must supply | Class |
|---|---|---|---|
| Customer | `ProviderRef(provider, external_id)`, stored on `BillingCustomer` | create/lookup call, customer id | **B** |
| Checkout creation | `create_checkout(...) -> CheckoutSession(ref, url)` | transaction/checkout create, hosted URL | **B** |
| One-time transaction | `BillingEventKind.ONE_OFF_PURCHASED` + `OneOffPurchase` | map its event to this kind | **B** + **D** |
| Provider transaction id | `external_event_id` / `ProviderRef.external_id` | which field is stable and unique | **B** + **D** |
| Provider customer id | `customer_ref` on the event | which field carries it | **B** + **D** |
| Checkout return | *not a signal* — see below | nothing; must stay inert | **A** |
| Webhook verification | `verify_webhook` raising `InvalidWebhook` | signature scheme, secret handling | **B** + **D** |
| Successful payment | `ONE_OFF_PURCHASED` | event name | **B** + **D** |
| Failed payment | `PAYMENT_FAILED` | event name | **B** + **D** |
| Canceled checkout | no event — purchase simply stays `PENDING` | nothing | **A** |
| Refund | `ONE_OFF_REFUNDED` | event name | **B** + **D** |
| Duplicate event | `UniqueConstraint(provider, external_event_id)` | supply a stable id | **A** |
| Out-of-order event | `occurred_at` = provider's clock, not ours | populate it from the provider payload | **A** |
| Event journal | `billing_events` table with raw `payload` | nothing | **A** |
| Paid-but-not-provisioned | detectable today; test exists | nothing | **A** |
| Transaction lookup / reconciliation | **absent** | see gap below | **C** |

## Genuine gaps

### 1. Reconciliation has no home yet (**C**)

There is no code that answers "the provider says this was paid — did we
provision it?" in bulk. Today the only detection is per-audit
(`test_paid_but_not_provisioned_is_visible`), which surfaces a stuck
purchase to the person looking at that audit.

That is enough for launch volumes and not enough for a support workflow.
It needs a product decision: is reconciliation a scheduled job, an admin
screen, or a manual query? Do not build it speculatively.

### 2. The guest checkout route does not use the provider protocol at all (**B** + **C**)

This is the largest gap and it is easy to miss, because both sides look
finished in isolation.

`create_customer` and `create_checkout` are **never called anywhere** in
the application. `POST /v1/public/audits/{id}/checkout` mints a random
`purchase_intent` and returns

    f"{settings.checkout_base_url}/{intent}?audit={audit_id}"

— a constructed URL, not a provider session. The route's own docstring
says so: it exists to carry the chain as far as the till, and the amount
arrives when the catalogue has one.

So the adapter work is not "implement three methods and wire them in".
It is that, plus deciding how the intent is carried:

- the generated `purchase_intent` is currently not persisted anywhere,
  so nothing links a returning webhook to the audit except whatever the
  adapter puts in provider custom data;
- `create_customer(organization_id, email)` requires an email, and a
  guest organization has no user and therefore no email.

Options for the email, all defensible: pass a synthetic address, skip
customer creation for one-offs, or make the protocol's email optional.
Decide before writing the adapter, not during.

Options for the intent: persist `OneOffPurchase` as `PENDING` at
checkout time and pass its id as provider custom data, or rely purely on
custom data and create the purchase on the event. The first makes
paid-but-not-provisioned detectable earlier; the second keeps the table
free of abandoned rows.

### 3. Checkout return is deliberately not a signal (**A**, but worth restating)

`test_checkout_return_does_not_unlock` pins it: the browser coming back
from the payment page unlocks nothing. Only a verified event does. Any
adapter that "helpfully" treats a return URL parameter as proof breaks
this, and the test will catch it.

### 4. Price identifiers (**B** + **D**)

`price_ref` on the event is resolved to our `Plan` through `PlanPrice`.
For one-off audit purchases the mapping from a provider price id to
"one audit" must exist as data before the first live checkout.

Pricing numbers themselves are not a technical question and are not
recorded anywhere in this repository by design.

## What must NOT change to accommodate a provider

- `BillingEventKind` is our vocabulary. An adapter translates into it and
  never adds provider words to the domain.
- The domain does not query the provider for state.
- Unlock comes from `AuditUnlock` + a `PAID` purchase, never from an
  email, a return URL, or a session cookie.
- `occurred_at` is the provider's clock. Using arrival time to order
  events describes our network, not the customer's history.
