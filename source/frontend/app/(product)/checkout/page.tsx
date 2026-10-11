"use client";

/**
 * Сторінка оплати — та сама, що вписана в Paddle як default payment link.
 *
 * ## Що це за сторінка й чому вона окрема
 *
 * Paddle будує посилання на касу як `<default payment link>?_ptxn=<id>`
 * і приводить сюди людину: з листа, з іншого браузера, наступного дня.
 * Тому тут немає ані номера аудиту в адресі, ані гостьової
 * спроможності, ані припущення, що людина щойно була на `/result`.
 *
 * ## Два входи, одна сторінка
 *
 * Перший — `?_ptxn=` від Paddle, описаний вище: транзакція вже існує.
 * Другий — `?offer=` або `?plan=` зі сторінки цін: транзакції ще немає,
 * її треба відкрити. Обидва закінчуються тим самим: касою провайдера
 * поверх цього екрана.
 *
 * Другий вхід потребує акаунта, бо покупка належить організації. Хто
 * увійшов — іде в касу одразу; хто ні — на форму входу й назад сюди.
 * Кабінету на цьому шляху немає взагалі: кнопка «Придбати пакет» вела
 * на «Тариф і використання», і людина, яка вже увійшла, бачила зайвий
 * екран замість оплати.
 *
 * Ставити цю роль на `/result` було б помилкою: без `?audit=` вона
 * показує форму «перевірити сайт», і покупець із посиланням на оплату
 * побачив би форму замість каси.
 *
 * ## Ініціалізація на завантаженні, а не на кліку
 *
 * Це і є вся суть default payment link: Paddle.js сам відкриває касу,
 * побачивши `_ptxn`, — але лише після `Paddle.Initialize()`. Сторінка,
 * що ініціалізує провайдера в обробнику кнопки, виглядає робочою й для
 * цього шляху не працює взагалі.
 *
 * ## Межа секретів
 *
 * Сюди приходить один клієнтський токен, який Paddle і призначив для
 * браузера, і оточення. Обидва — з бекенда, а не з `NEXT_PUBLIC_*`,
 * щоб конфігурація провайдера лишалась в одному місці. Ключ API і
 * секрет вебхука не потрапляють сюди ніколи.
 *
 * ## Ця сторінка нічого не відмикає
 *
 * Успішна оплата тут не є доказом. Після неї Paddle повертає людину на
 * `/result?audit=…&processing=1`, і вже та сторінка питає сервер та
 * чекає на перевірену подію провайдера.
 *
 * ## Закрите вікно каси
 *
 * Закрита каса — не «оплата не пройшла» і не «все гаразд»: вона
 * закривається і після оплати (сама), і без неї (людина). Поки на
 * `checkout.closed` тут не було відповіді взагалі, сторінка лишалась
 * зі спінером «Відкриваємо захищену оплату» назавжди — так само глухо,
 * як мовчання про зниклі гроші.
 *
 * Далі — рівно ті самі три відповіді, що й на `/buy`, і плутати їх не
 * можна: провайдер підтвердив «не брали» (лише тут можна сказати
 * «кошти не списано»), провайдер мовчить (підтвердження ще немає), і
 * оплата дійшла (ідемо далі). У пакета для цього є власний рядок
 * покупки; у підписки рядка немає за побудовою — її створює перша
 * перевірена подія, — тож для неї ознакою служить сам акаунт.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { LogoStacked } from "../../components/Brand";
import { Alert, Button, Panel, Spinner } from "../../components/primitives";
import {
  ApiError,
  getAccount,
  openOfferCheckout,
  openPlanCheckout,
  readPurchaseState,
} from "../../lib/api";
import {
  readCheckoutConfig,
  recallAudit,
  recallLocale,
} from "../../lib/guest-payment";
import {
  initializePaddle,
  openPaddleOverlay,
  successUrlFor,
  transactionRefFrom,
} from "../../lib/paddle";
import type { Locale } from "../../lib/contracts";
import { afterPayment, intentFrom } from "../../lib/checkout-intent";
import { asSiteLocale, publicHomeHref } from "../../lib/i18n";
import { LocaleProvider, useLocale } from "../../lib/locale";
import { problemKey } from "../../lib/problem";

/**
 * Стани сторінки. `opening` не означає «оплачено» — лише те, що касу
 * провайдера попрошено відкритися.
 */
type Phase =
  | "loading"
  | "opening"
  | "waiting"
  | "notPaid"
  | "unknown"
  | "nothing"
  | "unconfigured"
  | "error";

/** Як часто питаємо про долю каси. Ті самі числа, що й на `/buy`. */
const POLL_MS = 4000;

/**
 * Скільки чекати, поки людина ще в касі, і скільки — коли вона її вже
 * закрила. Друге коротке навмисно: події про закрите без оплати вікно
 * не буде ніколи, і дві хвилини спінера в цьому випадку — обман.
 *
 * Чекати ЛИШЕ на `checkout.closed` не можна: подія може не дійти
 * взагалі (людина пішла на іншу вкладку, провайдер її не надіслав), і
 * тоді сторінка висить так само, як висіла без обробника — просто з
 * приємнішим написом.
 */
const PAYMENT_ATTEMPTS = 30;
const CLOSED_ATTEMPTS = 4;
/** Після цього питаємо провайдера навіть при відкритій касі. */
const PATIENT_TICKS = 4;

export default function CheckoutPage() {
  // Paddle приводить сюди лише з `_ptxn` — мови в адресі немає й не
  // буде. Її памʼятає гостьова сесія: людина, що пішла платити з
  // результату своєю мовою, бачить ту саму мову й тут — будь-яку з
  // шести мов сайту, а не лише українську, як було, поки розпізнавалась
  // одна «uk» і решта чотири мовчки падали в англійську. Читання — в
  // ефекті: сторінка рендериться й на сервері, де сховища немає, і
  // початковий стан мусить збігатися з обох боків.
  const [locale, setLocale] = useState<Locale>("en");
  useEffect(() => {
    // Адреса головніша за памʼять: `?lang=` ставить сторінка цін, і це
    // мова, якою людина щойно читала умови. Памʼять лишається для входу
    // від Paddle, де параметрів немає взагалі.
    const asked = asSiteLocale(new URLSearchParams(window.location.search).get("lang"));
    const remembered = asked ?? asSiteLocale(recallLocale());
    if (remembered) setLocale(remembered);
  }, []);
  return (
    <LocaleProvider locale={locale}>
      <Checkout />
    </LocaleProvider>
  );
}

function Checkout() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [detail, setDetail] = useState("");
  /**
   * Касу відкриваємо РІВНО раз.
   *
   * Мова сторінки приходить у стан після першого рендеру (`en` → `uk`),
   * і поки вона стояла в залежностях ефекту, той виконувався вдруге: два
   * запити до каси, дві транзакції у провайдера й дві незавершені покупки
   * на одну людину. Мову для дороги на вхід читаємо з адреси, а не зі
   * стану, тож ефект більше ні від чого не залежить; сторож на випадок
   * майбутніх залежностей лишається.
   */
  const started = useRef(false);
  /** Каса закрилась. Доти питати провайдера нема про що. */
  const closed = useRef(false);
  const waited = useRef(0);
  /** Покупка пакета. У підписки її немає — там ознакою служить акаунт. */
  const [purchaseId, setPurchaseId] = useState<string | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  /** Що саме купують — щоб опитування знало, куди вести після оплати. */
  const intentRef = useRef<ReturnType<typeof intentFrom>>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let alive = true;
    void (async () => {
      const intent = intentFrom(window.location.search);
      intentRef.current = intent;
      if (intent) {
        try {
          const opened =
            intent.kind === "offer"
              ? await openOfferCheckout(intent.code)
              : await openPlanCheckout(intent.code);
          if (!alive) return;
          if (intent.kind === "offer" && "purchase_id" in opened) {
            setPurchaseId(opened.purchase_id);
          } else {
            setSubscribing(true);
          }
          const config = await readCheckoutConfig();
          if (!alive) return;
          const overlaid = await openPaddleOverlay({
            clientToken: config.client_token,
            environment: config.environment,
            transactionRef: opened.provider_ref,
            // Куди після оплати — залежить від того, що купили.
            //
            // Разова перевірка зі сторінки цін — це початок роботи, а не
            // поповнення балансу: покупець ще не називав ані сайту, ані
            // бренду, і «Тариф і використання» показав би йому цифру
            // замість наступного кроку (рішення власника 2026-09-06).
            // Пакет і підписка — саме поповнення, і для них кабінет
            // лишається правильним місцем.
            successUrl: `${window.location.origin}${afterPayment(intent)}`,
            // Без цього сторінка не дізнається про закриту касу ніколи
            // й лишається зі спінером назавжди.
            onClosed: () => {
              closed.current = true;
            },
          });
          if (!alive) return;
          if (!overlaid) {
            window.location.assign(opened.url);
            return;
          }
          // «Чекаємо» — не «оплачено»: далі про долю каси питає сервер.
          setPhase("waiting");
        } catch (problem) {
          if (!alive) return;
          const status = problem instanceof ApiError ? problem.status : 0;
          if (status === 401 || status === 403) {
            // Не увійшов — вхід і назад сюди, у ту саму касу.
            const back = `${window.location.pathname}${window.location.search}`;
            const asked =
              asSiteLocale(new URLSearchParams(window.location.search).get("lang")) ?? "en";
            router.replace(`/login?lang=${asked}&next=${encodeURIComponent(back)}`);
            return;
          }
          if (status === 409) {
            // Підписка вже є: платити вдруге нема за що, а керують нею в
            // кабінеті. Це єдина дорога звідси в кабінет — і вона не на
            // шляху до оплати, а замість неї.
            router.replace("/app/plan");
            return;
          }
          // Каса не відкрилась. Причина службова, тож екран каже те, що
          // правда для людини: оплата зараз недоступна, і це на нашому боці.
          setPhase("unconfigured");
        }
        return;
      }

      const transactionRef = transactionRefFrom(window.location.search);
      if (!transactionRef) {
        // Сюди прийшли без транзакції — платити нема за що. Мовчазний
        // спінер удавав би, що щось відбувається.
        if (alive) setPhase("nothing");
        return;
      }
      try {
        const config = await readCheckoutConfig();
        if (!alive) return;
        const paddle = await initializePaddle({
          clientToken: config.client_token,
          environment: config.environment,
          successUrl: successUrlFor(window.location.origin, recallAudit()),
        });
        if (!alive) return;
        // Виклику `Checkout.open` тут немає навмисно: побачивши `_ptxn`
        // в адресі, Paddle.js відкриває касу сам. Другий виклик відкрив
        // би її двічі.
        setPhase(paddle === null ? "unconfigured" : "opening");
      } catch (problem) {
        if (!alive) return;
        // Ключ каталогу, не сире значення: сюди приходять машинні коди
        // гостьового API й службові рядки, які людині не показуються.
        setDetail(problemKey(problem));
        setPhase("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  /**
   * Що сталося з касою, яку закрили.
   *
   * Провайдера питаємо лише після `checkout.closed`: поки вікно
   * відкрите, події ще можуть дійти самі, а зайвий запит нічого не
   * додає. Пакет має власний рядок покупки й відповідає точно;
   * підписка рядка не має за побудовою, тож ознакою служить сам
   * акаунт — щойно перевірена подія створила підписку, кабінет її
   * бачить.
   */
  useEffect(() => {
    if (phase !== "waiting") return;
    let alive = true;
    const tick = async () => {
      // Стан `waiting` без наміру недосяжний, але саме він каже, куди
      // вести після оплати, тож перевіряємо явно.
      const intent = intentRef.current;
      if (!intent) return;
      waited.current += 1;
      // Провайдера питаємо одразу, щойно касу закрито: події в такому
      // разі може не бути ніколи. Поки вікно відкрите — лише коли наші
      // записи мовчать надто довго.
      const ask = closed.current || waited.current > PATIENT_TICKS;
      try {
        if (purchaseId) {
          const state = await readPurchaseState(purchaseId, ask);
          if (!alive) return;
          if (state.state === "paid") {
            router.replace(afterPayment(intent));
            return;
          }
          if (state.charged === false) {
            // Провайдер підтвердив: грошей не брали. Лише цей стан має
            // право сказати «кошти не списано».
            setPhase("notPaid");
            return;
          }
        } else if (subscribing) {
          const account = await getAccount();
          if (!alive) return;
          if (
            account.billing_state !== "free" &&
            account.billing_state !== "cancelled"
          ) {
            router.replace(afterPayment(intent));
            return;
          }
        }
        // Провайдер не сказав «ні» — отже, ми не знаємо. Обіцяти, що
        // кошти не списано, тут не можна.
        const enough = closed.current ? CLOSED_ATTEMPTS : PAYMENT_ATTEMPTS;
        if (waited.current >= enough) setPhase("unknown");
      } catch {
        if (waited.current >= PAYMENT_ATTEMPTS) setPhase("unknown");
      }
    };
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [phase, purchaseId, subscribing, router]);

  /** Друга спроба відкриває ту саму сторінку — і ту саму касу. */
  const retry = () => {
    started.current = false;
    closed.current = false;
    waited.current = 0;
    setPurchaseId(null);
    setSubscribing(false);
    setPhase("loading");
    window.location.reload();
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-12">
      {/* Логотип по центру, як на решті технічних екранів: тут немає ні
          шапки, ні колонок, і притиснутий до краю знак виглядає
          недоробкою. */}
      <header className="mb-8 flex justify-center">
        {/* Дорога назад на сайт. Без неї сторінка оплати була глухим
            кутом: знак на ній нікуди не вів. */}
        <Link href={publicHomeHref(locale)} aria-label="Crawldy">
          <LogoStacked />
        </Link>
      </header>
      {phase === "loading" || phase === "opening" || phase === "waiting" ? (
        <Panel>
          <div className="flex items-center gap-3">
            <Spinner className="size-5" />
            <div>
              <h1 className="text-base font-semibold text-foreground">
                {t(phase === "waiting" ? "order.waiting" : "checkout.openingTitle")}
              </h1>
              <p className="mt-0.5 text-sm text-muted">
                {t(phase === "waiting" ? "checkout.unknownLead" : "checkout.openingLead")}
              </p>
            </div>
          </div>
        </Panel>
      ) : null}

      {phase === "notPaid" || phase === "unknown" ? (
        <Panel>
          <h1 className="text-base font-semibold text-foreground">
            {t(phase === "notPaid" ? "order.notPaidTitle" : "order.unknownTitle")}
          </h1>
          {/* «Кошти не списано» каже лише той стан, якому провайдер це
              підтвердив; коли він мовчить — текст інший. */}
          <p className="mt-1 text-sm text-muted">
            {t(phase === "notPaid" ? "order.notPaidLead" : "checkout.unknownLead")}
          </p>
          <div className="mt-3">
            <Button onClick={retry}>{t("order.retry")}</Button>
          </div>
        </Panel>
      ) : null}

      {phase === "nothing" ? (
        <Panel>
          <h1 className="text-base font-semibold text-foreground">
            {t("checkout.nothingTitle")}
          </h1>
          <p className="mt-1 text-sm text-muted">{t("checkout.nothingLead")}</p>
        </Panel>
      ) : null}

      {phase === "unconfigured" ? (
        <Panel className="border-warning/40">
          <h1 className="text-base font-semibold text-foreground">
            {t("checkout.unavailableTitle")}
          </h1>
          <p className="mt-1 text-sm text-muted">{t("checkout.unavailableLead")}</p>
        </Panel>
      ) : null}

      {phase === "error" ? (
        <Alert tone="danger">{detail ? t(detail) : t("checkout.unavailableLead")}</Alert>
      ) : null}
    </main>
  );
}
