"use client";

/**
 * Пейвол і чесні стани оплати.
 *
 * Один компонент на весь платіжний бік безкоштовного результату:
 * пропозиція, відкриття каси, очікування підтвердження, відмова,
 * закрите вікно. Розділяти їх на кілька панелей означало б розводити
 * по файлах один стан однієї кнопки.
 *
 * ## Чого тут немає
 *
 * Ціни — вона живе в прайсі провайдера, і назвати її тут означало б
 * мати друге джерело правди про гроші.
 *
 * Права. `unlocked` приходить із сервера й нікуди звідси не
 * встановлюється: цей компонент уміє показати стан і не вміє його
 * призначити.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";

import { Icon } from "./Icon";
import { Button, Panel, Spinner } from "./primitives";
import {
  isSettled,
  nextPollDelayMs,
  openCheckout,
  readPaymentStatus,
  rememberAudit,
} from "../lib/guest-payment";
import { openPaddleOverlay } from "../lib/paddle";
import {
  INITIAL_FLOW,
  canRetry,
  needsReconciliation,
  reduceFlow,
  shouldKeepPolling,
  type FlowState,
} from "../lib/payment-flow";
import { useLocale } from "../lib/locale";

interface Props {
  auditId: string;
  /**
   * Стан, з якого починаємо. Сторінка повернення з каси передає
   * `processing`, щоб опитування почалося одразу, а не після кліку.
   */
  initial?: FlowState;
  /** Право прийшло — сторінка перемальовує себе повним звітом. */
  onUnlocked?: () => void;
}

export function PaymentPanel({ auditId, initial, onUnlocked }: Props) {
  const [flow, dispatch] = useReducer(reduceFlow, initial ?? INITIAL_FLOW);
  const unlockedRef = useRef(false);

  const start = useCallback(async () => {
    dispatch({ type: "checkout.requested" });
    try {
      // Запамʼятати ДО каси: якщо накладну відкрити не вдасться, ми
      // підемо за адресою провайдера, і сторінка оплати мусить знати,
      // куди повернути людину — в адресі `?_ptxn=` аудиту немає.
      rememberAudit(auditId);
      const intent = await openCheckout(auditId);
      const opened = await openPaddleOverlay({
        clientToken: intent.client_token,
        environment: intent.environment,
        transactionRef: intent.transaction_ref,
        onCompleted: () => dispatch({ type: "checkout.completed" }),
        onClosed: () => dispatch({ type: "checkout.closed" }),
      });
      dispatch({ type: "checkout.opened" });
      if (!opened) {
        // Накладну касу відкрити нічим — переходимо за адресою, яку
        // видав провайдер. Мовчазна відмова була б гіршою.
        window.location.assign(intent.checkout_url);
      }
    } catch {
      // Причина не показується: локалізовані заголовок і підводка стану
      // «недоступно» вже кажуть усе, а сирий код сервера («checkout.
      // unavailable») людині не каже нічого.
      dispatch({ type: "checkout.unavailable" });
    }
  }, [auditId]);

  // Опитування сервера. Єдиний спосіб дізнатися про оплату: повернення
  // браузера й параметри його адреси доказом не є. Після закритого без
  // оплати вікна те саме питання несе прохання звірити транзакцію з
  // провайдером — інакше сервер, який не отримав події, не має що
  // відповісти, крім «обробляємо».
  useEffect(() => {
    if (!shouldKeepPolling(flow)) return;
    let alive = true;
    const reconcile = needsReconciliation(flow);
    const timer = window.setTimeout(
      () => {
        void (async () => {
          try {
            const status = await readPaymentStatus(auditId, { reconcile });
            if (!alive) return;
            dispatch({ type: "server.said", status });
            if (status.unlocked && !unlockedRef.current) {
              unlockedRef.current = true;
              onUnlocked?.();
            }
            if (isSettled(status)) alive = false;
          } catch {
            // Мережа моргнула — не привід оголошувати оплату невдалою.
            // Наступна спроба піде за тим самим розкладом; звірка без
            // відповіді лишається звіркою (`charged: null`).
            if (alive) dispatch({ type: "server.said", status: {
              audit_id: auditId,
              state: "processing",
              unlocked: false,
              charged: null,
            } });
          }
        })();
      },
      nextPollDelayMs(flow.attempt),
    );
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [flow, auditId, onUnlocked]);

  if (flow.phase === "processing") return <Waiting />;
  if (flow.phase === "reconciling") return <Reconciling />;
  if (flow.phase === "failed") return <Retry reason="failed" onRetry={start} />;
  if (flow.phase === "canceled") return <Retry reason="canceled" onRetry={start} />;
  if (flow.phase === "refunded") return <Retry reason="refunded" onRetry={start} />;
  if (flow.phase === "unavailable") {
    return <Retry reason="unavailable" onRetry={start} />;
  }
  return <Paywall busy={flow.phase === "opening"} onBuy={start} />;
}

/**
 * Пейвол. Каже, що саме відкриває повний аудит, — без ціни: вона живе
 * в прайсі провайдера, і плейсхолдер тут був би вигаданим числом.
 */
function Paywall({ busy, onBuy }: { busy: boolean; onBuy: () => void }) {
  const { t } = useLocale();
  const unlocks = [
    "scores",
    "findings",
    "pages",
    "evidence",
    "fixes",
    "download",
  ] as const;
  return (
    <Panel className="border-accent/40">
      <h2 className="text-base font-semibold text-foreground">
        {t("free.paywallTitle")}
      </h2>
      <p className="mt-1 text-sm text-muted">{t("free.paywallLead")}</p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {unlocks.map((key) => (
          <li key={key} className="flex items-start gap-2 text-sm text-foreground">
            <Icon name="check" className="mt-0.5 size-4 shrink-0 text-accent" />
            {t(`free.unlocks.${key}`)}
          </li>
        ))}
      </ul>
      <div className="mt-5">
        <Button size="lg" loading={busy} onClick={onBuy}>
          {t("free.cta")}
        </Button>
      </div>
    </Panel>
  );
}

/**
 * Повернення з каси — не доказ оплати. Доказ — перевірена подія
 * провайдера, і поки її немає, повний вміст закритий, а людині чесно
 * сказано, що відбувається. Ні «оплата не пройшла», ні повний звіт
 * авансом: перше — неправда, друге — дірка в межі.
 */
function Waiting() {
  const { t } = useLocale();
  return (
    <Panel className="border-accent/40">
      <div className="flex items-center gap-3">
        <Spinner className="size-5" />
        <div>
          <h2 className="text-base font-semibold text-foreground">
            {t("free.processingTitle")}
          </h2>
          <p className="mt-0.5 text-sm text-muted">{t("free.processingLead")}</p>
        </div>
      </div>
    </Panel>
  );
}

/**
 * Вікно каси закрилось без слова «оплачено», і сервер звіряє
 * транзакцію з провайдером.
 *
 * Кнопки тут немає навмисно. «Спробувати ще раз» до відповіді сервера
 * пропонувало б другу оплату людині, яка, можливо, щойно зробила першу,
 * а «кошти не списано» стверджувало б те, чого ще ніхто не перевірив.
 */
function Reconciling() {
  const { t } = useLocale();
  return (
    <Panel className="border-accent/40">
      <div className="flex items-center gap-3">
        <Spinner className="size-5" />
        <div>
          <h2 className="text-base font-semibold text-foreground">
            {t("free.payment.reconciling.title")}
          </h2>
          <p className="mt-0.5 text-sm text-muted">
            {t("free.payment.reconciling.lead")}
          </p>
        </div>
      </div>
    </Panel>
  );
}

type RetryReason = "failed" | "canceled" | "refunded" | "unavailable";

/** Спроба не вдалася — і це не блокувач. Кнопка лишається живою. */
function Retry({
  reason,
  onRetry,
}: {
  reason: RetryReason;
  onRetry: () => void;
}) {
  const { t } = useLocale();
  return (
    <Panel className="border-warning/40">
      <h2 className="text-base font-semibold text-foreground">
        {t(`free.payment.${reason}.title`)}
      </h2>
      <p className="mt-1 text-sm text-muted">{t(`free.payment.${reason}.lead`)}</p>
      <div className="mt-5">
        <Button size="lg" onClick={onRetry}>
          {t("free.payment.retry")}
        </Button>
      </div>
    </Panel>
  );
}

export { canRetry };
