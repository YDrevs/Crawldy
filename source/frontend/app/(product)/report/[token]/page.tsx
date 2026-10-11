"use client";

/**
 * Куплений звіт за постійним платним посиланням.
 *
 * Це вхід у продукт, а не в файл: гостьова сесія живе сім днів, а
 * куплений звіт — доти, доки його не відкликано (повернення коштів,
 * безпека). Людина з токеном відкриває той самий повний екран, що й
 * передплатник у кабінеті, — без сесії, без акаунта, без пошти.
 *
 * Сторінка не залежить від гостьової сесії навмисно й не має фолбеку
 * на неї: право тут доводить сам токен через `GET /r/{token}?format=web`,
 * і бекенд віддає екранну форму лише платним посиланням.
 *
 * Мова інтерфейсу йде за мовою звіту: посилання створене з мовою, і
 * людина, якій його переслали, читає обидві частини екрана однією мовою.
 *
 * Тіло звіту — спільний `AuditResultView`: подання одне на весь
 * продукт, і цей маршрут не є винятком.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AuditResultView, hostOf } from "../../../components/AuditResultView";
import { LogoStacked } from "../../../components/Brand";
import { AccountCta, GuestDownloads } from "../../../components/GuestReport";
import { Spinner } from "../../../components/primitives";
import { readSharedReport } from "../../../lib/api";
import type { AuditResult, Locale } from "../../../lib/contracts";
import { COMPLETE_LOCALES, publicHomeHref } from "../../../lib/i18n";
import { LocaleProvider, useLocale } from "../../../lib/locale";

export default function DurableReportPage() {
  const params = useParams<{ token: string }>();
  const [result, setResult] = useState<AuditResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    readSharedReport(params.token)
      .then((view) => {
        if (!cancelled) setResult(view);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [params.token]);

  if (failed) {
    // 404 навмисно не розшифровується: недійсний, відкликаний і чужий
    // токени виглядають однаково — як і на бекенді.
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col items-center justify-center gap-3 px-6 py-12 text-center">
        <LogoStacked />
        <p className="text-secondary">This link is not valid.</p>
      </main>
    );
  }

  if (result === null) {
    return (
      <main className="flex min-h-screen items-center justify-center text-muted">
        <Spinner className="size-5" />
      </main>
    );
  }

  const reportLocale = result.localization.locale as Locale;
  const locale = COMPLETE_LOCALES.includes(reportLocale) ? reportLocale : "en";

  return (
    <LocaleProvider locale={locale}>
      <DurableReport token={params.token} result={result} />
    </LocaleProvider>
  );
}

function DurableReport({
  token,
  result,
}: {
  token: string;
  result: AuditResult;
}) {
  const { t, locale } = useLocale();

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-6 py-12">
      {/* Знак по центру, адреса під ним — так само, як на сторінці
          результату. Це той самий документ, лише відкритий за
          посиланням, і виглядати він має тим самим. */}
      <header className="mb-10 flex flex-col items-center gap-3">
        <Link href={publicHomeHref(locale)} aria-label="Crawldy">
          <LogoStacked />
        </Link>
        <h1 className="text-base font-medium text-foreground">
          {hostOf(result.origin)}
        </h1>
      </header>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">{t("free.unlockedLead")}</p>
        <GuestDownloads token={token} />
      </div>
      <AuditResultView result={result} />
      <AccountCta />
    </main>
  );
}
