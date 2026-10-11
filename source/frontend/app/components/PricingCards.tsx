"use client";

/**
 * Чотири картки сторінки цін: Безкоштовне превʼю / Разова / Пакет /
 * Місячний план.
 *
 * ## Чотири рівні блоки, а не смуга й три картки
 *
 * Композиція — та сама, що була до 5 вересня (`164a74d`): один ряд із
 * чотирьох однакових карток на широкому екрані, два стовпчики на
 * планшеті, вертикальний стовпчик на телефоні. Перебудова «смуга превʼю
 * на всю ширину + три платні картки» була пропозицією зі статусом
 * «pending owner approval», яку помилково провели в промпт як
 * затверджену; власник її відхилив, і цей файл повертає попередню
 * презентацію. Безкоштовне превʼю стоїть у ряду як перший блок: це
 * вхід, показаний так само чітко, як платні формати.
 *
 * Кожна картка має однакову ієрархію (як у `164a74d`): рядок позначки,
 * заголовок блока, перелік того, що входить, ціна по центру над кнопкою,
 * одна дія притиснута до низу. У превʼю ціни немає: воно безкоштовне за
 * означенням, і окремий рядок лише повторював би заголовок.
 *
 * ## Склад — зі сторінки, комерційні значення — з конфігурації
 *
 * Що входить у пропозицію, каже сторінка своєї мови (`strings`), і це
 * видно ЗАВЖДИ. З бекенда (`/v1/offers`, `/v1/plans`) приходять лише
 * комерційні значення: ціна й валюта разової, ціна, валюта й кількість N
 * пакета, ціна, валюта й кількість перевірок Actual AI Presence місячного
 * плану. Відсутнє значення ховає лише саме число — рядок про склад
 * лишається підписом без числа, а головна ціна каже «ціна за запитом».
 * Вигаданих чисел не буває в жодному зі станів. Логіка рядків —
 * `lib/pricing-lines.ts`, чиста й покрита тестами без DOM.
 *
 * ## Три різні дороги до каси — за моделлю доступу
 *
 * - Превʼю і Разова ведуть на /result: ані те, ані інше не потребує
 *   акаунта; разова покупка відкриває повний звіт просто з превʼю.
 * - Пакет і Місячний план ведуть просто в касу: `/checkout?offer=` та
 *   `/checkout?plan=`. Акаунт їм потрібен (покупка належить організації),
 *   але влаштовує його сама сторінка оплати: хто вже увійшов, той іде в
 *   касу одразу; хто ні — на форму входу й назад у ту саму касу.
 *   Кабінету на цьому шляху немає: доки кнопка вела в кабінет на «Тариф
 *   і використання», людина, яка вже увійшла, бачила зайвий екран
 *   замість оплати (рішення власника 2026-09-06).
 */

import { useEffect, useState } from "react";

import { Icon } from "./Icon";
import { API_URL } from "../lib/api";
import { monthlyToShow, type PluralForms } from "../lib/pricing";
import { checkoutHref } from "../lib/checkout-intent";
import {
  type MonthlyPlan,
  type PackOffer,
  type PricingStrings,
  monthlyLines,
  monthlyPriceText,
  packLines,
  packUnitNote,
  priceText,
  singleLines,
} from "../lib/pricing-lines";

export type { PluralForms, PricingStrings };

/**
 * Пропозиція каталогу — лише ті поля, які потрібні рендеру. Кількість
 * присутності в пакеті приходить звідси окремим числом: вона більше не
 * дорівнює кількості перевірок (рішення власника 2026-09-06).
 */
interface PublicOffer extends PackOffer {
  code: string;
  offer_type: string;
}

/**
 * Публічний тариф — поля для показу й для вибору (`monthlyToShow`).
 * Безліміт перевірок і місячний період — властивості продукту, а не
 * поля конфігурації, тож їх тут немає.
 */
interface PublicPlan extends MonthlyPlan {
  code: string;
  sort_order: number;
  highlighted: boolean;
}

const CTA =
  "block w-full rounded-lg bg-brand px-3 py-2.5 text-center text-sm font-medium text-brand-ink hover:bg-brand-hover";

/**
 * Розмір ціни — ОДИН на всі картки: у сітці, де ціни й порівнюють, різні
 * кеглі робили найбільшим не найважливіше, а найкоротше. `break-words`
 * лишається запобіжником для довших валют.
 */
const PRICE_SIZE = "text-xl";

/**
 * Картка: рядок позначки, заголовок, перелік, ціна по центру над кнопкою,
 * кнопка внизу — ієрархія `164a74d`. Без ціни (превʼю) перелік і кнопка
 * стоять так само; `flex-1` тримає низ усіх чотирьох на одній лінії.
 */
function Card({
  badge,
  heading,
  lines,
  note,
  price,
  priceNote,
  cta,
}: {
  badge?: string;
  heading: string;
  lines: string[];
  /** Дрібний підпис ОДРАЗУ під переліком: умова доступу до формату
   *  («Потрібен акаунт Crawldy» / «Без реєстрації»). Він не складова
   *  пропозиції, тому стоїть поза списком і без галочки. */
  note?: string;
  price?: string;
  /** Дрібніший рядок під ціною: обчислена ціна однієї перевірки пакета. */
  priceNote?: string | null;
  cta: { href: string; label: string };
}) {
  return (
    <div className="flex flex-col rounded-xl border border-border bg-surface p-5">
      {/* Рядок позначки резервується в УСІХ картках, навіть порожній:
          інакше картка з позначкою зсуває заголовок на рядок нижче, і
          заголовки чотирьох блоків перестають стояти на одній лінії.
          Вигляд — підпис, а не дія: заливка бренду робила б її схожою
          на кнопку. Позначка притиснута до правого краю (рішення
          власника): ліворуч під нею починається заголовок, і два
          написи в одній колонці читались як один зсунутий блок. */}
      <div className="mb-2 flex min-h-6 justify-end">
        {badge ? (
          <span className="inline-block rounded-full border border-accent bg-accent-soft px-2.5 py-0.5 text-sm font-medium text-accent-ink sm:text-xs">
            {badge}
          </span>
        ) : null}
      </div>
      <h2 className="font-medium text-primary">{heading}</h2>
      <ul className="mt-3 flex flex-col gap-1.5 text-sm text-secondary">
        {lines.map((line) => (
          <li key={line} className="flex items-start gap-2">
            <Icon name="check" className="mt-0.5 size-4 shrink-0 text-accent" />
            <span>{line}</span>
          </li>
        ))}
      </ul>
      {note ? (
        <p className="mt-2 text-sm font-medium text-accent-text sm:text-xs">{note}</p>
      ) : null}
      {/* Ціна стоїть МІЖ переліком і кнопкою, крупно й по центру: у ряду
          з чотирьох саме її порівнюють. */}
      <div className="mt-5 flex flex-1 flex-col justify-end gap-4">
        {price ? (
          <div className="text-center">
            <p
              className={`${PRICE_SIZE} break-words font-semibold tracking-tight tabular-nums text-primary`}
            >
              {price}
            </p>
            {priceNote ? (
              <p className="mt-1 text-sm font-medium tabular-nums text-secondary sm:text-xs">{priceNote}</p>
            ) : null}
          </div>
        ) : null}
        <a href={cta.href} className={CTA}>
          {cta.label}
        </a>
      </div>
    </div>
  );
}

export function PricingCards({
  locale,
  strings,
}: {
  locale: string;
  strings: PricingStrings;
}) {
  const [offers, setOffers] = useState<PublicOffer[] | null>(null);
  const [plans, setPlans] = useState<PublicPlan[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        // Мова їде в обидва запити: бекенд віддає каталог мовою
        // сторінки, хоч слів із нього ця сторінка й не показує — числа
        // й порядок однакові для всіх мов за побудовою.
        const [offersRes, plansRes] = await Promise.all([
          fetch(`${API_URL}/v1/offers?lang=${locale}`, { cache: "no-store" }),
          fetch(`${API_URL}/v1/plans?lang=${locale}`, { cache: "no-store" }),
        ]);
        if (!offersRes.ok || !plansRes.ok) throw new Error("http");
        const offersBody = (await offersRes.json()) as PublicOffer[];
        const plansBody = (await plansRes.json()) as { plans: PublicPlan[] };
        if (cancelled) return;
        setOffers(offersBody);
        setPlans(plansBody.plans ?? []);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const loading = !failed && offers === null;

  // Кожен формат бере СВОЮ налаштовану пропозицію, якщо вона є. Немає —
  // картка все одно рендериться з повним складом: формат оплати існує
  // незалежно від того, чи заведено для нього ціну.
  const single = (offers ?? []).find((offer) => offer.offer_type === "single") ?? null;
  const pack = (offers ?? []).find((offer) => offer.offer_type === "pack") ?? null;
  const monthly = monthlyToShow(plans ?? []);

  // Превʼю і разова покупка не потребують акаунта. Мова їде в адресі:
  // гостьовий екран говорить усіма шістьма мовами сайту.
  const resultHref = locale === "en" ? "/result" : `/result?lang=${locale}`;
  // Пряма дорога в касу. Вхід, якщо він потрібен, влаштовує сама сторінка
  // оплати: людина, яка вже увійшла, не має бачити ані форми входу, ані
  // кабінету, а та, що не увійшла, повертається сюди ж після входу.
  // Раніше кнопка вела в кабінет на «Тариф і використання», і каса
  // відкривалася вже там — зайвий екран на шляху до оплати.
  const cabinetHref = `/login?lang=${locale}&next=${encodeURIComponent("/app/plan")}`;
  // Анонімна каса разової перевірки: оплата → сайт → звіти, без входу.
  const buyHref = locale === "en" ? "/buy" : `/buy?lang=${locale}`;

  // Поки числа їдуть — крапки, а не «ціна за запитом»: друге було б
  // неправдою протягом пів секунди. Сітка при цьому вже стоїть повністю.
  const pending = loading ? "…" : strings.priceOnRequest;

  return (
    <div aria-live="polite">
      {/* Чотири блоки — завжди, у ряд. Формат оплати існує незалежно від
          того, чи заведено для нього ціну; з конфігурації приходять числа
          й умови, а не сам факт існування блока. `aria-busy`, поки числа
          їдуть: знімок половинного стану не має права існувати. */}
      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        aria-busy={loading || undefined}
      >
        <Card
          heading={strings.free.heading}
          lines={strings.free.bullets}
          cta={{ href: resultHref, label: strings.free.cta }}
        />

        <Card
          heading={strings.single.kind}
          lines={singleLines(locale, strings)}
          note={strings.single.note}
          price={priceText(single, pending)}
          // Спершу оплата, потім дані сайту — і БЕЗ реєстрації
          // (рішення власника 2026-09-06). До того ця кнопка вела на
          // форму безкоштовного превʼю, і людина, яка натиснула
          // «купити», бачила перевірку сайту замість каси. Превʼю
          // лишилось окремою карткою ліворуч — хто хоче спершу
          // подивитись, іде туди свідомо.
          //
          // Адреса тут своя, не спільна з пакетом: `/checkout` — це
          // дорога через акаунт, бо пакет і підписка лягають на баланс.
          // Разову купує гість, і акаунта в неї немає ніде.
          cta={{ href: buyHref, label: strings.single.cta }}
        />

        <Card
          heading={strings.pack.kind}
          lines={packLines(locale, strings, pack)}
          note={strings.pack.note}
          price={priceText(pack, pending)}
          priceNote={packUnitNote(strings, pack)}
          // Пакета в каталозі може не бути (ціну ще не задано) — тоді
          // конкретної каси не існує, і чесніше привести в кабінет, ніж
          // відкривати оплату невідомо чого.
          cta={{
            href: pack
              ? checkoutHref({ kind: "offer", code: pack.code }, locale)
              : cabinetHref,
            label: strings.pack.cta,
          }}
        />

        <Card
          badge={strings.monthly.badge}
          heading={strings.monthly.kind}
          lines={monthlyLines(locale, strings, monthly)}
          note={strings.monthly.note}
          price={monthlyPriceText(monthly, strings, pending)}
          cta={{
            href: monthly
              ? checkoutHref({ kind: "plan", code: monthly.code }, locale)
              : cabinetHref,
            label: strings.monthly.cta,
          }}
        />
      </div>

      {failed ? (
        <p className="mt-4 max-w-measure text-sm text-secondary">
          {strings.loadFailed}
        </p>
      ) : null}
    </div>
  );
}
