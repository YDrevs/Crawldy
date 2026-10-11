# Application

The website, the cabinet, the admin area and the backend they talk to. Everything here is
`IMPLEMENTED` unless labelled otherwise, and every number was read from the current code.

## Boundaries

| Surface | Path | Audience | Authentication |
|---|---|---|---|
| Public website | `frontend/app/content/**` rendered through a catch-all route | anyone | none |
| Cabinet | `frontend/app/(product)/app/**` | signed-in customer | required; the layout redirects to `/login` when there is no session |
| Admin | `frontend/app/(product)/admin/**` | Crawldy team | required, and role-gated |
| Guest purchase | `frontend/app/(product)/buy`, `/checkout`, `/result` | anonymous buyer | a guest session capability, not an account |
| Backend API | `backend/app/api/routes/**` | the above | `X-API-Key` or session, depending on the route |

Backend route modules: `account`, `admin`, `admin_config`, `admin_ops`, `audits`, `auth`,
`contact`, `health`, `offers`, `plans`, `presence`, `public`, `schedules`, `share`, `sites`,
`webhooks`.

## Locales

Six launch locales, declared once in `frontend/app/lib/i18n.ts`:

```
PUBLIC_SITE_LOCALES = ["en", "de", "es", "fr", "ru", "uk"]
COMPLETE_LOCALES    = ["en", "de", "es", "fr", "ru", "uk"]
```

`PUBLIC_SITE_LOCALES` is the public website. `COMPLETE_LOCALES` is the set the cabinet is
fully written in. They are currently identical, and a test binds them together
(`frontend/app/lib/cabinet-locales.test.ts`) so the two cannot drift apart silently.

`Locale` in `frontend/app/lib/contracts.ts` is a wider type (twelve values). It is the type,
not the launch set; do not read it as a list of supported languages.

Locales are **not translations of one another**. A locale may order sections differently and
use its own examples; what stays equal across locales are the facts about the product.

### Language preservation between website and cabinet

The cabinet has no locale prefix in its URL, so the language of the public site would be lost
on the way in and out. The last public locale is therefore remembered in the browser under
`crawldy_site_locale` (`frontend/app/lib/site-locale.ts`), and every route back to the site is
built from it.

The profile wins over that memory when it has a language: a deliberate choice outranks the
trace of a visit. The memory exists for the case the profile cannot cover.

## Route structure

Pages are declared in one table, `frontend/app/content/registry.ts`. Adding a page means
writing its content and adding a row; the route, the sitemap, `hreflang`, the menu, the footer
and internal linking all read from there.

Fourteen pages are registered. A locale appears for a page only when that page is **written**
in that locale — an empty slot means the URL does not exist, is absent from the language
switcher and is not declared in `hreflang`.

| Pages | Locales | Routes |
|---|---|---|
| `home`, `ai_visibility`, `website_audit`, `seo_audit`, `technical_seo_audit`, `methodology`, `pricing`, `about`, `contact`, `legal_privacy`, `legal_terms`, `legal_refunds`, `legal_acceptable_use` | 6 | 78 |
| `geo_audit` | `en`, `fr` only | 2 |
| **Total public routes** | | **80** |

English has no locale prefix; every other locale is served under `/<locale>/…` with a
localized slug (for example `/pricing`, `/uk/tsiny`, `/de/preise`).

`/robots.txt` and `/sitemap.xml` are route handlers, not pages. The sitemap is the
authoritative list of public routes and reports 80.

### Mirror-host redirects

`frontend/next.config.mjs` redirects `crawldy.com`, `www.crawldy.com` and `www.crawldy.ai` to
the canonical host `crawldy.ai` with **308**, keyed on the `Host` header so local development
and preview builds are unaffected. A permanent redirect is used rather than a cross-domain canonical
because a canonical is advice, while a redirect is not.

## Commerce, exactly as implemented

- **Offers and credits.** A purchase grants credits. Audit credits and AI Presence credits are
  separate quantities and are spent separately (`credit_type` on the purchase model), so a
  package cannot promise units it does not contain.
- **Two purchase funnels.** An anonymous guest funnel (`/buy` → checkout → `/result`) and a
  signed-in funnel from the cabinet. Both open the **same** catalogue offer.
- **Payments.** `backend/app/billing/providers/` implements `fake` and `paddle` behind one
  adapter interface. The fake provider is not registered when the environment is production.
- **Who sells.** `CommerceModel` distinguishes `merchant_of_record` from `direct` — a separate
  concept from who supplies the product and who processed the payment.
- **Entitlement comes from a verified provider event**, never from the browser returning to a
  success URL. Returning from checkout is not proof of payment.
- **Reconciliation.** An operator screen can ask the provider about unreconciled purchases and
  credit only what the provider itself calls paid. It has no authority of its own.

`PLANNED` / `OUT OF CURRENT SCOPE`: a production Paddle configuration, a real production API
origin, and live payment completion. None of these was validated locally — see
[VERIFICATION.md](VERIFICATION.md).

## AI Presence

`backend/app/presence/` asks assistants questions about a niche and records whether the brand
was mentioned, whether it was linked, and which other domains were named. It is a
**measurement of what assistants answered**, produced by a separate run — not a score derived
from how readable the site is.

The general report deliberately carries no single presence score: a combined number would
imply a "visibility" measurement that was never taken. Rates appear only when the metrics
engine actually computed them over enough observations.

## Security headers

`frontend/next.config.mjs` applies four headers to every application route (`source: "/:path*"`),
in a fixed order, and disables the framework banner with `poweredByHeader: false`:

```
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
X-Frame-Options: DENY
Permissions-Policy: camera=(), geolocation=(), microphone=()
```

Known, deliberate limitations:

- **No Content-Security-Policy.** Measured, not skipped: neither enforcement nor Report-Only is
  ready. See [VERIFICATION.md](VERIFICATION.md).
- **No HSTS.** It depends on the HTTPS hosting environment, which does not exist yet.
- **Redirect responses carry no security headers.** Next answers `redirects()` before
  `headers()` is applied, so a 308 carries `Location` and status only. Measured, and harmless:
  a redirect has no body to frame or sniff, and the canonical target serves the full set. This
  is the current implementation, not a rule — middleware or edge hosting may add headers there.
- **`X-Frame-Options` governs other sites framing Crawldy.** It does not affect Crawldy
  embedding third parties, which is what the Paddle overlay and the Turnstile widget do.

## Contact form

The form is always present in the markup; a hidden attribute hides it from sight and from
focus until it is needed. Markup that a script has to draw does not exist for a crawler — and
a product that sells machine-readability cannot afford that mistake on its own site.

It posts with a real `method` and `action` to a first-party route. Bot protection is Cloudflare
Turnstile, whose site key is fetched from the backend before the widget script is loaded.
