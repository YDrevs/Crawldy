/**
 * legal-terms — en. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "These terms govern Crawldy, Free Preview, paid reports, accounts, Pack, Monthly, and Actual AI Presence." },
  { kind: "heading", text: "Parties" },
  { kind: "para", text: "Crawldy is operated by LIMITED LIABILITY COMPANY “Accurly” (LLC “Accurly”), Ukrainian company identification code 46295102, registered at 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "“You” means the individual using Crawldy or the organization on whose behalf Crawldy is used. If you act for an organization, you confirm that you may accept these terms for it." },
  { kind: "heading", text: "Acceptance and eligibility" },
  { kind: "para", text: "By using Crawldy, creating an account, or purchasing a service, you agree to these Terms, the Privacy and Cookie Policy, the Refund and Cancellation Policy, and the Acceptable Use Policy. Before payment, you must be able to open and save the current versions." },
  { kind: "para", text: "Accounts may be created and services purchased by users who are legally able to enter into binding contracts on their own." },
  { kind: "heading", text: "The service" },
  { kind: "para", text: "Crawldy analyzes accessible website pages and produces a report about Search and AI visibility, technical condition, performance, accessibility, and observable basic protection signals. The report shows coverage, findings, evidence, impact, and priorities." },
  { kind: "para", text: "The report is a snapshot of what was accessible at the time of analysis. The website, search systems, AI services, and standards may change later." },
  { kind: "heading", text: "Free Preview" },
  { kind: "para", text: "Free Preview may be run without an account and has no commercial limit on the number of previews. It shows a limited result: an overall score, coverage, and a small number of leading issues. It does not unlock the full report, grant a paid full-analysis entitlement, or call Actual AI Presence providers." },
  { kind: "para", text: "Technical rate, concurrency, and bot-protection limits may apply for stability and security. They are not a pricing quota." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Single is a one-time purchase of the full report for a specific audit. Registration is not required. After confirmed payment, the purchaser receives a secure link to that exact report. The link remains available for 12 months. The purchaser is responsible for keeping it confidential." },
  { kind: "para", text: "Account creation after purchase is optional. The report may be attached to an account only after ownership is verified. An unverified email match is not enough." },
  { kind: "para", text: "Single includes the Actual AI Presence quantity shown in checkout and the purchase confirmation. The launch configuration includes one check." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Pack requires an account. It grants the number of full analyses and Actual AI Presence checks shown before payment. Unused Pack analyses do not expire and are not removed by purchasing, renewing, or cancelling Monthly." },
  { kind: "para", text: "Pack is not a subscription and does not renew automatically." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly requires an account and renews each month at the price shown before payment. It includes unlimited full website analyses and a separately configured number of Actual AI Presence checks for each paid monthly period." },
  { kind: "para", text: "“Unlimited” means there is no commercial count limit on full analyses. Crawldy may use reasonable technical rate, queue, and concurrency controls for security and stability. These controls must not become a hidden paid quota." },
  { kind: "para", text: "Actual AI Presence is not unlimited. Its monthly allowance is shown before payment and resets at the start of each paid period. Unused monthly allowance does not roll over unless the plan page expressly says otherwise." },
  { kind: "para", text: "Monthly can be cancelled in the customer area or through the available subscription-management tool. Cancellation stops the next renewal. Access continues until the end of the paid period unless applicable law or a confirmed refund requires otherwise." },
  { kind: "para", text: "An organization cannot have two concurrent active or other non-terminal Monthly subscriptions." },
  { kind: "heading", text: "Websites you may analyze" },
  { kind: "para", text: "You may submit a website owned by you, your organization, or a client who has properly authorized the analysis. Only public pages may be analyzed for a lawful purpose." },
  { kind: "para", text: "Do not provide passwords, tokens, private links, account areas, private documents, or a target whose analysis violates law, contract, or another person’s rights." },
  { kind: "heading", text: "Actual AI Presence" },
  { kind: "para", text: "Actual AI Presence sends generated questions to external AI providers and records the answers received at a particular time. Provider models, availability, rules, and outputs may change." },
  { kind: "para", text: "The result does not guarantee that a brand will or will not be mentioned to another user, at another time, in another country, or with another wording." },
  { kind: "heading", text: "Payments through Paddle" },
  { kind: "para", text: "Payments are made through Paddle. Under Paddle’s standard model, Paddle acts as an authorized reseller and Merchant of Record and handles the payment, applicable taxes, and receipt. LLC “Accurly” operates Crawldy and supplies access to the service." },
  { kind: "para", text: "Before payment, checkout shows the selected product, price, currency, applicable tax, and renewal terms. For a transaction, the amount and currency accepted in checkout control unless mandatory law requires otherwise." },
  { kind: "para", text: "Paid access is granted only after confirmed payment. Closing checkout does not itself mean that payment succeeded. If status is unresolved, Crawldy must reconcile the transaction and must not invite a second payment until the result is known." },
  { kind: "heading", text: "Failed analyses and restored rights" },
  { kind: "para", text: "If a full analysis fails because of a Crawldy technical error, we may rerun it, restore the used Pack or Monthly entitlement, or refund Single under the Refund and Cancellation Policy." },
  { kind: "para", text: "The target website may be unavailable, block access, contain an incorrect address, or respond only in part. Crawldy will disclose actual coverage and will not invent unavailable data." },
  { kind: "heading", text: "Account and access security" },
  { kind: "para", text: "You are responsible for accurate account information, protecting your sign-in method, and the actions of users in your organization. Use the contact form if you suspect unauthorized access." },
  { kind: "para", text: "Do not share a guest report link with anyone who should not see its contents." },
  { kind: "heading", text: "Use of reports" },
  { kind: "para", text: "You may use, download, and share a purchased report within your organization. An agency or consultant may analyze a client website and share the report with that client when properly authorized." },
  { kind: "para", text: "This does not allow resale of accounts, credits, automated access, or Crawldy itself without a separate agreement. Crawldy software, design, methodology, check catalogue, and marks remain the property of LLC “Accurly” or their respective owners." },
  { kind: "heading", text: "Limits of the report" },
  { kind: "para", text: "Crawldy is an automated information tool. A report is not:" },
  {
    kind: "list",
    items: [
      "a guarantee of ranking or indexing by a search system;",
      "a guarantee of an AI assistant mentioning or recommending a brand;",
      "a penetration test, vulnerability assessment, or security certification;",
      "WCAG certification;",
      "legal, financial, or other professional advice;",
      "an automatic change to the website.",
    ],
  },
  { kind: "para", text: "You must assess recommendations before making changes and use an appropriate specialist for high-impact decisions." },
  { kind: "heading", text: "Availability" },
  { kind: "para", text: "We aim to keep Crawldy available but do not guarantee uninterrupted or error-free operation. Maintenance, external providers, network events, website changes, and events beyond reasonable control may affect availability." },
  { kind: "heading", text: "Suspension" },
  { kind: "para", text: "We may limit or suspend access when needed for security, law, abuse prevention, fraud investigation, or an unpaid subscription. Where practicable, we will explain the reason and how to resolve it." },
  { kind: "para", text: "A technical limit or Monthly cancellation does not erase separately purchased unused Pack analyses. An exception may apply after a refund, confirmed fraud, chargeback, or legal requirement." },
  { kind: "heading", text: "Liability" },
  { kind: "para", text: "Nothing in these Terms limits liability that cannot lawfully be limited or mandatory consumer rights." },
  { kind: "para", text: "To the extent permitted by law, LLC “Accurly” is not liable for indirect loss, lost profit, loss of ranking, expected AI mentions, or decisions made solely from an automated report. Total liability for a paid service is limited to the amount paid for the relevant Single or Pack, or for Monthly, the amount paid in the preceding 12 months. This limit does not apply to wilful misconduct, fraud, gross negligence, or any liability that cannot legally be limited." },
  { kind: "heading", text: "Ending use" },
  { kind: "para", text: "You may stop using Crawldy, cancel Monthly, and delete your account. Account deletion does not remove payment or other records that must be retained by law." },
  { kind: "heading", text: "Governing law" },
  { kind: "para", text: "These Terms are governed by the law of Ukraine. Disputes are heard by competent Ukrainian courts unless mandatory consumer rules allow the user to rely on another law or forum." },
  { kind: "para", text: "The parties should first try to resolve the issue through the protected contact form." },
  { kind: "heading", text: "Changes" },
  { kind: "para", text: "We may update these Terms when the product, providers, or law changes. The new version applies from the stated date. Material changes do not retroactively alter a completed one-time purchase. We will notify registered users of material changes through an available channel." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, Ukrainian company identification code 46295102." },
  { kind: "para", text: "59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Use the protected Crawldy contact form." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Terms of Service",
        meta: ["**Effective date:** `1 January 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contents",
        relatedLabel: "Related documents",
        related: [
    { label: "Privacy and Cookies", href: "/privacy" },
    { label: "Refunds and Cancellation", href: "/refunds" },
    { label: "Acceptable Use", href: "/acceptable-use" },
    { label: "Contact", href: "/contact" },
        ],
      }}
    />
  );
}

export const en: LocalizedPage = {
  slug: "terms",
  title: "Terms of Service — Crawldy",
  h1: "Terms of Service",
  description: "These terms govern Crawldy, Free Preview, paid reports, accounts, Pack, Monthly, and Actual AI Presence.",
  navLabel: "Terms of Service",
  Body,
};
