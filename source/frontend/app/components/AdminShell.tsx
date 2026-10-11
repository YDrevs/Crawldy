"use client";

/**
 * Оболонка службового кабінету: бічна навігація, робоча область.
 *
 * Структурний принцип той самий, що в кабінеті клієнта (`AppShell`):
 * ліворуч сталий перелік розділів, на вузькому екрані — верхня смуга,
 * активний пункт видно. Спільними лишаються токени, примітиви й іконки;
 * сама навігація — окрема, бо це інший продукт для іншої людини й із
 * іншими припущеннями про доступ.
 *
 * Мова тут своя: дві (українська, англійська) і живе вона в браузері
 * адміністратора, а не в профілі. Профіль керує клієнтським кабінетом
 * і публічним сайтом; службова сторінка не має права його переписувати.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import { LogoStacked } from "./Brand";
import { Dropdown, IconButton, MenuItem } from "./primitives";
import { cx } from "../lib/cx";
import {
  ADMIN_LOCALES,
  ADMIN_LOCALE_LABEL,
  type AdminLocale,
} from "../lib/admin-i18n";

interface AdminNavItem {
  href: string;
  icon: IconName;
  key: string;
}

/**
 * Пʼять розділів. «Ціни» веде на корінь `/admin`: сторінка цін існувала
 * до цієї оболонки, і переносити її адресу заради симетрії означало б
 * зачепити працюючий екран без потреби.
 */
export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/admin/payment", icon: "card", key: "nav.payment" },
  { href: "/admin", icon: "list", key: "nav.pricing" },
  { href: "/admin/ai", icon: "settings", key: "nav.ai" },
  { href: "/admin/payments", icon: "card", key: "nav.payments" },
  { href: "/admin/analytics", icon: "dashboard", key: "nav.analytics" },
  { href: "/admin/testing", icon: "refresh", key: "nav.testing" },
];

export function AdminShell({
  children,
  email,
  locale,
  onLocale,
  onSignOut,
  homeHref,
  t,
}: {
  children: ReactNode;
  email?: string;
  locale: AdminLocale;
  onLocale: (locale: AdminLocale) => void;
  onSignOut: () => void;
  /** Головна сайту мовою людини — знак веде туди, як і в кабінеті. */
  homeHref: string;
  t: (key: string) => string;
}) {
  const path = usePathname();

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <header
        className={cx(
          "border-border bg-surface",
          "border-b lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-e",
          "lg:sticky lg:top-0 lg:flex lg:flex-col",
        )}
      >
        <div className="flex items-center justify-between gap-4 px-5 py-4">
          <Link href={homeHref} aria-label="Crawldy" className="rounded-md">
            <LogoStacked width={104} />
          </Link>
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-border px-2 py-0.5 text-2xs uppercase tracking-wide text-muted">
              {t("shell.title")}
            </span>
            <div className="lg:hidden">
              <AccountMenu
                email={email}
                locale={locale}
                onLocale={onLocale}
                onSignOut={onSignOut}
                t={t}
              />
            </div>
          </div>
        </div>

        <nav
          aria-label={t("shell.title")}
          className={cx(
            "grid grid-cols-5 gap-1 px-3 pb-3",
            "lg:flex lg:flex-col lg:pb-0",
          )}
        >
          {ADMIN_NAV.map((item) => {
            // Точний збіг для кореня, префікс — для решти: інакше «Ціни»
            // лишалися б підсвіченими на кожній сторінці розділу.
            const active =
              item.href === "/admin" ? path === "/admin" : path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex flex-col items-center gap-1 rounded-md px-1 py-2 text-center text-2xs",
                  "lg:flex-row lg:gap-2.5 lg:px-3 lg:text-start lg:text-sm",
                  "transition-colors duration-fast",
                  active
                    ? "bg-surface-sunken font-medium text-primary"
                    : "text-secondary hover:bg-surface-sunken hover:text-primary",
                )}
              >
                <Icon name={item.icon} className="size-5 lg:size-4" />
                <span className="leading-tight">{t(item.key)}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto hidden border-t border-border p-3 lg:block">
          <AccountMenu
            email={email}
            locale={locale}
            onLocale={onLocale}
            onSignOut={onSignOut}
            t={t}
            wide
          />
        </div>
      </header>

      <main className="min-w-0 flex-1 bg-background">
        <div className="mx-auto max-w-6xl px-5 py-6 lg:px-8 lg:py-8">{children}</div>
      </main>
    </div>
  );
}

/** Мова й вихід. Широкий варіант стоїть унизу липкої панелі й відкривається вгору. */
function AccountMenu({
  email,
  locale,
  onLocale,
  onSignOut,
  t,
  wide = false,
}: {
  email?: string;
  locale: AdminLocale;
  onLocale: (locale: AdminLocale) => void;
  onSignOut: () => void;
  t: (key: string) => string;
  wide?: boolean;
}) {
  return (
    <Dropdown
      align={wide ? "start" : "end"}
      // Унизу липкої панелі меню, розкрите вниз, вийшло б за межу вікна.
      side={wide ? "up" : "down"}
      trigger={({ toggle }) =>
        wide ? (
          <button
            onClick={toggle}
            className={cx(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-start text-sm",
              "text-secondary transition-colors duration-fast",
              "hover:bg-surface-sunken hover:text-primary",
            )}
          >
            <Icon name="user" />
            <span className="min-w-0 flex-1 truncate">{email}</span>
            <Icon name="chevron-down" className="size-3.5" />
          </button>
        ) : (
          <IconButton icon="user" label={email ?? t("shell.title")} onClick={toggle} />
        )
      }
    >
      {ADMIN_LOCALES.map((code) => (
        <MenuItem
          key={code}
          icon={code === locale ? "check" : undefined}
          onClick={() => onLocale(code)}
        >
          {ADMIN_LOCALE_LABEL[code]}
        </MenuItem>
      ))}
      <div className="my-1 border-t border-border" />
      <MenuItem icon="logout" tone="danger" onClick={onSignOut}>
        {t("shell.signOut")}
      </MenuItem>
    </Dropdown>
  );
}

