"use client";

/**
 * Вибір мови.
 *
 * **Без прапорів.** Прапор — це країна, а не мова: іспанською говорять у
 * двадцяти країнах, а в Швейцарії чотири державні мови й один прапор.
 * Прапор поруч зі списком мов рано чи пізно ображає когось із читачів і
 * ніколи нікому не допомагає. Тому глобус і назва мови її ж мовою:
 * «Deutsch», а не «German» — той, хто шукає німецьку, шукає саме перше.
 *
 * ## Дві поведінки, одна кнопка
 *
 * На публічних сторінках мова є частиною адреси (`/de/pricing`), бо її
 * має бачити пошуковик і вміти запропонувати правильну версію. Там
 * перемикач веде посиланням — справжнім, яке можна відкрити в новій
 * вкладці й на яке можна послатися.
 *
 * У кабінеті мова — налаштування людини, а не властивість ресурсу. Там
 * перемикач викликає збереження профілю: обране на ноутбуці має діяти й
 * на телефоні.
 *
 * Різниця в тому, `href` чи `onSelect` передали в компонент.
 */

import Link from "next/link";

import { Icon } from "./Icon";
import { Dropdown, MenuItem, cx } from "./primitives";
import { LOCALE_LABEL } from "../lib/i18n";
import type { Locale } from "../lib/contracts";

interface Props {
  current: Locale;
  /** Мови, які показуємо. Порядок — порядок показу. */
  locales: Locale[];
  /** Публічний режим: адреса версії цією мовою. */
  hrefFor?: (locale: Locale) => string;
  /** Режим кабінету: зберегти вибір у профілі. */
  onSelect?: (locale: Locale) => void;
  /** Підпис кнопки для зчитувача екрана. Приходить перекладеним. */
  label: string;
  compact?: boolean;
}

export function LanguageSwitcher({
  current,
  locales,
  hrefFor,
  onSelect,
  label,
  compact = false,
}: Props) {
  return (
    <Dropdown
      align="end"
      trigger={({ open, toggle }) => (
        <button
          type="button"
          onClick={toggle}
          // Видиме — код мови («EN»), доступна назва була «Language»:
          // голосове керування шукає контрол за тим, що людина ЧИТАЄ, і
          // команда «EN» не знаходила кнопку з іншою назвою (WCAG 2.5.3).
          // У стислому режимі коду не видно, тож там мішатися нема з чим.
          aria-label={compact ? label : `${label}: ${current.toUpperCase()}`}
          aria-expanded={open}
          className={cx(
            "inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm",
            "text-secondary transition-colors duration-fast",
            "hover:bg-surface-sunken hover:text-primary",
          )}
        >
          <Icon name="globe" />
          {/* Код мови великими — короткий і впізнаваний у будь-якій
              писемності. Повна назва стоїть у списку. */}
          {!compact ? (
            <span className="uppercase">{current}</span>
          ) : null}
          <Icon name="chevron-down" className="size-3.5" />
        </button>
      )}
    >
      {locales.map((locale) => {
        const chosen = locale === current;
        const content = (
          <>
            {chosen ? (
              <Icon name="check" className="size-4 text-accent-text" />
            ) : (
              <span className="size-4" aria-hidden />
            )}
            <span className="flex-1 text-start">{LOCALE_LABEL[locale]}</span>
            <span className="text-xs uppercase text-muted">{locale}</span>
          </>
        );

        // Публічний режим — справжнє посилання: його можна відкрити в
        // новій вкладці, скопіювати й надіслати. Кнопка нічого з цього
        // не вміє, а мову сторінки люди пересилають частіше, ніж здається.
        if (hrefFor) {
          return (
            <Link
              key={locale}
              href={hrefFor(locale)}
              hrefLang={locale}
              lang={locale}
              aria-current={chosen ? "true" : undefined}
              className={cx(
                "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm",
                "transition-colors duration-fast hover:bg-surface-sunken",
                chosen ? "text-primary" : "text-secondary",
              )}
            >
              {content}
            </Link>
          );
        }

        return (
          <MenuItem key={locale} onClick={() => onSelect?.(locale)}>
            <span className="flex w-full items-center gap-2" lang={locale}>
              {content}
            </span>
          </MenuItem>
        );
      })}
    </Dropdown>
  );
}
