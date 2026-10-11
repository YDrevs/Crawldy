"use client";

/**
 * Тариф і використання.
 *
 * ## Один компактний підсумок замість чотирьох панелей
 *
 * Уся верхня частина — ОДИН контейнер зі стислими рядками: стан
 * тарифу, залишок аналізів періоду, куплені аналізи (з позначкою «не
 * згоряє» — і жодних пояснювальних абзаців), перевірки Actual AI
 * Presence, кінець періоду — лише коли період існує. Пояснення «що
 * списується першим» тут немає: це механіка обліку, а не мова клієнта.
 *
 * ## Безкоштовний стан — чесний
 *
 * Акаунт без покупки не має «тарифу з 1 аудитом»: безкоштовних повних
 * аудитів не існує (рішення власника 2026-09-03), а превʼю живе своїм
 * необмеженим шляхом і тут не рахується. Тому замість назви тарифу —
 * «активного тарифу немає», і жодної смуги «0 з 0».
 *
 * ## Підписка — справжня каса
 *
 * «Підписатися» відкриває касу підписки провайдера
 * (POST /v1/plans/{code}/checkout → накладна каса Paddle). Право видає
 * лише перевірена подія: після оплати сторінка перечитує акаунт і
 * бачить стан таким, яким його назвав сервер. `?subscribe=` продовжує
 * намір, збережений через вхід.
 *
 * ## Екран нічого не рахує
 *
 * Залишки, дати й стан приходять готовими з `/v1/account`; пропозиції
 * і тарифи — з живого каталогу тією ж мовою.
 */

import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { PageHeader } from "../../../components/AppShell";
import {
  Alert,
  Badge,
  Button,
  Panel,
  Spinner,
} from "../../../components/primitives";
import {
  API_URL,
  ApiError,
  getAccount,
  listOffers,
  openBillingPortalSession,
  readPaymentState,
  openOfferCheckout,
  openPlanCheckout,
  readPurchaseState,
} from "../../../lib/api";
import { readCheckoutConfig } from "../../../lib/guest-payment";
import { openPaddleOverlay } from "../../../lib/paddle";
import { useLocale } from "../../../lib/locale";
import { problemKey } from "../../../lib/problem";
import { monthlyToShow } from "../../../lib/pricing";
import type { Account, BillingState, Offer } from "../../../lib/contracts";

/** Стани, які варто пояснити словами, а не лише позначкою. */
const NEEDS_EXPLAINING: BillingState[] = ["past_due", "cancelling"];

/** Тон позначки стану. Проблема має виглядати проблемою. */
const TONE: Record<BillingState, "neutral" | "success" | "warning" | "danger"> = {
  free: "neutral",
  trialing: "neutral",
  active: "success",
  past_due: "danger",
  paused: "warning",
  cancelling: "warning",
  cancelled: "neutral",
};

/** Публічний тариф — рівно ті поля, що потрібні картці й касі. */
interface PublicPlanLite {
  code: string;
  name: string;
  description: string;
  analyses_per_month: number | null;
  analyses_unlimited: boolean;
  presence_checks_per_month: number;
  sort_order: number;
  highlighted: boolean;
  prices: { currency: string; amount_minor: number | null; exponent: number }[];
}

/**
 * Скільки разів питати про долю каси й через яку паузу.
 *
 * Ті самі числа, що на `/buy` і `/checkout`. Довгий бюджет — поки вікно
 * відкрите: людина ще вводить картку, і висновок під нею був би
 * поспішним. Короткий — коли вікно вже закрито: події про закрите без
 * оплати вікно не буде ніколи.
 */
const POLL_MS = 4000;
const OPEN_ATTEMPTS = 30;
const CLOSED_ATTEMPTS = 4;
/** Після цього питаємо провайдера навіть при відкритій касі. */
const PATIENT_TICKS = 4;

/**
 * Що сказати людині, яка відкрила касу.
 *
 * Відповідей три, і кажемо ми лише одну з них. Оплата дійшла — казати
 * нема чого, числа на екрані вже інші. Провайдер підтвердив, що грошей
 * не брав, — теж нема чого: людина сама щойно закрила вікно, і
 * повідомлення про це переказує їй її ж дію (рішення власника
 * 2026-09-07). Лишається єдиний випадок, у якому мовчати не можна:
 * провайдер мовчить, тобто гроші могли піти, а ми цього не бачимо.
 *
 * Сторінки `/buy` і `/checkout` поводяться інакше, і це не
 * непослідовність: там оплата — єдина мета екрана, і після закритої
 * каси людина лишається ні з чим, якщо не сказати їй, що сталося, і не
 * дати кнопку. Тут вона лишається в робочому кабінеті.
 *
 * Опитування починається разом із касою, а не з її закриття. Подія
 * `checkout.closed` може не дійти взагалі — людина пішла на іншу
 * вкладку, провайдер її не надіслав, — і екран, що чекає тільки на
 * неї, мовчить так само, як мовчав до всіх цих правок. Закриття лише
 * скорочує очікування, бо після нього чекати справді нема на що.
 */
async function settleTill({
  purchaseId,
  closed,
  refresh,
}: {
  /** Пакет має власний рядок покупки; підписка — ні (її створює подія). */
  purchaseId: string | null;
  closed: { current: boolean };
  refresh: () => Promise<Account | null>;
}): Promise<string | null> {
  for (let attempt = 1; ; attempt += 1) {
    await new Promise((wake) => setTimeout(wake, POLL_MS));
    const account = await refresh();
    if (purchaseId) {
      try {
        const ask = closed.current || attempt > PATIENT_TICKS;
        const state = await readPurchaseState(purchaseId, ask);
        // Оплата дійшла: баланс уже оновлено, і числа кажуть це краще
        // за будь-яке повідомлення.
        if (state.state === "paid") return null;
        // «Кошти не списано» — правда, але зайва: це переказ дії, яку
        // людина щойно зробила сама.
        if (state.charged === false) return null;
      } catch {
        // Мережа чи провайдер мовчать — це не «не платив».
      }
    } else if (
      account &&
      account.billing_state !== "free" &&
      account.billing_state !== "cancelled"
    ) {
      // Підписка зʼявилась: її створила перевірена подія, і кабінет її
      // уже показує.
      return null;
    }
    const enough = closed.current ? CLOSED_ATTEMPTS : OPEN_ATTEMPTS;
    if (attempt >= enough) return "checkout.unknownLead";
  }
}

export default function PlanPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center text-muted">
          <Spinner className="size-5" />
        </div>
      }
    >
      <PlanScreen />
    </Suspense>
  );
}

function PlanScreen() {
  const { t, d, n, locale } = useLocale();
  const [account, setAccount] = useState<Account | null>(null);
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async (): Promise<Account | null> => {
    try {
      const fresh = await getAccount(locale);
      setAccount(fresh);
      return fresh;
    } catch {
      setFailed(true);
      return null;
    }
  }, [locale]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Оплата, яку провайдер уже отримав, а події ще немає. Прав це не
  // видає — лише пояснює порожній кабінет тому, хто щойно заплатив.
  const [awaiting, setAwaiting] = useState(false);
  useEffect(() => {
    let alive = true;
    void readPaymentState()
      .then((state) => {
        if (alive) setAwaiting(state.awaiting_event);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [account]);

  /** Каса закрилась. Спільний для обох кас цієї сторінки. */
  const closed = useRef(false);

  const startSubscribe = useCallback(
    async (planCode: string) => {
      setNotice(null);
      try {
        const opened = await openPlanCheckout(planCode);
        const config = await readCheckoutConfig();
        const overlaid = await openPaddleOverlay({
          clientToken: config.client_token,
          environment: config.environment,
          transactionRef: opened.provider_ref,
          successUrl: `${window.location.origin}/app/plan`,
          // Закриття лише скорочує очікування — саме опитування вже йде.
          onClosed: () => {
            closed.current = true;
          },
        });
        closed.current = false;
        void settleTill({ purchaseId: null, closed, refresh: reload }).then(setNotice);
        if (!overlaid) window.location.assign(opened.url);
      } catch (problem) {
        setNotice(
          problemKey(problem, {
            409: "plan.alreadySubscribed",
            404: "billing.checkoutUnavailable",
          }),
        );
      }
    },
    [reload],
  );

  if (failed) {
    return (
      <>
        <PageHeader title={t("plan.title")} />
        <Panel>
          <p className="text-secondary">{t("state.offline")}</p>
        </Panel>
      </>
    );
  }

  if (account === null) {
    return (
      <div className="flex min-h-64 items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const state = account.billing_state;
  const openPortal = () =>
    void openBillingPortalSession()
      .then((r) => window.open(r.url, "_blank", "noopener"))
      // Мовчазна відмова читалась як зламана кнопка: платіжного профілю
      // ще немає, поки провайдер не підтвердив першу оплату, і сказати
      // це дешевше, ніж лишити людину гадати.
      .catch((problem) =>
        setNotice(problemKey(problem, { 404: "billing.portalEmpty" })),
      );

  return (
    <>
      <PageHeader
        title={t("plan.title")}
        action={
          <Button variant="ghost" onClick={openPortal}>
            {t("billing.portal")}
          </Button>
        }
      />

      {NEEDS_EXPLAINING.includes(state) ? (
        <div className="mb-6">
          <Alert tone={state === "past_due" ? "danger" : "warning"}>
            {state === "past_due"
              ? t("plan.pastDueWhy")
              : t("plan.cancellingWhy", { date: d(account.usage.period_end) })}
          </Alert>
        </div>
      ) : null}

      {notice ? (
        <div className="mb-6">
          <Alert tone="info">{t(notice)}</Alert>
        </div>
      ) : null}

      {awaiting ? (
        <div className="mb-6">
          <Alert tone="info">{t("billing.awaitingEvent")}</Alert>
        </div>
      ) : null}

      <UsageSummary account={account} />

      <BuyMore
        onSubscribe={startSubscribe}
        onSettled={setNotice}
        refresh={reload}
        // Намір «купити пакет», збережений через вхід зі сторінки цін:
        // та сама дорога, що й `?subscribe=`, лише для разової покупки.
        // Незавершена підписка вже є — друга картка Monthly поруч із нею
        // була б запрошенням до подвійного наділу. Single і Pack
        // лишаються: вони додають окремо куплені перевірки.
        hasSubscription={
          account.billing_state !== "free" &&
          account.billing_state !== "cancelled"
        }
      />
    </>
  );
}

/**
 * Увесь стан використання — один контейнер зі стислими рядками.
 *
 * Порожня велика панель заради «немає» тут не зʼявляється: нуль — це
 * значення рядка, а не привід для окремої картки.
 */
function UsageSummary({ account }: { account: Account }) {
  const { t, d, n } = useLocale();
  const usage = account.usage;
  const free = account.billing_state === "free" || account.billing_state === "cancelled";
  const unlimited = usage.audits_limit === null;
  // Рядок аналізів періоду існує лише там, де існує сам наділ: тариф
  // із нульовим обсягом — це не «0 з 0», а відсутність рядка.
  const hasAllowance = !free && (unlimited || (usage.audits_limit ?? 0) > 0);
  // Присутність рахується двома різними одиницями, і зводити їх в одне
  // число не можна: місячний наділ згорає з періодом, куплена одиниця —
  // ні. Поки рядок був один, власник пакета не бачив, скільки з його
  // числа переживе кінець місяця.
  const presencePeriod = !free && (usage.presence_limit ?? 0) > 0;

  return (
    <Panel data-testid="usage-summary">
      <dl className="flex flex-col">
        <SummaryRow
          label={t("plan.row.plan")}
          value={
            <span className="inline-flex items-center gap-2">
              <span>{free ? t("plan.none") : account.plan.name}</span>
              {free ? null : (
                <Badge tone={TONE[account.billing_state]}>
                  {t(`plan.state.${account.billing_state}`)}
                </Badge>
              )}
            </span>
          }
        />
        {hasAllowance ? (
          <SummaryRow
            label={t("plan.row.analyses")}
            value={
              unlimited
                ? t("plan.valueUnlimited")
                : t("plan.value.ofLimit", {
                    left: usage.audits_remaining ?? 0,
                    limit: usage.audits_limit ?? 0,
                  })
            }
          />
        ) : null}
        <SummaryRow
          label={t("plan.row.purchased")}
          value={<span className="tabular-nums">{usage.one_off_available}</span>}
        />
        {presencePeriod ? (
          <SummaryRow
            label={t("plan.row.presencePeriod")}
            value={t("plan.value.ofLimit", {
              left: usage.presence_remaining ?? 0,
              limit: usage.presence_limit ?? 0,
            })}
          />
        ) : null}
        <SummaryRow
          label={
            presencePeriod
              ? t("plan.row.presencePurchased")
              : t("plan.row.presence")
          }
          value={
            <span className="tabular-nums">
              {usage.presence_credits_available}
            </span>
          }
        />
        {hasAllowance ? (
          <SummaryRow
            label={t("plan.row.periodEnds")}
            value={d(usage.period_end)}
          />
        ) : null}
      </dl>
      {/* Куплене живе довше за період, і це головне, чого не видно з
          самого числа: власник пакета інакше читає його як місячний
          наділ, що згорить. */}
      {usage.one_off_available > 0 || usage.presence_credits_available > 0 ? (
        <p className="mt-3 text-xs text-muted">{t("plan.noExpiry")}</p>
      ) : null}
    </Panel>
  );
}

function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2.5 last:border-b-0">
      <dt className="text-sm text-secondary">{label}</dt>
      <dd className="text-sm text-primary">{value}</dd>
    </div>
  );
}

/**
 * Докупити: та сама комерційна мова й ієрархія карток, що на сторінці
 * цін — пропозиції з живого каталогу плюс місячний тариф зі справжньою
 * касою підписки. Переліків можливостей немає: продукт один.
 */
function BuyMore({
  onSubscribe,
  onSettled,
  refresh,
  hasSubscription,
}: {
  onSubscribe: (code: string) => void;
  /** Що сказати після закритої каси — вирішує сторінка, показує теж вона. */
  onSettled: (notice: string | null) => void;
  refresh: () => Promise<Account | null>;
  hasSubscription: boolean;
}) {
  const { t, n, locale } = useLocale();
  const [offers, setOffers] = useState<Offer[] | null>(null);
  const [plans, setPlans] = useState<PublicPlanLite[] | null>(null);
  const [promo, setPromo] = useState("");
  const [error, setError] = useState<string | null>(null);
  /** Каса пакета закрилась: після цього чекати довго нема на що. */
  const closed = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [offerRows, plansRes] = await Promise.all([
          listOffers(locale),
          fetch(`${API_URL}/v1/plans?lang=${locale}`, { cache: "no-store" }),
        ]);
        const plansBody = plansRes.ok
          ? ((await plansRes.json()) as { plans: PublicPlanLite[] })
          : { plans: [] };
        if (cancelled) return;
        setOffers(offerRows);
        setPlans(plansBody.plans ?? []);
      } catch {
        if (!cancelled) {
          setOffers([]);
          setPlans([]);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  // Чинному підписнику Monthly не пропонується взагалі: зміна тарифу —
  // окремий майбутній потік, а не друга каса поруч із першою.
  const monthly = hasSubscription ? null : monthlyToShow(plans ?? []);

  const buy = useCallback(
    async (offer: Offer, promoCode?: string) => {
      setError(null);
      try {
        const opened = await openOfferCheckout(
          offer.code,
          offer.promo_eligible ? promoCode : undefined,
        );
        const config = await readCheckoutConfig();
        // Накладна каса, як у підписки й у гостя. Раніше тут стояв прямий
        // перехід на адресу від провайдера — а Paddle будує її з «default
        // payment link» акаунта, тобто з адреси НАШОЇ сторінки оплати. На
        // локальному стенді це `https://localhost:3000/...`, чого не існує,
        // і кнопка вмирала на ERR_SSL_PROTOCOL_ERROR, поки сусідня кнопка
        // підписки працювала. Перехід лишається запасним шляхом.
        const overlaid = await openPaddleOverlay({
          clientToken: config.client_token,
          environment: config.environment,
          transactionRef: opened.provider_ref,
          successUrl: `${window.location.origin}/app/plan`,
          // Каса закривається і після оплати, і без неї. Поки тут не
          // було відповіді, обидва випадки виглядали однаково: нічого
          // не сталося.
          onClosed: () => {
            closed.current = true;
          },
        });
        if (!overlaid) window.location.assign(opened.url);
        closed.current = false;
        void settleTill({
          purchaseId: opened.purchase_id,
          closed,
          refresh,
        }).then(onSettled);
      } catch (err) {
        // Ключ каталогу, не сирий detail: службовий рядок бекенда — не
        // текст для людини.
        // 404 тут — каса не відкрилась (пропозиція налаштована не для
        // чинного провайдера), а не «аудит недоступний у цьому браузері»,
        // як каже загальний ключ.
        setError(problemKey(err, { 404: "billing.checkoutUnavailable" }));
      }
    },
    [onSettled, refresh],
  );

  // Вихід лише ПІСЛЯ всіх хуків. Поки цей рядок стояв вище за `useCallback`
  // і `useEffect`, перший рендер (каталог ще не завантажено) виходив з
  // двома хуками менше, а другий рендерив їх усі — і React падав із
  // помилкою 310 «rendered more hooks than during the previous render».
  // Видно було саме з наміром з адреси (`?buy=`, `?subscribe=`): без нього
  // ефект покупки не змінював порядку рендерів. Порядок хуків — це
  // інваріант React, а не стиль.
  if ((offers ?? []).length === 0 && monthly === null) return null;

  // Показник валюти йде з бекенда: ділити на сто «бо зазвичай так»
  // означало б показати 4900 єн як 49.
  const price = (amount: number | null, exponent: number, currency: string) =>
    amount === null
      ? ""
      : `${(amount / 10 ** exponent).toFixed(exponent)} ${currency}`;

  return (
    <Panel className="mt-6">
      <h2 className="font-medium text-primary">{t("billing.buyMore")}</h2>
      {error ? <p className="mt-2 text-sm text-danger">{t(error)}</p> : null}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {(offers ?? []).map((offer) => (
          <div key={offer.code} className="flex flex-col rounded-xl border border-border p-4">
            <div className="font-medium">{offer.display_name}</div>
            <div className="mt-1 flex flex-col gap-0.5 text-sm text-secondary">
              <span>{n("billing.grants", offer.audit_credits)}</span>
              {offer.presence_credits > 0 ? (
                <span>{n("billing.grantsPresence", offer.presence_credits)}</span>
              ) : null}
            </div>
            <div className="mt-3 flex flex-1 items-end justify-between gap-3">
              <span className="font-semibold tabular-nums">
                {price(offer.display_amount_minor, offer.exponent, offer.currency)}
              </span>
              <Button onClick={() => buy(offer, promo)}>{t("billing.buy")}</Button>
            </div>
          </div>
        ))}
        {monthly ? (
          <div className="flex flex-col rounded-xl border border-border p-4">
            <div className="font-medium">{monthly.name}</div>
            <div className="mt-1 flex flex-col gap-0.5 text-sm text-secondary">
              <span>
                {monthly.analyses_unlimited
                  ? t("plan.valueUnlimited")
                  : monthly.analyses_per_month !== null
                    ? n("billing.grants", monthly.analyses_per_month)
                    : ""}
              </span>
              {monthly.presence_checks_per_month > 0 ? (
                <span>
                  {n("billing.grantsPresence", monthly.presence_checks_per_month)}
                </span>
              ) : null}
            </div>
            <div className="mt-3 flex flex-1 items-end justify-between gap-3">
              <span className="font-semibold tabular-nums">
                {monthly.prices[0]
                  ? `${price(
                      monthly.prices[0].amount_minor,
                      monthly.prices[0].exponent,
                      monthly.prices[0].currency,
                    )} ${t("billing.perMonth")}`
                  : ""}
              </span>
              <Button onClick={() => onSubscribe(monthly.code)}>
                {t("billing.subscribe")}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      {(offers ?? []).some((o) => o.promo_eligible) ? (
        <input
          value={promo}
          onChange={(e) => setPromo(e.target.value)}
          placeholder={t("billing.promo")}
          className="mt-3 w-56 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
        />
      ) : null}
    </Panel>
  );
}
