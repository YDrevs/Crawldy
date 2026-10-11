/**
 * Каркас юридичної сторінки.
 *
 * Чотири документи в шести мовах мають однакову будову, тож вона живе
 * тут, а не двадцять чотири рази в кожному файлі: заголовок, дата
 * чинності з версією, якірна навігація, розділи, посилання на сусідні
 * документи.
 *
 * ## Чого тут немає
 *
 * Ані карток тарифів, ані повторюваної кнопки «Спробувати
 * безкоштовно», ані будь-якої іншої маркетингової обвʼязки: юридична
 * сторінка допомагає знайти умови, а не веде людину у воронку
 * (специфікація пакета, §10.2). Тому й `SiteCta`, який стоїть унизу
 * решти публічних сторінок, сюди не ставиться.
 *
 * ## Текст не переписується
 *
 * Абзаци, списки й підзаголовки приходять готовими з затвердженого
 * пакета. Єдине, що компонент робить із рядком, — розпізнає провідну
 * жирну мітку («**Дані акаунта.** …»), бо вона є в самому джерелі.
 * Плейсхолдери `[[…]]` лишаються видимими навмисно: їхні значення
 * підставляє власник, і сторінка не має права вдавати, що вони вже є.
 */

import Link from "next/link";

import { Hero, Section } from "./sections";

/** Один блок документа. Більшого в затверджених текстах немає. */
export type LegalBlock =
  | { kind: "para"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "heading"; text: string };

export interface LegalDoc {
  /**
   * `<h1>` сторінки.
   *
   * H1 малює тіло сторінки, а не оболонка — так само, як на решті
   * публічних сторінок. Поле `LocalizedPage.h1` при цьому лишається
   * метаданими; збігатися вони мусять, і за цим стежить тест.
   */
  title: string;
  /** Дата набрання чинності й версія — два рядки з джерела. */
  meta: string[];
  blocks: LegalBlock[];
  /** Підпис якірної навігації. Порожньо — навігації не буде. */
  contentsLabel?: string;
  /** Сусідні документи й контактна сторінка, підписані цією мовою. */
  related: { label: string; href: string }[];
  relatedLabel: string;
}

/** Стійкий якір із заголовка розділу: працює для всіх шести абеток. */
export function anchorOf(text: string, index: number): string {
  const slug = text
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
  return slug ? `${index + 1}-${slug}` : `${index + 1}`;
}

/**
 * Дві розмітки, які є в джерелі, і жодної більше.
 *
 * Провідна мітка абзацу — `**Дані оплати.** решта речення`. Вставка в
 * зворотних лапках — адреса домену або ще не підставлена змінна;
 * лапки службові, на екрані їх бути не має, а сам фрагмент лишається
 * помітним як технічне значення. Загального markdown-парсера тут не
 * треба: більшого в затверджених текстах немає.
 */
function inline(text: string) {
  return text.split(/`([^`]+)`/g).map((part, index) =>
    index % 2 === 1 ? (
      <code key={index} className="font-mono text-[0.95em] text-primary">
        {part}
      </code>
    ) : (
      part
    ),
  );
}

function Para({ text }: { text: string }) {
  const lead = /^\*\*(.+?)\*\*\s*(.*)$/s.exec(text);
  return (
    <p className="mt-4 text-secondary first:mt-0">
      {lead ? (
        <>
          <strong className="font-semibold text-primary">{lead[1]}</strong>{" "}
          {inline(lead[2])}
        </>
      ) : (
        inline(text)
      )}
    </p>
  );
}

export function LegalPage({ doc }: { doc: LegalDoc }) {
  // Вступ документа стоїть до першого підзаголовка — і в джерелі, і на
  // екрані. Зміст після нього, а не перед: перелік розділів раніше за
  // речення про те, що це за документ, читається як зміст порожнечі.
  const first = doc.blocks.findIndex((block) => block.kind === "heading");
  const intro = first < 0 ? doc.blocks : doc.blocks.slice(0, first);
  const body = first < 0 ? [] : doc.blocks.slice(first);
  const headings = body.filter((block) => block.kind === "heading");

  let seen = -1;

  return (
    <>
      {/* Стислий перший екран: заголовок і одразу текст. Підводки під
          H1 немає навмисно — пояснювати юридичний документ рекламним
          реченням означало б додати до нього те, чого в ньому немає. */}
      <Hero title={doc.title} compact />

      <Section>
      {/* Дата чинності й версія стоять одразу під H1: перше, що питають
          у юридичного документа, — чи він чинний. */}
      <p className="text-sm text-muted">
        {doc.meta.map((line) => (
          <MetaLine key={line} text={line} />
        ))}
      </p>

      <div className="mt-6 max-w-measure text-base leading-relaxed">
        {intro.map((block, index) =>
          block.kind === "para" ? (
            <Para key={`i-${index}`} text={block.text} />
          ) : block.kind === "list" ? (
            <ul
              key={`il-${index}`}
              className="mt-4 flex list-disc flex-col gap-2 ps-5 text-secondary"
            >
              {block.items.map((item) => (
                <li key={item}>{inline(item)}</li>
              ))}
            </ul>
          ) : null,
        )}
      </div>

      {doc.contentsLabel && headings.length > 3 ? (
        <nav aria-label={doc.contentsLabel} className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
            {doc.contentsLabel}
          </h2>
          <ul className="mt-3 flex flex-col gap-1.5 text-sm">
            {headings.map((block, order) => (
              <li key={block.kind === "heading" ? block.text : order}>
                <a
                  href={`#${anchorOf(
                    block.kind === "heading" ? block.text : "",
                    order,
                  )}`}
                  className="text-secondary underline-offset-2 hover:text-primary hover:underline"
                >
                  {block.kind === "heading" ? block.text : null}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      {/* Основний текст читабельним кеглем, а не дрібним «юридичним». */}
      <div className="mt-8 max-w-measure text-base leading-relaxed">
        {body.map((block, index) => {
          if (block.kind === "heading") {
            seen += 1;
            return (
              <h2
                key={`h-${index}`}
                id={anchorOf(block.text, seen)}
                className="mt-10 scroll-mt-24 text-lg font-semibold text-primary first:mt-0"
              >
                {block.text}
              </h2>
            );
          }
          if (block.kind === "list") {
            return (
              <ul
                key={`l-${index}`}
                className="mt-4 flex list-disc flex-col gap-2 ps-5 text-secondary"
              >
                {block.items.map((item) => (
                  <li key={item}>{inline(item)}</li>
                ))}
              </ul>
            );
          }
          return <Para key={`p-${index}`} text={block.text} />;
        })}
      </div>

      <nav aria-label={doc.relatedLabel} className="mt-12 border-t border-border pt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
          {doc.relatedLabel}
        </h2>
        <ul className="mt-3 flex flex-col gap-2 text-sm sm:flex-row sm:flex-wrap sm:gap-x-6">
          {doc.related.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="text-secondary underline-offset-2 hover:text-primary hover:underline"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      </Section>
    </>
  );
}

/** `**Версія:** 1.0` — жирна мітка й значення, кожен рядок окремо. */
function MetaLine({ text }: { text: string }) {
  const parsed = /^\*\*(.+?)\*\*\s*(.*)$/s.exec(text);
  const value = (parsed ? parsed[2] : text).replace(/`/g, "");
  return (
    <span className="block">
      {parsed ? <strong className="font-medium">{parsed[1]}</strong> : null}{" "}
      {value}
    </span>
  );
}
