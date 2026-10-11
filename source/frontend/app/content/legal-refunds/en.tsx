/**
 * legal-refunds — en. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "This policy explains Crawldy’s voluntary rules. It does not restrict rights that cannot be excluded by contract or law." },
  { kind: "heading", text: "If checkout is closed" },
  { kind: "para", text: "If you close checkout before completing payment, your audit remains saved. You are not charged unless Paddle confirms the payment. Once non-payment is confirmed, you may try again for the same audit." },
  { kind: "para", text: "If payment status is unresolved, Crawldy first checks the transaction and does not offer another payment until the first result is known." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "The full Single report starts processing immediately after confirmed payment at your request. Once the purchased report has been successfully produced and opened, no voluntary change-of-mind refund is offered except where required by law." },
  { kind: "para", text: "We will refund or rerun the analysis at no extra charge if:" },
  {
    kind: "list",
    items: [
      "the payment was duplicated;",
      "payment was taken but paid access was not provided;",
      "a Crawldy technical error prevented a usable full report and a rerun cannot resolve the issue within a reasonable time.",
    ],
  },
  { kind: "para", text: "A low score, findings, no expected AI mention, or disagreement with an evidence-based result is not by itself a technical error." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "A completely unused Pack may be refunded within 14 calendar days after purchase. Once any full analysis or Actual AI Presence check has been used, no voluntary refund of the entire Pack is offered except where required by law." },
  { kind: "para", text: "If an entitlement was consumed but the analysis failed because of a Crawldy technical error, that entitlement is restored. Unused Pack entitlements do not expire." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly can be cancelled at any time. Cancellation stops the next renewal and access continues through the paid period." },
  { kind: "para", text: "The first Monthly payment may be refunded within 14 calendar days if no full analysis or Actual AI Presence check has been run after payment." },
  { kind: "para", text: "The most recent automatic renewal may be refunded within 7 calendar days after the charge if no full analysis or Actual AI Presence check has been run in the new period. After use in the new period, no voluntary refund or prorating is offered except where required by law." },
  { kind: "para", text: "Cancelling Monthly does not remove separately purchased Pack entitlements." },
  { kind: "heading", text: "Target-website problems" },
  { kind: "para", text: "If a website is unavailable, blocks the analysis, has an incorrect address, or responds only in part, Crawldy shows actual coverage. We will consider a rerun or refund if the result is not usable and that limitation was not reasonably clear before purchase." },
  { kind: "heading", text: "How to request a refund" },
  { kind: "para", text: "Open the protected Crawldy contact form and select “Payment, refund, or subscription.” Provide your reply address, domain, approximate purchase date, and transaction or receipt identifier if available." },
  { kind: "para", text: "Do not send a card number, security code, or bank password." },
  { kind: "para", text: "We will acknowledge the request and provide a decision or ask for the information needed to locate the purchase. An approved refund is issued through Paddle to the original payment method. Timing depends on Paddle, the bank, and the payment method." },
  { kind: "heading", text: "Chargebacks and fraud" },
  { kind: "para", text: "If a payment is disputed without first contacting us, associated entitlements may be suspended while the dispute is reviewed. This does not remove mandatory rights. A confirmed refund, chargeback, or fraudulent payment may cancel the corresponding unused access." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, Ukrainian company identification code 46295102." },
  { kind: "para", text: "Use the protected Crawldy contact form." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Refunds and Cancellation",
        meta: ["**Effective date:** `1 January 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contents",
        relatedLabel: "Related documents",
        related: [
    { label: "Privacy and Cookies", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Acceptable Use", href: "/acceptable-use" },
    { label: "Contact", href: "/contact" },
        ],
      }}
    />
  );
}

export const en: LocalizedPage = {
  slug: "refunds",
  title: "Refunds and Cancellation — Crawldy",
  h1: "Refunds and Cancellation",
  description: "This policy explains Crawldy’s voluntary rules. It does not restrict rights that cannot be excluded by contract or law.",
  navLabel: "Refunds and Cancellation",
  Body,
};
