/**
 * Стан оплати на екрані — і чому він саме такий.
 *
 * Чистий редюсер без React і без мережі: вся логіка «що показати
 * людині» живе тут і перевіряється без браузера. Компонент лишається
 * розміткою, а не місцем, де ховається правило доступу.
 *
 * ## Одне правило, з якого випливає решта
 *
 * **`unlocked` приходить із сервера й нізвідки більше.** Жоден перехід
 * тут не встановлює його сам: ані відкриття каси, ані повернення з
 * неї, ані «здається, минуло достатньо часу». Саме тому редюсер не
 * має дії «оплачено» — є лише «сервер відповів ось це».
 */

import type { PaymentState, PaymentStatus } from "./guest-payment";

/**
 * Що показує екран.
 *
 * `reconciling`, `canceled` і `unavailable` — наші стани, не серверні.
 * Перше — вікно каси закрилось без слова «оплачено», і сервер звіряє
 * транзакцію з провайдером; друге — звірка підтвердила, що списання не
 * було; третє — наша ж відмова відкрити касу. Змішувати їх із
 * серверними означало б стверджувати про гроші те, чого сервер не
 * казав.
 *
 * ## Закрите вікно — не доказ, що грошей не взяли
 *
 * Каса закривається і після оплати (сама), і без неї (людина). Коли
 * подія `checkout.completed` не прийшла, це ще нічого не доводить:
 * подія могла загубитись, а гроші — піти. Тому `checkout.closed` без
 * `completed` веде не в «не списано», а в звірку, і лише відповідь
 * сервера «списання не було» відкриває стан із повторною спробою.
 */
export type Phase =
  | "idle"
  | "opening"
  | "processing"
  | "reconciling"
  | "paid"
  | "failed"
  | "refunded"
  | "canceled"
  | "unavailable";

export interface FlowState {
  phase: Phase;
  /** Чи можна читати повний звіт. Лише з відповіді сервера. */
  unlocked: boolean;
  /** Скільки разів ми вже питали сервер — для інтервалу опитування. */
  attempt: number;
  /**
   * Каса сказала, що оплату завершено.
   *
   * Це НЕ «оплачено»: доказ грошей і далі лише в події провайдера, і
   * `unlocked` цим прапорцем не стає. Він відповідає рівно на одне
   * питання — чому закрилося вікно. Каса закривається сама після
   * успішної оплати, і без цієї памʼяті те саме закриття читалось як
   * «людина передумала».
   */
  completed: boolean;
}

export type FlowAction =
  | { type: "checkout.requested" }
  | { type: "checkout.opened" }
  | { type: "checkout.unavailable" }
  | { type: "checkout.completed" }
  | { type: "checkout.closed" }
  | { type: "server.said"; status: PaymentStatus };

export const INITIAL_FLOW: FlowState = {
  phase: "idle",
  unlocked: false,
  attempt: 0,
  completed: false,
};

const SERVER_PHASE: Record<PaymentState, Phase> = {
  none: "idle",
  processing: "processing",
  paid: "paid",
  failed: "failed",
  refunded: "refunded",
};

export function reduceFlow(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "checkout.requested":
      return { ...state, phase: "opening" };

    case "checkout.opened":
      // Каса відкрита — це намір, не оплата. Далі відповідає сервер.
      return { ...state, phase: "processing", attempt: 0 };

    case "checkout.unavailable":
      return { ...state, phase: "unavailable" };

    case "checkout.completed":
      // Каса відзвітувала про успішну оплату. Це ще не доступ: гроші
      // підтверджує подія провайдера, і саме її ми чекаємо далі. Але
      // закриття вікна після цього вже не можна читати як відмову.
      if (state.unlocked) return state;
      return { ...state, phase: "processing", completed: true };

    case "checkout.closed":
      // Вікно закрито. Що це означає, залежить від того, чи встигла
      // каса сказати «оплачено»: після успішної оплати вона закривається
      // САМА, і без цієї перевірки людині, яка щойно заплатила,
      // показувалось «ви закрили вікно, не завершивши оплату».
      if (state.unlocked || state.phase === "paid" || state.completed) return state;
      // Без слова «оплачено» вікно закрите — це питання, а не відповідь.
      // Сервер звірить транзакцію з провайдером; до його слова екран не
      // каже ані «не списано», ані «спробуйте ще раз».
      return { ...state, phase: "reconciling", attempt: 0 };

    case "server.said": {
      const { status } = action;
      if (state.phase === "reconciling" && status.state === "processing") {
        // Події від провайдера немає — вирішує те, що сервер зʼясував у
        // нього сам. `false` — списання не було, і людина може почати
        // знову; `true` — гроші пішли, чекаємо на подію так само, як
        // після успішної каси; `null` — провайдер ще не відповів, і
        // стан лишається звіркою.
        const phase: Phase =
          status.charged === false
            ? "canceled"
            : status.charged === true
              ? "processing"
              : "reconciling";
        return {
          phase,
          unlocked: false,
          attempt: state.attempt + 1,
          completed: state.completed,
        };
      }
      const phase = SERVER_PHASE[status.state];
      // Оплачено, але доступу ще немає — це не «готово». Кажемо
      // «обробляємо» й питаємо далі: обіцяти звіт, якого не видно, —
      // найгірший із можливих станів екрана.
      const settled = status.state === "paid" && !status.unlocked;
      return {
        phase: settled ? "processing" : phase,
        unlocked: status.unlocked,
        attempt: state.attempt + 1,
        completed: state.completed,
      };
    }
  }
}

/** Чи варто питати сервер далі. */
export function shouldKeepPolling(state: FlowState): boolean {
  return (
    (state.phase === "processing" || state.phase === "reconciling") &&
    !state.unlocked
  );
}

/** Чи має наступне питання до сервера нести прохання звірити транзакцію. */
export function needsReconciliation(state: FlowState): boolean {
  return state.phase === "reconciling";
}

/**
 * Чи можна пробувати оплату ще раз із цього стану.
 *
 * Звірка (`reconciling`) сюди не входить навмисно: поки сервер не сказав,
 * що списання не було, кнопка «спробувати ще раз» пропонувала б другу
 * оплату людині, яка, можливо, щойно зробила першу.
 */
export function canRetry(state: FlowState): boolean {
  return (
    !state.unlocked &&
    (state.phase === "idle" ||
      state.phase === "failed" ||
      state.phase === "canceled" ||
      state.phase === "unavailable")
  );
}
