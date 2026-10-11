"use client";

/**
 * Разова покупка: спершу оплата, потім сайт. Без реєстрації.
 *
 * ## Порядок, і чому саме такий
 *
 * Кнопка «Разова перевірка» на сторінці цін веде сюди, і перше, що тут
 * відбувається, — каса. Людина ще не називала сайту: питати його до
 * оплати означало б виконати роботу, за яку ще не заплатили, а вести на
 * форму входу — вимагати акаунт, якого разова покупка не потребує
 * (рішення власника 2026-09-06).
 *
 * Далі: підтверджена оплата → форма (адреса сайту й факти бренду) →
 * перевірка сайту → перевірка присутності → чотири документи. Обидві
 * перевірки куплені однією оплатою, і питаємо ми про них ОДИН раз.
 *
 * ## Хто така людина без акаунта
 *
 * Гостьова організація без учасників. Спроможність — токен на сім днів;
 * покупка й обидві куплені одиниці належать саме цій організації. Ані
 * користувача, ані пароля тут не створюється ніде.
 *
 * ## Що буде, якщо закрити вкладку
 *
 * Токен гостя живе на вкладку, а оплачена покупка — ні, тож замовлення
 * (номер покупки + токен) лягає в довговічне сховище браузера. Людина,
 * яка заплатила й закрила вкладку, повертається на цю ж адресу й
 * продовжує з того самого місця. Правом це не є: сервер однаково звіряє
 * покупку з організацією токена.
 *
 * ## Ця сторінка нічого не відмикає
 *
 * Повернення браузера з каси не є доказом оплати. Право дає лише
 * перевірена подія провайдера, і саме її чекає стан «оплата
 * підтверджується».
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { LogoStacked } from "../../components/Brand";
import { Icon } from "../../components/Icon";
import {
  Alert,
  Button,
  Field,
  Input,
  Panel,
  Select,
  Spinner,
} from "../../components/primitives";
import { ApiError } from "../../lib/api";
import type { Locale } from "../../lib/contracts";
import {
  downloadGuestPresenceReport,
  issueReportLink,
  readCheckoutConfig,
  readGuestAudit,
  readGuestPresenceRun,
  rememberLocale,
  startGuestPresence,
} from "../../lib/guest-payment";
import { asSiteLocale, publicHomeHref } from "../../lib/i18n";
import { LocaleProvider, useLocale } from "../../lib/locale";
import {
  forgetOrder,
  openOrder,
  readOrder,
  restoreOrderSession,
  startPaidAudit,
} from "../../lib/order";
import { openPaddleOverlay } from "../../lib/paddle";

/** Мови, якими існує набір запитань до помічників. */
const PROMPT_LANGUAGES = ["en", "uk"] as const;

/** Як часто питати сервер про подію провайдера й про хід перевірок. */
const POLL_MS = 4000;

/**
 * Скільки чекати на подію оплати, перш ніж сказати правду.
 *
 * Вебхук приходить секунди. Нескінченний спінер не давав би відрізнити
 * «гроші в дорозі» від «оплати не було», а це різні відповіді.
 */
const PAYMENT_ATTEMPTS = 30;

/**
 * Скільки чекати ПІСЛЯ закритої каси.
 *
 * Вікно закривається і після оплати: подія про успіх іде своїм шляхом і
 * зазвичай приходить за секунди. Але людина, яка просто закрила касу,
 * не має дивитися на спінер дві хвилини — після кількох спроб чесніше
 * сказати, що підтвердження немає.
 */
const CLOSED_ATTEMPTS = 4;

/** Заголовок і пояснення кожного з трьох станів «оплати ще немає». */
const TITLES: Record<"notPaid" | "unknown" | "throttled", string> = {
  notPaid: "order.notPaidTitle",
  unknown: "order.unknownTitle",
  throttled: "order.throttledTitle",
};
const LEADS: Record<"notPaid" | "unknown" | "throttled", string> = {
  notPaid: "order.notPaidLead",
  unknown: "order.unknownLead",
  throttled: "order.throttledLead",
};

/**
 * `notPaid` і `unknown` — різні відповіді, і плутати їх не можна.
 *
 * «Кошти не списано» має право сказати лише той, кому провайдер це
 * підтвердив. Коли він не відповів, чесна відповідь інша: підтвердження
 * ще немає. Один стан на обидва випадки продавав би другу покупку тому,
 * хто вже заплатив.
 */
type Phase =
  | "opening"
  | "waiting"
  | "notPaid"
  | "unknown"
  | "throttled"
  | "lost"
  | "form"
  | "running"
  | "ready"
  | "failed";

export default function BuyPage() {
  const [locale, setLocale] = useState<Locale>("en");
  useEffect(() => {
    const asked = asSiteLocale(new URLSearchParams(window.location.search).get("lang"));
    if (asked) {
      setLocale(asked);
      // Каса повертає без нашого `?lang=`: мову памʼятає гостьова сесія.
      rememberLocale(asked);
    }
  }, []);
  return (
    <LocaleProvider locale={locale}>
      <Buy locale={locale} />
    </LocaleProvider>
  );
}

function Buy({ locale }: { locale: Locale }) {
  const { t } = useLocale();
  const [phase, setPhase] = useState<Phase>("opening");
  const [purchaseId, setPurchaseId] = useState("");
  const [form, setForm] = useState({
    url: "",
    brand: "",
    aliases: "",
    category: "",
    location: "",
    language: locale === "uk" ? "uk" : "en",
  });
  const [auditId, setAuditId] = useState("");
  const [auditStatus, setAuditStatus] = useState("queued");
  const [presenceId, setPresenceId] = useState("");
  const [presenceStatus, setPresenceStatus] = useState("");
  const [linkToken, setLinkToken] = useState("");
  const [problem, setProblem] = useState("");
  const started = useRef(false);
  const waited = useRef(0);
  const presenceAsked = useRef(false);
  const languageTouched = useRef(false);
  // Каса закрилась. Не доказ того, що не заплатили: вікно закривається
  // і після успішної оплати. Але це привід спитати провайдера прямо
  // зараз, а не чекати на подію, якої може не бути ніколи.
  const closed = useRef(false);

  // Мова сторінки приходить у стан після першого рендеру, і початкове
  // значення поля мусить її наздогнати: українська сторінка з «en» у
  // виборі мови запитань виглядає як недоробка. Свідомий вибір людини
  // при цьому не перетирається.
  useEffect(() => {
    if (languageTouched.current) return;
    setForm((current) => ({
      ...current,
      language: locale === "uk" ? "uk" : "en",
    }));
  }, [locale]);

  /**
   * Відкрити касу. Та сама дія і на вході, і в кнопці «спробувати ще раз».
   *
   * Раніше кнопка перезавантажувала адресу, а сторінка на ній діставала
   * з памʼяті ту саму неоплачену покупку — і поверталася в той самий
   * мертвий стан. Тому повтор саме тут, а не в адресному рядку.
   *
   * Друга спроба не плодить кас: сервер віддає ту саму відкриту, поки
   * вона не закрита.
   */
  const beginCheckout = useCallback(async () => {
    setProblem("");
    setPhase("opening");
    waited.current = 0;
    closed.current = false;
    try {
      const opened = await openOrder();
      setPurchaseId(opened.purchase_id);
      const config = await readCheckoutConfig();
      const overlaid = await openPaddleOverlay({
        clientToken: config.client_token || opened.client_token,
        environment: config.environment || opened.environment,
        transactionRef: opened.transaction_ref,
        // Повертаємось СЮДИ ж: покупка вже є, і далі сторінка чекає
        // на подію провайдера, а не вирішує сама.
        successUrl: `${window.location.origin}/buy?order=${opened.purchase_id}&lang=${locale}`,
        onClosed: () => {
          closed.current = true;
        },
      });
      if (!overlaid) {
        if (opened.checkout_url) {
          window.location.assign(opened.checkout_url);
          return;
        }
        // Каса не відкрилась і посилання немає: списувати не було з
        // чого, і це саме той випадок, коли «кошти не списано» — правда.
        setPhase("notPaid");
        return;
      }
      setPhase("waiting");
    } catch (failure) {
      // Забагато спроб — відповідь про НАС, а не про гроші. Називати її
      // «оплата не пройшла» означало б пояснювати людині чужу причину,
      // а порадою «спробуйте ще раз» заганяти в ту саму стіну.
      if (failure instanceof ApiError && failure.status === 429) {
        setPhase("throttled");
        return;
      }
      setProblem(failure instanceof ApiError ? failure.message : "");
      setPhase("notPaid");
    }
  }, [locale]);

  // ── 1. Каса ─────────────────────────────────────────────────────────
  //
  // Рівно один раз: другий виклик — це друга транзакція у провайдера й
  // друга незавершена покупка на одну людину.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      const asked = new URLSearchParams(window.location.search).get("order") ?? "";
      // Токен відновлюємо завжди: та сама гостьова організація тримає
      // покупку й куплені одиниці. А от ПОКУПКУ з памʼяті беремо лише
      // тоді, коли вона справді жива — інакше свіжий візит зі сторінки
      // цін застрягав на чужій неоплаченій касі й одразу показував
      // «оплата не пройшла».
      const known = restoreOrderSession();
      if (asked) {
        setPurchaseId(asked);
        setPhase("waiting");
        return;
      }
      if (known !== null) {
        const state = await readOrder(known.purchaseId).catch(() => null);
        if (state && (state.started_audit_id || state.state === "paid")) {
          setPurchaseId(known.purchaseId);
          setPhase("waiting");
          return;
        }
        forgetOrder();
      }
      await beginCheckout();
    })();
  }, [beginCheckout]);

  // ── 2. Чекаємо на перевірену подію ──────────────────────────────────
  useEffect(() => {
    if (phase !== "waiting" || !purchaseId) return;
    let alive = true;
    const tick = async () => {
      waited.current += 1;
      try {
        // Провайдера питаємо одразу, щойно людина закрила касу: події в
        // такому разі може не бути ніколи. Поки вікно відкрите — лише
        // власні записи, і лише коли вони мовчать надто довго.
        const ask = closed.current || waited.current > 4;
        const state = await readOrder(purchaseId, ask);
        if (!alive) return;
        if (state.started_audit_id) {
          setAuditId(state.started_audit_id);
          setPhase("running");
          return;
        }
        if (state.state === "paid") {
          setPhase("form");
          return;
        }
        if (state.state === "refunded" || state.charged === false) {
          // Провайдер підтвердив: грошей не брали. Лише тут ми маємо
          // право це сказати.
          setPhase("notPaid");
          return;
        }
        // Провайдер не відповів «ні» — значить, ми не знаємо. Після
        // закритої каси чекати довго нема сенсу, але й обіцяти, що
        // кошти не списано, не можна.
        const enough = closed.current ? CLOSED_ATTEMPTS : PAYMENT_ATTEMPTS;
        if (waited.current >= enough) setPhase("unknown");
      } catch {
        if (waited.current >= PAYMENT_ATTEMPTS) setPhase("lost");
      }
    };
    void tick();
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [phase, purchaseId]);

  // ── 3. Названий сайт ────────────────────────────────────────────────
  const launch = useCallback(async () => {
    const url = form.url.trim();
    if (!url || !purchaseId) return;
    setProblem("");
    try {
      const audit = await startPaidAudit(purchaseId, url);
      setAuditId(audit.audit_id);
      setAuditStatus(audit.status);
      setPhase("running");
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 402) {
        // Подія ще в дорозі — це очікування, а не відмова.
        setPhase("waiting");
        return;
      }
      setProblem(failure instanceof ApiError ? failure.message : "");
    }
  }, [form.url, purchaseId]);

  // ── 4. Хід перевірок ────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== "running" || !auditId) return;
    let alive = true;
    const tick = async () => {
      try {
        const view = await readGuestAudit(auditId, locale);
        if (!alive) return;
        const status = String((view as { status?: string }).status ?? "completed");
        setAuditStatus(status);
        const finished = status === "completed" || status === "partial";
        if (status === "failed") {
          setPhase("failed");
          return;
        }
        if (!finished) return;

        // Присутність питаємо один раз і тими фактами, які людина вже
        // назвала: другий раз про те саме — це не турбота, а недовіра.
        if (!presenceAsked.current && form.brand.trim() && form.category.trim()) {
          presenceAsked.current = true;
          try {
            const run = await startGuestPresence(auditId, {
              brand: form.brand.trim(),
              brand_aliases: form.aliases
                .split(",")
                .map((alias) => alias.trim())
                .filter(Boolean),
              category: form.category.trim(),
              location: form.location.trim() || null,
              language: form.language,
              idempotency_key: `order-${purchaseId}`,
            });
            setPresenceId(run.id);
            setPresenceStatus(run.status);
            return;
          } catch {
            // Присутність не стартувала — звіт сайту від цього не зникає.
            setPresenceId("");
          }
        }
        if (presenceId) {
          const run = await readGuestPresenceRun(presenceId);
          if (!alive) return;
          setPresenceStatus(run.status);
          if (run.status !== "completed" && run.status !== "failed") return;
        }
        if (!linkToken) {
          const link = await issueReportLink(auditId, locale);
          if (!alive) return;
          setLinkToken(link.token);
        }
        setPhase("ready");
      } catch {
        // Мережа моргнула — наступний оберт спробує знову.
      }
    };
    void tick();
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [phase, auditId, presenceId, linkToken, locale, form, purchaseId]);

  return (
    /* Вміст цих екранів короткий, і притиснутий до верху він лишає під
       собою порожній екран. `justify-center` тримає його посередині, а
       довга форма просто росте вниз і прокручується, як і всюди. */
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center px-6 py-12">
      <header className="mb-8 flex justify-center">
        {/* Дорога назад на сайт: знак і є цим виходом на всіх
            гостьових екранах, і цей не має бути винятком. Головна —
            МОВОЮ сторінки. */}
        <Link href={publicHomeHref(locale)} aria-label="Crawldy">
          <LogoStacked />
        </Link>
      </header>
      {/* Заголовок сторінки стоїть лише там, де він щось називає: форма
          й готові звіти. У станів «оплата не пройшла», «підтвердження
          немає», «забагато спроб» є власний заголовок, і «Ваша
          перевірка» над ним лише повторював слово (рішення власника
          2026-09-07). */}
      {phase === "form" || phase === "running" || phase === "ready" ? (
        <h1 className="mb-6 text-center text-xl font-semibold text-primary">
          {t("order.title")}
        </h1>
      ) : null}

      {phase === "opening" || phase === "waiting" ? (
        <Panel>
          <div className="flex flex-col items-center gap-3 text-center">
            <Spinner className="size-5" />
            <p className="text-sm text-secondary">
              {t(phase === "opening" ? "order.opening" : "order.waiting")}
            </p>
          </div>
        </Panel>
      ) : null}

      {phase === "notPaid" || phase === "unknown" || phase === "throttled" ? (
        <Panel>
          <div className="flex flex-col items-center gap-1 text-center">
            {/* Заголовок першого рівня: на цьому екрані він єдиний. */}
            <h1 className="text-base font-semibold text-foreground">
              {t(TITLES[phase])}
            </h1>
            {/* «Кошти не списано» каже лише той стан, якому провайдер це
                підтвердив. Коли він мовчить — текст інший, а коли
                відмовили ми самі — третій. */}
            <p className="text-sm text-secondary">{t(LEADS[phase])}</p>
            {/* Кнопки при переповненому ліміті немає навмисно: вона
                привела б у ту саму відмову. */}
            {phase === "throttled" ? null : (
              <div className="mt-3">
                <Button onClick={() => void beginCheckout()}>{t("order.retry")}</Button>
              </div>
            )}
          </div>
        </Panel>
      ) : null}

      {phase === "lost" ? (
        <Panel>
          <p className="text-center text-sm text-secondary">{t("order.lost")}</p>
        </Panel>
      ) : null}

      {phase === "form" ? (
        <Panel>
          <p className="text-sm text-secondary">{t("order.formLead")}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={t("order.url")}>
              <Input
                value={form.url}
                placeholder="https://example.com"
                onChange={(e) => setForm({ ...form, url: e.target.value })}
              />
            </Field>
            <Field label={t("free.presence.brand")}>
              <Input
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              />
            </Field>
            <Field label={t("free.presence.category")}>
              <Input
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              />
            </Field>
            <Field
              label={t("free.presence.aliases")}
              hint={t("free.presence.aliasesHint")}
            >
              <Input
                value={form.aliases}
                onChange={(e) => setForm({ ...form, aliases: e.target.value })}
              />
            </Field>
            <Field label={t("free.presence.location")}>
              <Input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </Field>
            <Field label={t("order.language")}>
              <Select
                value={form.language}
                onChange={(e) => {
                  languageTouched.current = true;
                  setForm({ ...form, language: e.target.value });
                }}
              >
                {PROMPT_LANGUAGES.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {problem ? (
            <div className="mt-4">
              <Alert tone="danger">{problem}</Alert>
            </div>
          ) : null}
          <div className="mt-4">
            <Button disabled={!form.url.trim()} onClick={() => void launch()}>
              {t("order.run")}
            </Button>
          </div>
        </Panel>
      ) : null}

      {phase === "running" ? (
        <Panel>
          <Step
            label={t("order.runningAudit")}
            done={auditStatus === "completed" || auditStatus === "partial"}
          />
          {presenceId ? (
            <Step
              label={t("order.runningPresence")}
              done={presenceStatus === "completed"}
            />
          ) : null}
        </Panel>
      ) : null}

      {phase === "failed" ? (
        <Alert tone="danger">
          <span className="block text-center">{t("order.auditFailed")}</span>
        </Alert>
      ) : null}

      {phase === "ready" ? (
        <Panel>
          <p className="text-center text-sm text-primary">
            {t(presenceId ? "order.done" : "order.doneAudit")}
          </p>
          <p className="mt-4 text-center text-xs uppercase tracking-wide text-muted">
            {t("order.downloads")}
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {linkToken
              ? [
                  { format: "docx-general", label: t("result.downloadGeneral") },
                  { format: "docx-technical", label: t("result.downloadTechnical") },
                ].map((item) => (
                  <a
                    key={item.format}
                    href={`/r/${linkToken}?format=${item.format}`}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-secondary transition-colors duration-fast hover:bg-surface-sunken hover:text-primary"
                  >
                    <Icon name="download" className="size-4" />
                    {item.label}
                  </a>
                ))
              : null}
            {presenceId
              ? ([
                  { kind: "general" as const, label: t("free.presence.general") },
                  { kind: "technical" as const, label: t("free.presence.technical") },
                ]).map((item) => (
                  <Button
                    key={item.kind}
                    variant="quiet"
                    onClick={() =>
                      void downloadGuestPresenceReport(presenceId, locale, item.kind).catch(
                        () => undefined,
                      )
                    }
                  >
                    {item.label}
                  </Button>
                ))
              : null}
          </div>
          {linkToken ? (
            <div className="mt-4 text-center">
              <a
                href={`/report/${linkToken}`}
                className="text-sm text-accent-text hover:text-primary"
              >
                {t("order.openReport")}
              </a>
            </div>
          ) : null}
        </Panel>
      ) : null}
    </main>
  );
}

function Step({ label, done }: { label: string; done: boolean }) {
  return (
    <div className="flex items-center justify-center gap-3 py-2 text-sm text-secondary">
      {done ? (
        <Icon name="check" className="size-4 text-success" />
      ) : (
        <Spinner className="size-4" />
      )}
      <span>{label}</span>
    </div>
  );
}
