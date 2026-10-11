"use client";

/**
 * Шапка публічних сторінок.
 *
 * Клієнтський компонент — рівно через дві речі, які без стану не
 * зробити: розкривне меню мов і меню на вузькому екрані. Решта
 * публічної частини лишається серверною.
 *
 * ## У шапці немає другої кнопки запуску перевірки
 *
 * Кнопка «Перевірити сайт», що зʼявлялась після прокручування, прибрана
 * рішенням власника: це зайвий повторний CTA. Головна дія живе біля
 * поля адреси на сторінці, а навігаційний пункт «Що перевіряємо» веде
 * на пояснення складу перевірки.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "./Icon";
import { PublicAccount, type AccountLabels } from "./PublicAccount";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { Logo } from "./Brand";
import type { Locale } from "../lib/contracts";
import type { PageKey } from "../lib/page-types";
import { pathOf } from "../lib/pages";
import { rememberSiteLocale } from "../lib/site-locale";

export interface NavLink {
  href: string;
  label: string;
}

export function PublicHeader({
  product,
  locale,
  locales,
  pageKey,
  home,
  account,
  aria,
}: {
  /** Три пункти колонки «Продукт» — той самий порядок, що в футері. */
  product: NavLink[];
  locale: Locale;
  /** Мови, якими існує саме ця сторінка. */
  locales: Locale[];
  pageKey: PageKey;
  /** Адреса головної цією мовою: логотип веде туди, а не завжди в «/». */
  home: string;
  /** Написи шапки приходять готовими: вона не має власного каталогу. */
  account: AccountLabels;
  aria: { nav: string; language: string; menu: string };
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  // Кабінет не має мовного префікса в адресі, тож дорогу назад на сайт
  // будувати нема з чого. Остання публічна сторінка лишає мову тут.
  useEffect(() => {
    rememberSiteLocale(locale);
  }, [locale]);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
      {/* Проміжок 32px розводить логотип і навігацію — але навігація
          нижче за `lg` схована, а проміжок лишався. На 320px це давало
          рівно 1.14px за межу вікна: 20 (відступ) + 149 (знак) + 32
          (проміжок) + 120 (мова й меню) = 321. Знак і кнопки при цьому
          не завеликі — зайвим був сам проміжок, бо `ms-auto` і так
          притискає групу праворуч. Нижче за `lg` він менший; на
          десктопі, де навігація є, лишається той самий. */}
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3 lg:gap-8 lg:px-8">
        <Link href={home} aria-label="Crawldy" className="shrink-0">
          <Logo height={30} />
        </Link>

        <nav aria-label={aria.nav} className="hidden gap-0.5 lg:flex">
          {product.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="whitespace-nowrap rounded-md px-3 py-2 text-sm text-secondary transition-colors duration-fast hover:bg-surface-sunken hover:text-primary"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ms-auto flex items-center gap-1">
          {/* Перемикач веде на **цю саму сторінку** іншою мовою, а не
              на головну: людина, яка читає сторінку про аудит і обирає
              німецьку, хоче ту саму сторінку німецькою. Мови, якою
              сторінки немає, у списку немає взагалі. */}
          <LanguageSwitcher
            current={locale}
            locales={locales}
            hrefFor={(next) => pathOf(pageKey, next) ?? home}
            label={aria.language}
          />

          {/* Вхід стоїть завжди — спокійним посиланням, яке ні з чим не
              змагається. Мова їде з ним: форма входу існує всіма шістьма.
              Хто вже увійшов, бачить тут своє імʼя: невидима сесія
              міняла поведінку кнопок, не пояснюючи чому. */}
          <PublicAccount locale={locale} labels={account} />

          <button
            type="button"
            onClick={() => setMenuOpen((was) => !was)}
            aria-expanded={menuOpen}
            aria-controls="public-menu"
            aria-label={aria.menu}
            className="inline-flex size-9 items-center justify-center rounded-md text-secondary hover:bg-surface-sunken hover:text-primary lg:hidden"
          >
            <Icon name={menuOpen ? "close" : "list"} />
          </button>
        </div>
      </div>

      {/* Меню на вузькому екрані. Розділи й мова тут же: ховати мову в
          третій рівень означає, що її не знайде той, кому вона потрібна
          найбільше. */}
      {menuOpen ? (
        <nav
          id="public-menu"
          aria-label={aria.menu}
          className="border-t border-border bg-surface px-5 py-3 lg:hidden"
        >
          <ul className="flex flex-col">
            {product.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-md px-2 py-2.5 text-base text-secondary hover:bg-surface-sunken hover:text-primary"
                >
                  {link.label}
                </Link>
              </li>
            ))}
            <li className="mt-2 border-t border-border pt-2">
              <PublicAccount
                locale={locale}
                labels={account}
                variant="menu"
                onNavigate={() => setMenuOpen(false)}
              />
            </li>
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
