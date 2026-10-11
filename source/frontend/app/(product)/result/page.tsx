"use client";

/**
 * Безкоштовний результат анонімного аудиту — і платний стан після оплати.
 *
 * Ієрархія екрана — продуктове рішення, а не верстка: загальний бал,
 * обсяг проблеми (скільки й якої ваги), покриття, три головні проблеми
 * мовою наслідку, заклик до повного аудиту. Шести вимірів тут немає
 * навмисно: це діагностика, і вона за межею оплати. Сервер її й не
 * віддає — сторінка не змогла б показати виміри навіть помилково.
 *
 * ## Це не дашборд
 *
 * Безкоштовний результат — не «менший звіт», а відповідь власнику на
 * питання «чи в мене все гаразд і наскільки ні». Тому тут немає
 * таблиць, вкладок і решіток метрик: одна колонка, спокійний ритм,
 * рівно пʼять блоків.
 *
 * ## Порожній бал — не нуль
 *
 * Коли прочитаного замало, бала немає, і сторінка каже саме це.
 * Правило те саме, що в усьому продукті: краще чесне «не виміряли»,
 * ніж вигадане число.
 *
 * ## Три входи, і жоден не мовчазний
 *
 * `/result` — форма адреси: відкриває гостьову сесію й ставить аудит.
 * `/result?audit=<id>` — живий результат із бекенда.
 * `/result?demo=1` — макет, і лише за явним проханням.
 *
 * Макет колись стояв тут дефолтом, і це найнебезпечніша форма
 * заглушки: екран виглядає робочим, поки хтось не спробує заплатити.
 * Тепер він за окремим параметром, тож продакшн не може мовчки
 * показати вигадані числа.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { AuditResultView, hostOf } from "../../components/AuditResultView";
import { GuestPresence } from "../../components/GuestPresence";
import { AccountCta, GuestDownloads } from "../../components/GuestReport";
import { LogoStacked } from "../../components/Brand";
import { PaymentPanel } from "../../components/PaymentPanel";
import { Alert, Badge, Button, Panel, Spinner } from "../../components/primitives";
import { Score } from "../../components/Score";
import {
  MOCK_FREE_RESULT,
  type FreeAuditResult,
} from "../../lib/free-result";
import {
  auditIsRunning,
  ensureGuestSession,
  isShortView,
  issueReportLink,
  readGuestAudit,
  readGuestFull,
  recallLocale,
  rememberLocale,
  startGuestAudit,
  type StartedAudit,
} from "../../lib/guest-payment";
import { INITIAL_FLOW } from "../../lib/payment-flow";
import { mockResult } from "../../lib/mock-result";
import { normalizeSiteUrl } from "../../lib/site-url";
import { problemKey } from "../../lib/problem";
import type { AuditResult, Locale } from "../../lib/contracts";
import { LocaleProvider, useLocale } from "../../lib/locale";
import { asSiteLocale, publicHomeHref } from "../../lib/i18n";
import { Running, TechnicalScreen } from "./screens";

export default function FreeResultPage() {
  return (
    <Suspense fallback={<Centered><Spinner className="size-6" /></Centered>}>
      <LocalizedFreeResult />
    </Suspense>
  );
}

/**
 * Мова гостьового результату приходить з адреси (`?lang=uk`), яку
 * ставлять кнопки локалізованих сторінок сайту. Раніше тут стояло
 * зашите "en", і український відвідувач з української головної
 * потрапляв на англійський екран. Невідоме значення падає на
 * англійську — фолбек той самий, що в усьому кабінеті.
 *
 * Мов тут ШІСТЬ, а не дві. Публічний сайт написаний шістьма, і кнопка
 * «перевірити сайт» на іспанській сторінці веде рівно сюди — тобто до
 * цієї правки іспанець із іспанської сторінки отримував англійський
 * результат, хоча каталог бекенда іспанську має. Це була наша межа, а
 * не межа даних.
 *
 * Мова ще й запамʼятовується на сесію: повернення з каси Paddle
 * (`?audit=…&processing=1`) параметра мови не несе, і без згадки
 * українець, який щойно заплатив, бачив би англійський екран.
 */
function LocalizedFreeResult() {
  const params = useSearchParams();
  const locale: Locale =
    asSiteLocale(params.get("lang")) ?? asSiteLocale(recallLocale()) ?? "en";
  useEffect(() => {
    rememberLocale(locale);
  }, [locale]);
  return (
    <LocaleProvider locale={locale}>
      <FreeResult />
    </LocaleProvider>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-screen items-center justify-center">{children}</div>;
}

function FreeResult() {
  const params = useSearchParams();
  const auditId = params.get("audit");

  if (params.get("demo") === "1") return <DemoResult />;
  // `?url=` ставить форма героя головної: та сама форма, той самий
  // шлях — адреса вже введена, лишилося натиснути ту саму кнопку тут
  // або дозволити їй натиснутись самій.
  if (!auditId) return <StartAudit initialUrl={params.get("url") ?? ""} />;
  return (
    <LiveResult
      auditId={auditId}
      returningFromCheckout={params.get("processing") === "1"}
    />
  );
}

// ── вхід: адреса сайту ─────────────────────────────────────────────────────

/**
 * Єдине питання, яке ми ставимо до аудиту, — адреса.
 *
 * Ні пошти, ні акаунта, ні згоди на розсилку: людина ще нічого від нас
 * не отримала, і просити щось до цього означає торгувати обіцянкою.
 * Заголовка й пояснення немає навмисно: поле і кнопка кажуть усе самі.
 *
 * Адресу людина пише як звикла: `smartkp.com.ua` без протоколу — теж
 * валідний вхід, він нормалізується перед запуском. Валідація
 * контрольована застосунком (`noValidate`): браузерна підказка
 * приходить мовою браузера, а не мовою сторінки.
 */
function StartAudit({ initialUrl = "" }: { initialUrl?: string }) {
  const { t, locale } = useLocale();
  const [url, setUrl] = useState(initialUrl);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Адресу з героя головної запускаємо одразу: людина вже натиснула
  // «перевірити» там. Рівно раз — помилка знімає прапорець і повертає
  // керування людині, а не заганяє її в цикл автозапусків.
  const [autoStarted, setAutoStarted] = useState(false);

  const start = useCallback(async (raw: string) => {
    const target = normalizeSiteUrl(raw);
    if (target === null) {
      setError("free.invalidUrl");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await ensureGuestSession();
      const started = await startGuestAudit(target);
      // Адреса стає станом: перезавантаження сторінки не має губити
      // аудит, за який людина вже чекає. Мова їде в адресі теж —
      // інакше цей перехід мовчки перемикав би українця на англійську.
      const lang = locale === "en" ? "" : `&lang=${locale}`;
      window.location.assign(`/result?audit=${started.audit_id}${lang}`);
    } catch (problem) {
      // Стан тримає КЛЮЧ каталогу, не сире значення сервера: гість із
      // вичерпаною квотою бачив на екрані «quota.exhausted».
      setError(problemKey(problem));
      setBusy(false);
    }
  }, [locale]);

  useEffect(() => {
    if (initialUrl && !autoStarted) {
      setAutoStarted(true);
      void start(initialUrl.trim());
    }
  }, [initialUrl, autoStarted, start]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    await start(url);
  }

  // Адреса вже прийшла з головної — людина натиснула «перевірити» там,
  // і показувати їй ту саму порожню форму ще раз немає навіщо. Раніше
  // вона блимала долю секунди між головною і станом «читаємо сайт»:
  // форма малювалась, і лише потім ефект запускав аудит. Тепер цей
  // проміжний екран не малюється взагалі — доки помилка не поверне
  // керування людині.
  if (initialUrl && !error) return <Starting />;

  return (
    <TechnicalScreen>
      <form className="mt-6 flex flex-wrap gap-3" onSubmit={submit} noValidate>
        <input
          type="text"
          inputMode="url"
          autoComplete="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="smartkp.com.ua"
          aria-label={t("newAudit.label")}
          aria-invalid={error === "free.invalidUrl" || undefined}
          className="h-12 min-w-0 flex-1 rounded-md border border-border bg-surface px-4 text-base text-foreground outline-none focus:border-accent"
        />
        <Button size="lg" type="submit" loading={busy}>
          {t("free.startCta")}
        </Button>
      </form>
      {error ? (
        <div className="mt-4">
          <Alert tone="danger">{t(error)}</Alert>
        </div>
      ) : null}
    </TechnicalScreen>
  );
}

// ── живий результат ────────────────────────────────────────────────────────

/** Скільки чекати перед наступним питанням про стан аудиту. */
const AUDIT_POLL_MS = 4000;

function LiveResult({
  auditId,
  returningFromCheckout,
}: {
  auditId: string;
  returningFromCheckout: boolean;
}) {
  const { t, locale } = useLocale();
  const [view, setView] = useState<StartedAudit | FreeAuditResult | null>(null);
  const [full, setFull] = useState<AuditResult | null>(null);
  const [linkToken, setLinkToken] = useState("");
  const [error, setError] = useState("");

  // Право читається з сервера — тут і ніде більше. Цей виклик робиться
  // лише після того, як сервер сказав `unlocked`, і повторний відмовний
  // стан його не обходить: 402 просто лишить `full` порожнім.
  const loadPaid = useCallback(async () => {
    try {
      setFull(await readGuestFull(auditId, locale));
      const link = await issueReportLink(auditId, locale);
      setLinkToken(link.token);
    } catch (problem) {
      setError(problemKey(problem));
    }
  }, [auditId, locale]);

  const refresh = useCallback(async () => {
    try {
      const next = await readGuestAudit(auditId, locale);
      setView(next);
      if (next.unlocked) await loadPaid();
      return next;
    } catch (problem) {
      setError(problemKey(problem));
      return null;
    }
  }, [auditId, locale, loadPaid]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Поки аудит виконується, питаємо далі. Готовий аудит опитувати
  // немає сенсу: він більше не змінюється сам.
  useEffect(() => {
    if (view === null || !auditIsRunning(view.status)) return;
    const timer = window.setTimeout(() => void refresh(), AUDIT_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [view, refresh]);

  if (error && view === null) {
    return (
      <Centered>
        <div className="max-w-md px-6">
          <Alert tone="danger">{t(error)}</Alert>
        </div>
      </Centered>
    );
  }
  if (view === null) return <Centered><Spinner className="size-6" /></Centered>;
  if (!isShortView(view)) return <Running started={view} />;

  if (view.unlocked && full !== null) {
    return <PaidReport result={full} linkToken={linkToken} />;
  }

  return (
    <LockedReport
      result={view}
      returningFromCheckout={returningFromCheckout}
      onUnlocked={() => void refresh()}
    />
  );
}

/** Аудит уже поставлено, сторінка ще не переїхала на його адресу. */
function Starting() {
  const { t } = useLocale();
  return (
    <TechnicalScreen>
      <Panel>
        <div className="flex items-center gap-3">
          <Spinner className="size-5" />
          <div>
            <h1 className="text-base font-semibold text-foreground">
              {t("free.auditRunningTitle")}
            </h1>
            <p className="mt-0.5 text-sm text-muted">
              {t("free.auditRunningLead")}
            </p>
          </div>
        </div>
      </Panel>
    </TechnicalScreen>
  );
}

/**
 * Оплачений стан — той самий повний звіт, що в кабінеті. Не «версія для
 * гостя»: подання одне, різниться лише доступ і завантаження.
 */
function PaidReport({
  result,
  linkToken,
}: {
  result: AuditResult;
  linkToken: string;
}) {
  const { t } = useLocale();
  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-6 py-12">
      {/* Та сама шапка, що й до оплати: оплата не робить це іншим
          документом, і переїзд знака вбік читався б як інша сторінка. */}
      <ResultHeader origin={result.origin} />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">{t("free.unlockedLead")}</p>
        {linkToken ? <GuestDownloads token={linkToken} /> : null}
      </div>
      <AuditResultView result={result} />
      {/* Друга половина покупки: одиниця присутності, яку досі не було як
          витратити з гостьового екрана. Блок сам зникає, коли покупка
          присутності не містить. */}
      <GuestPresence auditId={result.audit_id} />
      <AccountCta />
    </main>
  );
}

function LockedReport({
  result,
  returningFromCheckout,
  onUnlocked,
}: {
  result: FreeAuditResult;
  returningFromCheckout: boolean;
  onUnlocked: () => void;
}) {
  const { t } = useLocale();
  return (
    <main className="mx-auto min-h-screen w-full max-w-2xl px-6 py-12">
      <ResultHeader origin={result.origin} />

      <OverallScore result={result} />
      <IssueTotals result={result} />
      <CoverageSummary result={result} />
      <TopProblems result={result} />
      <PaymentPanel
        auditId={result.audit_id}
        initial={
          returningFromCheckout ? { ...INITIAL_FLOW, phase: "processing" } : undefined
        }
        onUnlocked={onUnlocked}
      />

    </main>
  );
}

// ── макет ──────────────────────────────────────────────────────────────────

/**
 * Макет за явним `?demo=1`. Існує, щоб екран можна було дивитися й
 * знімати без піднятого стека, — і саме тому він ніколи не вмикається
 * сам.
 */
function DemoResult() {
  const { t, locale } = useLocale();
  const params = useSearchParams();
  const unlocked = params.get("unlocked") === "1";
  const result: FreeAuditResult = { ...MOCK_FREE_RESULT, unlocked };

  // Зразок підписаний як зразок — на екрані, а не лише в коді: адресу
  // з `?demo=1` можна переслати, і читач мусить бачити, що це формат,
  // а не вимірювання.
  const banner = (
    <p className="mb-6 rounded-md border border-border bg-surface-sunken px-4 py-2 text-center text-xs text-muted">
      {t("free.sampleBanner")}
    </p>
  );

  if (unlocked) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 pt-6">
        {banner}
        <PaidReport result={mockResult(result.audit_id, locale)} linkToken="" />
      </div>
    );
  }
  return (
    <main className="mx-auto min-h-screen w-full max-w-2xl px-6 py-12">
      {banner}
      <ResultHeader origin={result.origin} />
      <OverallScore result={result} />
      <IssueTotals result={result} />
      <CoverageSummary result={result} />
      <TopProblems result={result} />
    </main>
  );
}

/**
 * Шапка сторінки результату: знак по центру, адреса сайту під ним.
 *
 * Адреса — не підпис до знака, а предмет усього документа: далі йде
 * бал, кількість проблем і покриття, і всі вони про неї. Поки вона
 * стояла дрібним сірим написом у правому куті, читач мусив шукати
 * очима, про який саме сайт звіт. Тому вона під знаком і тим самим
 * розміром, що заголовки панелей.
 */
function ResultHeader({ origin }: { origin: string }) {
  const { locale } = useLocale();
  return (
    <header className="mb-10 flex flex-col items-center gap-3">
      {/* Дорога назад. З результату її не було взагалі: людина
          приходила з головної й лишалася без виходу, тоді як на решті
          сторінок саме знак і є цим виходом. Головна — МОВОЮ сторінки:
          зашите «/» мовчки перемикало б українця на англійську. */}
      <Link href={publicHomeHref(locale)} aria-label="Crawldy">
        <LogoStacked />
      </Link>
      {/* `h1` саме тут: адреса — назва цього документа, і до неї на
          сторінці не було жодного заголовка першого рівня. */}
      <h1 className="text-base font-medium text-foreground">{hostOf(origin)}</h1>
    </header>
  );
}

/** Загальний бал — або чесне «не виміряли». */
function OverallScore({ result }: { result: FreeAuditResult }) {
  const { t } = useLocale();
  return (
    <section className="mb-8 text-center">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
        {t("free.overall")}
      </p>
      <div className="flex justify-center">
        <Score value={result.overall_score} size="lg" />
      </div>
      {result.overall_score === null ? (
        <p className="mx-auto mt-3 max-w-sm text-sm text-muted">
          {t("free.noScore")}
        </p>
      ) : null}
    </section>
  );
}

/** Скільки проблем і якої ваги. Розподіл, а не діагноз. */
function IssueTotals({ result }: { result: FreeAuditResult }) {
  const { t, n } = useLocale();
  const rows: Array<{ key: "high" | "medium" | "low"; tone: "danger" | "warning" | "neutral" }> = [
    { key: "high", tone: "danger" },
    { key: "medium", tone: "warning" },
    { key: "low", tone: "neutral" },
  ];
  return (
    <Panel className="mb-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-medium text-foreground">
          {n("free.issuesFound", result.issues_total)}
        </h2>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-border bg-border text-center">
        {rows.map(({ key, tone }) => (
          <div key={key} className="bg-surface px-3 py-3">
            {/* Підпис смуги — не декоративна позначка, а слово, за яким
                читають число під ним. На 320px `text-xs` давав 13px, і
                автоматичний вимір кегля це спіймав: пояснювальний текст
                на телефоні починається з 14px. `text-sm` дає рівно 14px
                під 480px і лишає 13px на десктопі, де відстань інша. */}
            <dt className="text-sm text-muted">{t(`free.severity.${key}`)}</dt>
            <dd
              className={
                "mt-1 text-lg font-semibold tabular-nums " +
                (result.severity[key] > 0 && tone === "danger"
                  ? "text-danger"
                  : "text-foreground")
              }
            >
              {result.severity[key]}
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

/** Покриття крупним планом: чи вистачило прочитаного. */
/**
 * Покриття однією фразою про те, що ми справді зробили.
 *
 * Тут стояли два рядки одночасно: «Сайт відповідав повністю» і
 * «Прочитано 10 із 11 сторінок». Перший заперечував друге, а разом вони
 * не казали головного — скільки з знайденого перевірено. Тепер число і
 * є твердженням, а рівень покриття зник: він переказував ті самі два
 * числа словами.
 *
 * Другий рядок зʼявляється лише коли адреси справді не відповіли.
 * Різниця `known − read` для цього не годиться: у знаменнику є й
 * сторінки, до яких краул не дійшов за власним бюджетом, і назвати їх
 * невдачами означало б звинуватити сайт у нашій межі.
 */
function CoverageSummary({ result }: { result: FreeAuditResult }) {
  const { t, n } = useLocale();
  const { pages_read, pages_known } = result.coverage;
  if (pages_read === null || pages_known === null) return null;

  // Скільки знайдених адрес лишилось непрочитаними. Це НЕ `pages_failed`:
  // та величина вужча — адреси, що віддали помилку. Питання, яке ставить
  // читач, дивлячись на «10 із 52», інше: а решта сорок дві?
  //
  // `Math.max` — не косметика: знаменник обмежений бюджетом краулу, і
  // теоретично може відстати від лічильника. Відʼємне число тут гірше
  // за відсутнє.
  const unchecked = Math.max(0, pages_known - pages_read);

  return (
    <Panel className="mb-4">
      <h2 className="text-sm font-medium text-foreground">{t("free.coverage")}</h2>
      {/* Форма числівника береться зі ЗНАМЕННИКА: іменник узгоджується
          з кількістю знайдених сторінок, а не прочитаних. */}
      <p className="mt-1 text-sm text-foreground">
        {n("free.coverage.checked", pages_known, {
          read: pages_read,
          known: pages_known,
        })}
      </p>
      {unchecked > 0 ? (
        <p className="mt-1 text-sm text-muted">
          {n("free.coverage.unchecked", unchecked)}
        </p>
      ) : null}
    </Panel>
  );
}

/**
 * Три головні проблеми — мовою наслідку, з ціною кожної в балах.
 *
 * Бейджів «Терміново» / «Важливо» тут більше немає. Вони були другим
 * словником про серйозність поруч із лічильниками зверху, і читались як
 * суперечність: «Терміново» стояло нижче за два «Важливо», бо порядок
 * брався не зі смуги. Тепер видно число, і воно пояснює порядок само.
 *
 * Число — справжня ізольована дельта з рушія скорингу, порахована на
 * бекенді. Сумувати три такі не можна: кожна міряна окремо проти того
 * самого базового бала, і стеля на `issue_key` робить ефект нелінійним.
 * Тому спільного «покращите на N» тут немає й не буде.
 */
function TopProblems({ result }: { result: FreeAuditResult }) {
  const { t } = useLocale();
  if (result.problems.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-base font-medium text-foreground">
        {t("free.topProblems")}
      </h2>
      <ul className="space-y-3">
        {result.problems.map((problem) => (
          <li key={problem.problem}>
            <Panel>
              <p className="font-medium text-foreground">{problem.problem}</p>
              {problem.why ? (
                <p className="mt-1 text-sm text-muted">{problem.why}</p>
              ) : null}
              {/* «+0 до бала» не показуємо ніколи: нуль означає або
                  приріст менший за одиницю після округлення, або
                  відсутній загальний бал, — і жодне з двох не «марно». */}
              {problem.floored || problem.impact_points === 0 ? null : (
                <p className="mt-3 text-sm tabular-nums text-secondary">
                  {t("free.scoreImpact", {
                    points: `−${problem.impact_points}`,
                  })}
                </p>
              )}
            </Panel>
          </li>
        ))}
      </ul>
    </section>
  );
}
