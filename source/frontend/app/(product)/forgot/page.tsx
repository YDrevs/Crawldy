"use client";

/**
 * Запит на відновлення пароля.
 *
 * **Підтвердження нейтральне, і це головне в цьому екрані.** Ми не
 * кажемо «лист надіслано» — ми кажемо «якщо акаунт із такою адресою
 * існує». Різниця не в делікатності формулювання: сказати «такої адреси
 * немає» означає перетворити форму на безкоштовний перевіряльник, чи
 * зареєстрована людина в сервісі. Бекенд віддає однаковий 202 обом
 * випадкам, тож іншого цей екран і не знає — показати він може тільки
 * те, що йому відповіли.
 *
 * Мова їде з `?lang=` — тією ж дорогою, що й на форму входу, і тим же
 * правилом: англійська без параметра, решта з параметром. Вона ж
 * передається бекенду як запасна: мову листа обирає профіль адресата,
 * а мова сторінки стає в пригоді лише тоді, коли профіль її не має.
 *
 * Валідація контрольована застосунком (`noValidate`): браузерні
 * підказки приходять мовою браузера, а не мовою сторінки.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LanguageSwitcher } from "../../components/LanguageSwitcher";
import { LogoStacked } from "../../components/Brand";
import { Alert, Button, Input, Panel, Spinner } from "../../components/primitives";
import { requestPasswordReset } from "../../lib/api";
import type { Locale } from "../../lib/contracts";
import {
  PUBLIC_SITE_LOCALES,
  asSiteLocale,
  productHref,
  publicHomeHref,
} from "../../lib/i18n";
import { LocaleProvider, useT } from "../../lib/locale";
import { problemKey } from "../../lib/problem";
import { readSiteLocale } from "../../lib/site-locale";

/** Достатньо, щоб зловити одруківку; сувору перевірку робить бекенд. */
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      }
    >
      <LocalizedForgot />
    </Suspense>
  );
}

function LocalizedForgot() {
  const params = useSearchParams();
  const requested = asSiteLocale(params.get("lang"));
  const [site, setSite] = useState<Locale>(requested ?? "en");

  // Адреса головніша за памʼять: `?lang=` — те, що людина щойно читала.
  // Памʼять потрібна для входу без параметра: із закладки чи з листа.
  useEffect(() => {
    if (requested === null) {
      const remembered = readSiteLocale();
      if (remembered !== null) setSite(remembered);
    }
  }, [requested]);

  return (
    <LocaleProvider locale={site}>
      <RequestForm locale={site} onLocale={setSite} />
    </LocaleProvider>
  );
}

function RequestForm({
  locale,
  onLocale,
}: {
  locale: Locale;
  onLocale: (locale: Locale) => void;
}) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit() {
    const value = email.trim();
    if (!value) {
      setError("auth.emailRequired");
      return;
    }
    if (!EMAIL_SHAPE.test(value)) {
      setError("auth.emailInvalid");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await requestPasswordReset(value, locale);
      setSent(true);
    } catch (caught) {
      // 503 означає, що листа нікому передати. Прикидатися успіхом тут
      // не можна: людина чекала б на те, чого не буде.
      setError(problemKey(caught, { 503: "recovery.unavailable" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex justify-end p-4">
        <LanguageSwitcher
          current={locale}
          locales={PUBLIC_SITE_LOCALES}
          onSelect={onLocale}
          label={t("auth.language")}
        />
      </div>

      <main className="flex flex-1 flex-col items-center justify-center gap-7 px-5 pb-16">
        <Link href={publicHomeHref(locale)} aria-label="Crawldy">
          <LogoStacked width={168} />
        </Link>

        <Panel className="w-full max-w-[26rem]">
          {sent ? (
            <div className="flex flex-col gap-4">
              <Alert tone="success" title={t("recovery.sentTitle")}>
                {t("recovery.sentBody")}
              </Alert>
              <Link
                href={productHref("/login", locale)}
                className="rounded-sm text-center text-sm font-medium text-accent-text hover:text-primary"
              >
                {t("recovery.backToSignIn")}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-lg font-semibold tracking-tight text-primary">
                {t("recovery.title")}
              </h1>
              <p className="mt-2 text-sm text-secondary">{t("recovery.intro")}</p>
              <form
                className="mt-5 flex flex-col gap-4"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit();
                }}
              >
                <Input
                  label={t("auth.email")}
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
                {error ? <Alert tone="danger">{t(error)}</Alert> : null}
                <Button type="submit" loading={busy} className="w-full">
                  {t("recovery.submit")}
                </Button>
              </form>
              <div className="mt-5 border-t border-border pt-5 text-center text-sm">
                <Link
                  href={productHref("/login", locale)}
                  className="rounded-sm font-medium text-accent-text hover:text-primary"
                >
                  {t("recovery.backToSignIn")}
                </Link>
              </div>
            </>
          )}
        </Panel>
      </main>
    </div>
  );
}
