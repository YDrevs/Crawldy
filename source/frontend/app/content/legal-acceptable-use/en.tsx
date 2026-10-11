/**
 * legal-acceptable-use — en. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "These rules protect users, Crawldy, and websites being analyzed." },
  { kind: "heading", text: "Permitted use" },
  { kind: "para", text: "You may analyze public pages of your own website, your organization’s website, or a client website when the client has authorized the analysis. Agencies and consultants may use Crawldy for client websites and provide purchased reports to those clients." },
  { kind: "heading", text: "Prohibited use" },
  { kind: "para", text: "You must not use Crawldy to:" },
  {
    kind: "list",
    items: [
      "analyze a website for an unlawful, fraudulent, harmful, or harassing purpose;",
      "access pages, files, or systems that are not public;",
      "provide passwords, tokens, private links, secret keys, or other credentials;",
      "bypass login, CAPTCHA, Turnstile, rate limits, technical blocks, or other safeguards;",
      "exploit vulnerabilities, conduct penetration testing, deliver malware, deny service, or perform destructive testing;",
      "deliberately create excessive load or avoid technical limits through multiple sessions, accounts, or organizations;",
      "violate privacy, copyright, trademark, contractual restrictions, or other third-party rights;",
      "resell accounts, credits, automated access, or copy Crawldy without a separate agreement;",
      "present a report as an official certification of security, accessibility, legal compliance, search ranking, or AI recommendation.",
    ],
  },
  { kind: "heading", text: "How analysis works" },
  { kind: "para", text: "Crawldy reads observable signals from public pages. The service must not sign in to private areas, submit credentials, send forms, bypass protection, or perform intrusive testing without a separately designed and expressly authorized feature and lawful basis." },
  { kind: "heading", text: "Protecting the service" },
  { kind: "para", text: "We may stop or slow an analysis when it creates a risk for the target website, Crawldy, other users, or the law. Technical anti-abuse measures are separate from paid entitlements." },
  { kind: "para", text: "Where practicable, a restriction is limited to the problematic analysis or user. Monthly cancellation or a technical block does not erase lawfully purchased Pack entitlements unless they were refunded, fraud is confirmed, or law requires it." },
  { kind: "heading", text: "Reporting a concern" },
  { kind: "para", text: "If you believe Crawldy is being used improperly against your website, use the protected contact form. Provide the domain, time, and available technical information. Do not send passwords or secrets." },
  { kind: "heading", text: "Enforcement" },
  { kind: "para", text: "Depending on severity, we may warn the user, stop an analysis, temporarily limit access, or terminate an account. We may retain necessary evidence and contact competent authorities when required by law or needed to address a genuine threat." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, Ukrainian company identification code 46295102." },
  { kind: "para", text: "Use the protected Crawldy contact form." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Acceptable Use",
        meta: ["**Effective date:** `1 January 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contents",
        relatedLabel: "Related documents",
        related: [
    { label: "Privacy and Cookies", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Refunds and Cancellation", href: "/refunds" },
    { label: "Contact", href: "/contact" },
        ],
      }}
    />
  );
}

export const en: LocalizedPage = {
  slug: "acceptable-use",
  title: "Acceptable Use — Crawldy",
  h1: "Acceptable Use",
  description: "These rules protect users, Crawldy, and websites being analyzed.",
  navLabel: "Acceptable Use",
  Body,
};
