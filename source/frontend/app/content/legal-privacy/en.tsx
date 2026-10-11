/**
 * legal-privacy — en. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "This policy explains what data Crawldy processes, why it is needed, who may receive it, and what rights users have." },
  { kind: "heading", text: "Who operates Crawldy" },
  { kind: "para", text: "Crawldy is operated by LIMITED LIABILITY COMPANY “Accurly” (LLC “Accurly”), Ukrainian company identification code 46295102. Registered address: 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "For privacy questions, use the protected Crawldy contact form and select “Privacy and data.”" },
  { kind: "heading", text: "Scope" },
  { kind: "para", text: "This policy applies to `crawldy.ai and crawldy.com`, Free Preview, paid analyses, Actual AI Presence, accounts, the customer area, payments, and the contact form." },
  { kind: "heading", text: "Data we process" },
  { kind: "para", text: "**Website address and analysis data.** We process the submitted URL and domain, publicly available pages, server responses, headers, metadata, links, structured data, performance measurements, findings, evidence, coverage, and scores." },
  { kind: "para", text: "**Account data.** If you create an account, we process your name, email address, authentication data, organization membership, analysis history, purchased balances, and service usage." },
  { kind: "para", text: "**Payment data.** Paddle processes payment details in checkout. Crawldy does not receive the full card number. We receive and store the customer or transaction identifier, selected product, amount, currency, payment status, subscription status, refund data, and other information needed to provide and account for the purchase." },
  { kind: "para", text: "**Actual AI Presence.** For a paid analysis, we may create queries about the brand, website, company, market, or services and send them to OpenAI, Anthropic, Google, and Perplexity. We store the query, provider response, date, model, status, and recorded observation. Free Preview does not run Actual AI Presence." },
  { kind: "para", text: "**Contact form.** We process the name, reply address, subject, message, delivery status, and Cloudflare Turnstile result." },
  { kind: "para", text: "**Technical and security data.** We may process the IP address, browser and device type, language, request time, error logs, session identifiers, rate-limit data, and anti-abuse signals." },
  { kind: "heading", text: "Why we use data" },
  { kind: "para", text: "We use data to:" },
  {
    kind: "list",
    items: [
      "analyze the submitted website and produce a result;",
      "provide the purchased report, keep a Pack balance, or operate Monthly;",
      "run Actual AI Presence after payment;",
      "create and protect an account;",
      "confirm a payment, refund, or cancellation;",
      "answer a request;",
      "detect errors, fraud, automated abuse, and security threats;",
      "meet accounting, tax, and other legal obligations;",
      "improve Crawldy’s reliability and clarity using aggregated or de-identified data.",
    ],
  },
  { kind: "heading", text: "Legal bases" },
  { kind: "para", text: "Where applicable, we process data to perform a contract or take steps before entering one, comply with a legal obligation, pursue legitimate interests in operating and securing the service, or act on your consent. Consent is used for optional analytics or marketing cookies if those tools are enabled." },
  { kind: "heading", text: "Automated analysis" },
  { kind: "para", text: "Crawldy automatically produces technical findings, a score, coverage, and priorities. These results help assess a website, but they do not make a legal or similarly significant decision about a person. An overall score may be unavailable when there is not enough data." },
  { kind: "heading", text: "Who may receive data" },
  { kind: "para", text: "We disclose only the data needed for a particular function:" },
  {
    kind: "list",
    items: [
      "Paddle for checkout, payments, taxes, receipts, subscriptions, refunds, and payment support;",
      "Cloudflare for Turnstile and other enabled security functions;",
      "OpenAI, Anthropic, Google, and Perplexity for paid Actual AI Presence;",
      "hosting, database, storage, authentication, email, monitoring, and backup providers as needed to operate Crawldy;",
      "professional advisers, courts, or public authorities when required by law or needed to protect legal rights.",
    ],
  },
  { kind: "para", text: "We do not sell personal data. We do not intentionally send passwords, payment credentials, or private-page content to Actual AI Presence. Users must not submit that information to Crawldy." },
  { kind: "heading", text: "Retention" },
  {
    kind: "list",
    items: [
      "Free Preview data is kept for up to 30 days unless a longer period is needed for security, a support request, or a legal obligation.",
      "An anonymously purchased Single report and its secure access token are kept for 12 months after purchase.",
      "Account data, report history, Pack, and Monthly records are kept while the account is active. After verified deletion, data not required by law is deleted or de-identified within 30 days. Backups may be retained for up to 90 days.",
      "Contact messages are kept for up to 24 months after the request is closed.",
      "Security and rate-limit logs are kept for up to 90 days unless an incident requires a longer investigation.",
      "Payment, accounting, and tax records are kept for the period required by law.",
      "External providers retain data under their terms and the actual API configuration.",
    ],
  },
  { kind: "heading", text: "Cookies and local storage" },
  { kind: "para", text: "Crawldy may use technically necessary cookies for the operation of the site, authentication, and storing user preferences." },
  { kind: "para", text: "Cloudflare Turnstile processes browser signals needed to distinguish a person from an automated request. Cloudflare states that Turnstile does not access or transmit text entered into a form. Paddle may use its own necessary technologies in checkout under its policy." },
  { kind: "heading", text: "Your rights" },
  { kind: "para", text: "Depending on applicable law, you may ask us to:" },
  {
    kind: "list",
    items: [
      "confirm whether we process your personal data;",
      "provide a copy;",
      "correct inaccurate data;",
      "delete data;",
      "restrict or object to processing;",
      "provide portable data;",
      "withdraw consent for future processing;",
      "explain the source and use of data.",
    ],
  },
  { kind: "para", text: "You may also complain to a competent data-protection authority. Use the protected contact form and select “Privacy and data.” We may ask you to verify your identity or authority to act for an organization." },
  { kind: "heading", text: "Other people’s data and client websites" },
  { kind: "para", text: "You must have a lawful basis to submit a website for analysis. Do not provide private URLs, passwords, tokens, private documents, or secrets. If you act for a client, you are responsible for the necessary permission and notice." },
  { kind: "heading", text: "Eligibility to use the service" },
  { kind: "para", text: "The service is intended for users who are legally able to enter into binding contracts on their own." },
  { kind: "heading", text: "Security" },
  { kind: "para", text: "We use technical and organizational measures to protect data. No system can guarantee absolute security. If an incident occurs, we will act as required by applicable law." },
  { kind: "heading", text: "Changes" },
  { kind: "para", text: "We may update this policy when the product, providers, or law changes. The current date and version will be shown on this page. We will notify registered users of material changes through the account or another available channel." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, Ukrainian company identification code 46295102." },
  { kind: "para", text: "59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Use the protected Crawldy contact form." },
  { kind: "para", text: "---" },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Privacy and Cookies",
        meta: ["**Effective date:** `1 January 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contents",
        relatedLabel: "Related documents",
        related: [
    { label: "Terms of Service", href: "/terms" },
    { label: "Refunds and Cancellation", href: "/refunds" },
    { label: "Acceptable Use", href: "/acceptable-use" },
    { label: "Contact", href: "/contact" },
        ],
      }}
    />
  );
}

export const en: LocalizedPage = {
  slug: "privacy",
  title: "Privacy and Cookies — Crawldy",
  h1: "Privacy and Cookies",
  description: "This policy explains what data Crawldy processes, why it is needed, who may receive it, and what rights users have.",
  navLabel: "Privacy and Cookies",
  Body,
};
