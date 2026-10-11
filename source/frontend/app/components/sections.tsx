/**
 * Блоки, з яких складаються публічні сторінки.
 *
 * ## Навіщо вони існують
 *
 * Шість мов × десяток сторінок — це шістдесят сторінок. Написані
 * як окремий JSX, вони розійдуться вже на третій правці: німецька
 * лишиться з трьома пунктами там, де в англійській їх стало чотири, і
 * ніхто цього не побачить, бо жоден тест не читає верстку.
 *
 * Тому мова постачає **текст**, а не розмітку. Тіло локалізованої
 * сторінки — це виклик кількох блоків із локалізованими рядками, і
 * фактична рівність між мовами стає видимою: однакові блоки з різними
 * словами.
 *
 * ## Але не однакові сторінки
 *
 * Стратегія прямо дозволяє мові мати інший порядок розділів і інші
 * приклади: французький намір «audit GEO» не той самий, що англійський
 * «GEO audit». Тому блоки — конструктор, а не шаблон: локаль вільна
 * поставити їх у своєму порядку, додати свій або пропустити чужий.
 * Однаковими лишаються **факти про продукт**, а не композиція.
 *
 * Серверні компоненти. Публічна сторінка має приходити готовим HTML:
 * розмітка, яку домальовує скрипт, для асистента не існує — це знахідка
 * нашого ж двигуна.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import { cx } from "../lib/cx";

/** Смуга на всю ширину з внутрішнім обмеженням по мірі читання. */
export function Section({
  children,
  bordered = true,
  id,
  tight = false,
}: {
  children: ReactNode;
  bordered?: boolean;
  id?: string;
  /**
   * Менші вертикальні поля. Для смуги, яка є ГОЛОВНИМ вмістом сторінки,
   * а не черговим розділом: на сторінці цін порожнє поле над картками
   * відсувало те, заради чого на неї приходять (рішення власника).
   */
  tight?: boolean;
}) {
  return (
    <section id={id} className={cx(bordered && "border-b border-border")}>
      <div
        className={cx(
          "mx-auto max-w-6xl px-5 lg:px-8",
          tight ? "py-7 lg:py-9" : "py-12 lg:py-16",
        )}
      >
        {children}
      </div>
    </section>
  );
}

/**
 * Перший екран: обіцянка ліворуч, доказ праворуч.
 *
 * Доказ поруч із обіцянкою переконує сильніше за обіцянку, після якої
 * треба гортати.
 */
export function Hero({
  eyebrow,
  title,
  lead,
  primary,
  secondary,
  note,
  aside,
  action,
  compact = false,
}: {
  /** Надзаголовок — не обовʼязковий: головна тримає перший екран самим питанням. */
  eyebrow?: string;
  title: string;
  /** Підводка — не обовʼязкова: коли наступну дію пояснює сама форма, текст зайвий. */
  lead?: string;
  primary?: { href: string; label: string };
  secondary?: { href: string; label: string };
  note?: string;
  aside?: ReactNode;
  /**
   * Дія замість кнопок: головна сторінка ставить сюди форму адреси, щоб
   * відвідувач запускав перевірку, не переходячи нікуди. Коли задано —
   * primary/secondary не рендеряться.
   */
  action?: ReactNode;
  /**
   * Стислий перший екран: менші вертикальні поля й жодного порожнього
   * рядка під текстом. Потрібен там, де герой — це рівно заголовок і
   * речення, а головний вміст іде одразу під ним (сторінка цін). Порожній
   * контейнер кнопок додавав 28px до сторінки, на якій кнопок немає.
   */
  compact?: boolean;
}) {
  return (
    <section className="border-b border-border">
      <div
        className={cx(
          "mx-auto grid max-w-6xl items-center gap-9 px-5 lg:px-8",
          compact ? "py-7 lg:py-9" : "py-10 lg:py-16",
          aside ? "lg:grid-cols-[1fr_27rem] lg:gap-16" : "lg:gap-16",
        )}
      >
        <div>
          {eyebrow ? (
            <p className="text-xs font-medium uppercase tracking-wide text-accent-text">
              {eyebrow}
            </p>
          ) : null}
          {/* Ширина міри залежить від того, чи є що поруч: у вузькій
              колонці поруч із прикладом звіту заголовок має вміщатися в
              16 символів рядка, на всю ширину — може дихати. Одна цифра
              на обидва випадки лишає половину екрана порожньою. */}
          <h1
            className={cx(
              "text-balance text-xl font-semibold tracking-tight text-primary",
              "sm:text-2xl lg:text-3xl",
              eyebrow && "mt-3",
              aside ? "max-w-[16ch]" : "max-w-[26ch]",
            )}
          >
            {title}
          </h1>
          {lead ? (
            <p className="mt-4 max-w-measure text-md text-secondary">{lead}</p>
          ) : null}

          {compact && !action && !primary && !secondary ? null : action ? (
            <div className="mt-7">{action}</div>
          ) : (
            <div className="mt-7 flex flex-wrap items-center gap-3">
              {primary ? (
                <Link
                  href={primary.href}
                  className="inline-flex h-12 items-center gap-2 rounded-md bg-brand px-6 text-base font-medium text-brand-ink transition-colors duration-fast hover:bg-brand-hover"
                >
                  {primary.label}
                  <Icon name="arrow-right" />
                </Link>
              ) : null}
              {secondary ? (
                <Link
                  href={secondary.href}
                  className="inline-flex h-12 items-center gap-2 rounded-md px-4 text-base text-accent-text transition-colors duration-fast hover:text-primary"
                >
                  {secondary.label}
                  <Icon name="arrow-down" className="size-4" />
                </Link>
              ) : null}
            </div>
          )}

          {note ? <p className="mt-4 text-sm text-muted">{note}</p> : null}
        </div>

        {aside ? (
          <div id="example" className="scroll-mt-24 lg:justify-self-end">
            {aside}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** Заголовок розділу з підводкою. */
export function Heading({
  title,
  lead,
  level = 2,
  size,
}: {
  title: string;
  lead?: string;
  level?: 2 | 3;
  /**
   * Розмір напису — окремо від рівня, і це не косметика.
   *
   * Поки тег і кегль рахувалися з одного `level`, обрати правильне місце в
   * карті документа означало обрати й більший напис: розділ, який мусив
   * бути `h2`, лишався `h3` рівно тому, що мав виглядати меншим. Структура
   * документа програвала оформленню, і читач з екранним зчитувачем діставав
   * підрозділ підрозділу, якого не існує.
   *
   * Тепер `level` каже, ЩО це в структурі, а `size` — як воно виглядає.
   * `level` і далі означає справжній рівень тега: `3` — це `h3`, і жодне
   * значення не малює тег іншого рівня.
   *
   * Без `size` розмір лишається той, який цей рівень мав завжди, тож жоден
   * наявний виклик не змінює вигляду.
   */
  size?: "xl" | "lg";
}) {
  const Tag = level === 2 ? "h2" : "h3";
  const scale = size ?? (level === 2 ? "xl" : "lg");
  return (
    <>
      <Tag
        className={cx(
          "font-semibold tracking-tight text-primary",
          scale === "xl" ? "text-xl" : "text-lg",
        )}
      >
        {title}
      </Tag>
      {lead ? <p className="mt-3 max-w-measure text-secondary">{lead}</p> : null}
    </>
  );
}

export interface Card {
  icon?: IconName;
  title: string;
  text: string;
  /**
   * Застереження біля обіцянки, а не дрібним шрифтом унизу сторінки:
   * воно й існує, щоб обіцянку читали правильно.
   */
  note?: string;
  href?: string;
}

/** Сітка карток. Клікабельна лише та, у якої є куди вести. */
export function CardGrid({
  cards,
  columns = 3,
}: {
  cards: Card[];
  /**
   * Колонок на широкому екрані. Чотири картки у трьох колонках лишають
   * порожню клітинку кольору рамки — 2×2 для них охайніше.
   */
  columns?: 2 | 3;
}) {
  return (
    <ul
      className={cx(
        "mt-6 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2",
        columns === 3 && "lg:grid-cols-3",
      )}
    >
      {cards.map((card) => (
        <li key={card.title} className="bg-surface">
          <CardInner card={card} />
        </li>
      ))}
    </ul>
  );
}

function CardInner({ card }: { card: Card }) {
  const body = (
    <>
      {card.icon ? <Icon name={card.icon} className="size-5 text-accent" /> : null}
      {/* h2, а не h3: картки стоять одразу під h1 сторінки, і рівень через
          один робив пропуск у структурі (`heading-order`, 9 прогонів із 38).
          Клас той самий, тож розмір і вага лишаються попередніми. */}
      <h2 className="font-medium text-primary">{card.title}</h2>
      <p className="text-sm text-secondary">{card.text}</p>
      {card.note ? <p className="mt-auto pt-2 text-xs text-muted">{card.note}</p> : null}
    </>
  );
  const shape = "flex h-full flex-col gap-2 p-5";
  return card.href ? (
    <Link
      href={card.href}
      className={cx(shape, "transition-colors duration-fast hover:bg-surface-sunken")}
    >
      {body}
    </Link>
  ) : (
    <div className={shape}>{body}</div>
  );
}

/** Пари «твердження — пояснення». Для розділів про принципи. */
export function Definitions({ items }: { items: { term: string; detail: string }[] }) {
  return (
    <dl className="grid gap-px overflow-hidden rounded-lg border border-border bg-border">
      {items.map((row) => (
        <div key={row.term} className="bg-surface p-5">
          <dt className="font-medium text-primary">{row.term}</dt>
          <dd className="mt-1 text-sm text-secondary">{row.detail}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Простий перелік. Для відповіді на питання «що ви побачите у звіті»:
 * там саме перелік, і подавати його картками означало б роздути п'ять
 * коротких рядків до розміру розділу.
 */
export function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="mt-5 flex max-w-measure flex-col gap-2">
      {items.map((item) => (
        <li key={item} className="flex gap-2.5 text-secondary">
          <Icon name="check" className="mt-1 size-4 shrink-0 text-accent" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

/** Абзаци тексту в мірі читання. */
export function Prose({ paragraphs }: { paragraphs: string[] }) {
  return (
    <div className="mt-4 flex max-w-measure flex-col gap-3">
      {paragraphs.map((text) => (
        <p key={text.slice(0, 40)} className="text-secondary">
          {text}
        </p>
      ))}
    </div>
  );
}

/** Посилання «читати далі» — основа перелінковки між сторінками. */
export function More({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="mt-5 inline-flex items-center gap-1.5 text-accent-text hover:text-primary"
    >
      {label}
      <Icon name="arrow-right" className="size-4" />
    </Link>
  );
}

/**
 * Перелік посилань на споріднені сторінки.
 *
 * Не прикраса: сторінка без вихідних посилань лишається сиротою, і це
 * знахідка нашого ж двигуна про неї. Тому блок обовʼязковий на кожній
 * сторінці, крім головної.
 */
export function Related({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string; text: string }[];
}) {
  return (
    <Section bordered={false}>
      <Heading title={title} level={3} />
      <ul className="mt-5 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
        {links.map((link) => (
          <li key={link.href} className="bg-surface">
            <Link
              href={link.href}
              className="flex h-full flex-col gap-1 p-5 transition-colors duration-fast hover:bg-surface-sunken"
            >
              <span className="font-medium text-primary">{link.label}</span>
              <span className="text-sm text-secondary">{link.text}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}
