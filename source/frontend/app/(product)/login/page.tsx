"use client";

/**
 * Вхід і реєстрація.
 *
 * Одна сторінка на обидва наміри, але **два стани**, а не дві однакові
 * кнопки поруч. Різниця не косметична: вимоги до пароля належать тому,
 * хто його створює, і показувати «щонайменше 12 символів» тому, хто
 * вводить наявний, — це давати правило там, де його вже не застосувати.
 *
 * Заголовка й підзаголовка немає навмисно: призначення форми зрозуміле
 * і так (рішення власника, екрани 04–05). Маркетингу тут немає з тієї
 * самої причини — людина, яка дійшла до входу, уже переконана.
 *
 * Форма існує всіма шістьма мовами публічного сайту. Кабінет за нею —
 * en/uk, тож у профіль зберігається лише мова, яку кабінет уміє
 * показати; решта мов живе в дорозі назад (логотип → мовна головна).
 *
 * Валідація контрольована застосунком (`noValidate`): стандартні
 * браузерні підказки приходять мовою браузера, а не мовою сторінки.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LanguageSwitcher } from "../../components/LanguageSwitcher";
import { LogoStacked } from "../../components/Brand";
import { Alert, Button, Input, Panel, Spinner } from "../../components/primitives";
import { getMe, login, register, saveMyLocale } from "../../lib/api";
import type { Locale } from "../../lib/contracts";
import {
  COMPLETE_LOCALES,
  PUBLIC_SITE_LOCALES,
  asSiteLocale,
  productHref,
  publicHomeHref,
} from "../../lib/i18n";
import { landingFor, safeNext } from "../../lib/landing";
import { MIN_PASSWORD_LENGTH } from "../../lib/password-policy";
import { readSiteLocale } from "../../lib/site-locale";
import { LocaleProvider, useT } from "../../lib/locale";
import { problemKey } from "../../lib/problem";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      }
    >
      <LocalizedLogin />
    </Suspense>
  );
}

/** Достатньо, щоб зловити одруківку; сувору перевірку робить бекенд. */
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Дозволені значення `?notice=` — і лише вони.
 *
 * Перелік, а не підстановка: інакше довільний рядок з адреси став би
 * ключем каталогу, і сторонній міг би підібрати посилання, що показує
 * на формі входу чуже повідомлення.
 */
const NOTICE_KEYS: Record<string, string> = {
  reset: "auth.noticeReset",
  changed: "auth.noticeChanged",
};

function LocalizedLogin() {
  // `?lang=` несе МОВУ САЙТУ, з якого прийшли, — будь-яку з шести, і
  // форма тепер існує кожною з них. Дорога назад (логотип) веде на
  // мовну версію головної: саме звідси й був баг «/uk → вхід →
  // головна стала англійською». `?next=` зберігає намір: обраний пакет
  // чи підписка продовжуються одразу після автентифікації.
  const params = useSearchParams();
  const router = useRouter();
  const requested = asSiteLocale(params.get("lang"));
  const [site, setSite] = useState<Locale>(requested ?? "en");

  // Адреса головніша за памʼять: `?lang=` — це те, що людина щойно
  // читала. Памʼять потрібна для входу без параметра — із закладки,
  // з листа, після виходу з кабінету. Читається в ефекті, бо на сервері
  // сховища немає, а розбіжність розмітки при гідратації — окрема біда.
  useEffect(() => {
    if (requested === null) {
      const remembered = readSiteLocale();
      if (remembered !== null) setSite(remembered);
    }
  }, [requested]);
  const requestedNext = params.get("next");
  const next = safeNext(requestedNext);
  // Що сталося перед тим, як людина сюди потрапила. Після скидання й
  // після зміни пароля сесії немає — сказати про успіх більше нема
  // кому, тож новина їде параметром адреси.
  const notice = NOTICE_KEYS[params.get("notice") ?? ""] ?? null;

  // Хто вже увійшов, не мусить вводити пароль удруге: намір їде далі
  // одразу. Роль питається в того самого запиту — другого не треба.
  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (!cancelled) {
          router.replace(landingFor(me.user?.platform_role, requestedNext));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [requestedNext, router]);

  return (
    <LocaleProvider locale={site}>
      <SignIn
        locale={site}
        notice={notice}
        // Явний вибір у перемикачі — єдине, що змінює мову: він рухає
        // і форму, і дорогу назад.
        onLocale={setSite}
        homeHref={publicHomeHref(site)}
        requestedNext={requestedNext}
      />
    </LocaleProvider>
  );
}

type Mode = "signin" | "signup";

function SignIn({
  locale,
  notice,
  onLocale,
  homeHref,
  requestedNext,
}: {
  locale: Locale;
  /** Ключ каталогу про те, що сталося перед приходом сюди, або `null`. */
  notice: string | null;
  onLocale: (locale: Locale) => void;
  /** Головна МОВОЮ САЙТУ відвідувача — логотип веде туди, не в «/». */
  homeHref: string;
  /** Намір із адреси, як він прийшов: `null` — його не було. */
  requestedNext: string | null;
}) {
  const t = useT();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const creating = mode === "signup";

  /** Валідація застосунку — ключ каталогу або null, коли все гаразд. */
  function invalidKey(): string | null {
    if (!email.trim()) return "auth.emailRequired";
    if (!EMAIL_SHAPE.test(email.trim())) return "auth.emailInvalid";
    if (!password) return "auth.passwordRequired";
    if (creating && password.length < MIN_PASSWORD_LENGTH) return "auth.passwordHint";
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
      const me = await (creating
        ? register(email, password)
        : login(email, password));
      // Мова їде далі в кабінет, але лише та, яку кабінет уміє показати
      // (en/uk): збережена «de» дала б змішаномовний інтерфейс. Явно
      // збережений вибір у профілі не перезаписується ніколи.
      if (!me.user?.locale && (COMPLETE_LOCALES as string[]).includes(locale)) {
        await saveMyLocale(locale).catch(() => undefined);
      }
      router.replace(landingFor(me.user?.platform_role, requestedNext));
    } catch (caught) {
      // Стан тримає ключ каталогу: сирий detail бекенда — службовий
      // рядок однією мовою на всі інтерфейси, а не текст для людини.
      setError(
        problemKey(caught, {
          401: "auth.badCredentials",
          409: "auth.emailTaken",
          422: "auth.passwordHint",
        }),
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
        {/* Назад — на головну МОВОЮ, з якої прийшли. Зашитий «/» тут
            мовчки перемикав українця на англійську. */}
        <Link href={homeHref} aria-label="Crawldy">
          <LogoStacked width={168} />
        </Link>

        <Panel className="w-full max-w-[26rem]">
          {notice ? (
            <div className="mb-4">
              <Alert tone="success">{t(notice)}</Alert>
            </div>
          ) : null}
          <form
            className="flex flex-col gap-4"
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
            <Input
              label={t("auth.password")}
              type="password"
              autoComplete={creating ? "new-password" : "current-password"}
              // Правило пароля — лише там, де пароль створюють. Той, хто
              // вводить наявний, уже нічого з ним зробити не може.
              hint={creating ? t("auth.passwordHint") : undefined}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {error ? <Alert tone="danger">{t(error)}</Alert> : null}
            <Button type="submit" loading={busy} className="w-full">
              {creating ? t("auth.signUp") : t("auth.signIn")}
            </Button>
            {/* Прямо під кнопкою входу й лише в режимі входу: той, хто
                створює акаунт, пароля ще не має, тож відновлювати йому
                нічого. У навігації цього посилання немає навмисно —
                воно потрібне рівно тут і більше ніде. */}
            {creating ? null : (
              <Link
                href={productHref("/forgot", locale)}
                className="rounded-sm text-center text-sm font-medium text-accent-text hover:text-primary"
              >
                {t("auth.forgot")}
              </Link>
            )}
          </form>

          <div className="mt-5 border-t border-border pt-5 text-center text-sm">
            <span className="text-secondary">
              {creating ? t("auth.haveAccount") : t("auth.newHere")}
            </span>{" "}
            <button
              type="button"
              onClick={() => {
                setMode(creating ? "signin" : "signup");
                setError("");
              }}
              className="rounded-sm font-medium text-accent-text hover:text-primary"
            >
              {creating ? t("auth.signIn") : t("auth.signUp")}
            </button>
          </div>
        </Panel>
      </main>
    </div>
  );
}
