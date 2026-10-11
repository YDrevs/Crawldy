"use client";

/**
 * Установлення нового пароля за посиланням із листа.
 *
 * **Токен перевіряється ДО того, як щось вводити.** Бекенд має для
 * цього окремий запит, який посилання не витрачає, і саме він тут
 * викликається при відкритті екрана. Інакше людина набирала б новий
 * пароль двічі, тиснула «зберегти» і аж тоді дізнавалася, що посилання
 * застаріло, — найдорожчий спосіб повідомити про це.
 *
 * **Прострочений, використаний, скасований і вигаданий токен дають один
 * і той самий текст.** Розрізняти їх означало б підказувати, що такий
 * токен колись існував.
 *
 * **Слабкий пароль посилання не спалює.** Бекенд перевіряє політику ДО
 * атомарного споживання токена, тож після 422 можна просто ввести
 * інший пароль — і екран на це розрахований: він лишається на місці й
 * не жене по нове посилання.
 *
 * Після успіху — на форму входу тією ж мовою, з підписом про успіх:
 * сесії при скиданні не видається навмисно, людина входить наново.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LanguageSwitcher } from "../../components/LanguageSwitcher";
import { LogoStacked } from "../../components/Brand";
import { Alert, Button, Input, Panel, Spinner } from "../../components/primitives";
import { ApiError, checkPasswordResetToken, resetPassword } from "../../lib/api";
import type { Locale } from "../../lib/contracts";
import {
  PUBLIC_SITE_LOCALES,
  asSiteLocale,
  productHref,
  publicHomeHref,
  withNotice,
} from "../../lib/i18n";
import { LocaleProvider, useT } from "../../lib/locale";
import { MIN_PASSWORD_LENGTH } from "../../lib/password-policy";
import { problemKey } from "../../lib/problem";

/** Стан посилання: поки не спитали, чинне, мертве. */
type LinkState = "checking" | "valid" | "dead";

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      }
    >
      <LocalizedReset />
    </Suspense>
  );
}

function LocalizedReset() {
  const params = useSearchParams();
  const requested = asSiteLocale(params.get("lang"));
  const [site, setSite] = useState<Locale>(requested ?? "en");
  const token = params.get("token") ?? "";

  return (
    <LocaleProvider locale={site}>
      <ResetForm locale={site} onLocale={setSite} token={token} />
    </LocaleProvider>
  );
}

function ResetForm({
  locale,
  onLocale,
  token,
}: {
  locale: Locale;
  onLocale: (locale: Locale) => void;
  token: string;
}) {
  const t = useT();
  const router = useRouter();
  const [link, setLink] = useState<LinkState>("checking");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Одна перевірка на відкриття екрана. Запит навмисно не споживає
  // посилання, тож повторний вхід на ту саму адресу нічого не ламає.
  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setLink("dead");
      return;
    }
    checkPasswordResetToken(token)
      .then(() => {
        if (!cancelled) setLink("valid");
      })
      .catch(() => {
        if (!cancelled) setLink("dead");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  /** Валідація застосунку — ключ каталогу або null, коли все гаразд. */
  function invalidKey(): string | null {
    if (password.length < MIN_PASSWORD_LENGTH) return "auth.passwordHint";
    if (password !== repeat) return "recovery.mismatch";
    return null;
  }

  async function submit() {
    const invalid = invalidKey();
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resetPassword(token, password);
      // Сесії після скидання немає навмисно: людина входить наново вже
      // новим паролем. Мова їде з нею, підпис про успіх — теж.
      router.replace(withNotice(productHref("/login", locale), "reset"));
    } catch (caught) {
      // 404 тут означає, що посилання померло між перевіркою й
      // надсиланням — наприклад, його щойно використали в іншій вкладці.
      if (caught instanceof ApiError && caught.status === 404) {
        setLink("dead");
        return;
      }
      setError(
        problemKey(caught, { 422: "auth.passwordHint", 404: "recovery.linkDead" }),
      );
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
          {link === "checking" ? (
            <p
              className="flex items-center justify-center gap-2 py-6 text-sm text-muted"
              role="status"
            >
              <Spinner className="size-4" />
              {t("recovery.checking")}
            </p>
          ) : link === "dead" ? (
            <div className="flex flex-col gap-4">
              <Alert tone="warning">{t("recovery.linkDead")}</Alert>
              <Link
                href={productHref("/forgot", locale)}
                className="rounded-sm text-center text-sm font-medium text-accent-text hover:text-primary"
              >
                {t("recovery.askAnother")}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-lg font-semibold tracking-tight text-primary">
                {t("recovery.title")}
              </h1>
              <form
                className="mt-5 flex flex-col gap-4"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit();
                }}
              >
                <Input
                  label={t("recovery.newPassword")}
                  type="password"
                  autoComplete="new-password"
                  hint={t("auth.passwordHint")}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <Input
                  label={t("recovery.repeatPassword")}
                  type="password"
                  autoComplete="new-password"
                  value={repeat}
                  onChange={(event) => setRepeat(event.target.value)}
                />
                {error ? <Alert tone="danger">{t(error)}</Alert> : null}
                <Button type="submit" loading={busy} className="w-full">
                  {t("recovery.save")}
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
