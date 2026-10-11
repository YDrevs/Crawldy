"use client";

/**
 * Оболонка кабінету: бічна навігація, робоча область, контекстна шапка.
 *
 * Стабільна структура важливіша за красиву: людина, яка щодня заходить
 * подивитися бал сайту, має знаходити те саме на тому самому місці. Тому
 * навігація не згортається сама, не переставляється й не залежить від
 * того, на якій ти сторінці.
 *
 * На вузькому екрані бічна панель стає верхньою смугою, а не
 * висувною шухлядою: розділів пʼять, вони поміщаються, і шухляда додала б
 * один зайвий дотик до кожного переходу.
 *
 * Оболонка адмінки — окрема. Спільними лишаються токени, примітиви й
 * іконки; навігація й припущення про доступ — ні.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useState } from "react";

import { ChangePasswordDialog } from "./ChangePasswordDialog";
import { Icon, type IconName } from "./Icon";
import { Logo } from "./Brand";
import { Button, Dropdown, IconButton, MenuItem } from "./primitives";
import { cx } from "../lib/cx";
import { useLocale } from "../lib/locale";
import { LOCALE_LABEL, COMPLETE_LOCALES, publicHomeHref } from "../lib/i18n";
import { useSiteLocale } from "../lib/site-locale";
import type { Locale } from "../lib/contracts";

interface NavItem {
  href: string;
  icon: IconName;
  labelKey: string;
  /** Підпис для вузького екрана, якщо повний туди не вміщується. */
  shortKey?: string;
}

// «Налаштувань» тут немає: сторінки не існує, а пункт меню, що веде в
// 404, гірший за відсутній. Мова й вихід живуть у меню акаунта.
const NAV: NavItem[] = [
  { href: "/app", icon: "dashboard", labelKey: "nav.dashboard", shortKey: "nav.dashboard.short" },
  { href: "/app/sites", icon: "globe", labelKey: "nav.sites" },
  { href: "/app/audits", icon: "list", labelKey: "nav.audits" },
  { href: "/app/presence", icon: "search", labelKey: "nav.presence" },
  { href: "/app/plan", icon: "card", labelKey: "nav.plan", shortKey: "nav.plan.short" },
];

export function AppShell({
  children,
  email,
  profileLocale,
  onSignOut,
  onLocaleChange,
  onPasswordChanged,
}: {
  children: ReactNode;
  email?: string;
  /**
   * Мова профілю ЯК ВОНА Є, без підстановки англійської.
   *
   * `useLocale()` віддає мову інтерфейсу, а вона вже підставила `en`
   * там, де в профілі порожньо, — і по ній не відрізнити англійця від
   * німця, у якого мови в профілі бути не може. Дорога назад на сайт
   * питає саме профіль, тож вона мусить бачити порожнє порожнім.
   */
  profileLocale?: string;
  onSignOut: () => void;
  onLocaleChange: (locale: Locale) => void;
  /**
   * Пароль змінено. Оболонка лише повідомляє — гасити сесію й вести на
   * форму входу мусить той, хто нею володіє: після зміни всі сесії
   * відкликані, включно з цією, тож лишатися в кабінеті нема на чому.
   */
  onPasswordChanged: () => void;
}) {
  const { t, locale } = useLocale();
  const path = usePathname();
  // Діалог живе на рівні оболонки, а не всередині меню: меню
  // закривається на вибір пункту й забрало б діалог із собою.
  const [changing, setChanging] = useState(false);
  // Мова САЙТУ, а не кабінету: кабінет існує двома мовами, сайт — шістьма,
  // і людина з /de мусить повернутися на /de, а не на англійську головну.
  const site = useSiteLocale(profileLocale);

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Бічна навігація. На вузькому — верхня смуга. */}
      <header
        className={cx(
          "border-border bg-surface",
          "border-b lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-e",
          "lg:sticky lg:top-0 lg:flex lg:flex-col",
        )}
      >
        <div className="flex items-center justify-between gap-4 px-5 py-4">
          {/* Знак веде на САЙТ, а не на головну кабінету: у кабінету є
              власний пункт «Огляд», а дороги назад на сайт не було
              взагалі. Мова — та, якою людина дивилася САЙТ: кабінет
              говорить двома мовами, сайт шістьма, і зашите «/» (як і
              мова профілю) перемикало б німця на англійську. */}
          <Link
            href={publicHomeHref(site)}
            aria-label="Crawldy"
            className="rounded-md"
          >
            <Logo />
          </Link>
          <div className="lg:hidden">
            <AccountMenu
              email={email}
              locale={locale}
              onSignOut={onSignOut}
              onLocaleChange={onLocaleChange}
              onChangePassword={() => setChanging(true)}
            />
          </div>
        </div>

        <nav
          aria-label={t("nav.dashboard")}
          className={cx(
            // На вузькому екрані — сітка на всі п'ять пунктів, а не
            // прокручувана смуга. Смуга ховала «Налаштування» за краєм
            // екрана: розділ, якого не видно, для більшості людей не
            // існує, і жест «прогорни горизонтально» тут ніщо не
            // підказує. П'ять — рівно стільки, скільки вміщується
            // піктограмою з коротким підписом.
            "grid grid-cols-5 gap-1 px-3 pb-3",
            "lg:flex lg:flex-col lg:pb-0",
          )}
        >
          {NAV.map((item) => {
            // Точний збіг для кореня кабінету, префікс — для решти:
            // інакше «Огляд» лишався б підсвіченим на кожній сторінці.
            const active =
              item.href === "/app" ? path === "/app" : path.startsWith(item.href);
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
                {/* Короткий підпис лише там, де довгий не вміщується.
                    Два рядки замість одного — бо це різні слова, а не
                    одне слово різного розміру: обрізати «Тариф і
                    використання» трьома крапками гірше, ніж назвати
                    розділ коротко. */}
                <span className="lg:hidden">{t(item.shortKey ?? item.labelKey)}</span>
                <span className="hidden whitespace-nowrap lg:inline">{t(item.labelKey)}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto hidden border-t border-border p-3 lg:block">
          <AccountMenu
            email={email}
            locale={locale}
            onSignOut={onSignOut}
            onLocaleChange={onLocaleChange}
            onChangePassword={() => setChanging(true)}
            wide
          />
        </div>
      </header>

      <main className="min-w-0 flex-1 bg-background">
        <div className="mx-auto max-w-6xl px-5 py-6 lg:px-8 lg:py-8">{children}</div>
      </main>

      <ChangePasswordDialog
        open={changing}
        onClose={() => setChanging(false)}
        onChanged={() => {
          setChanging(false);
          onPasswordChanged();
        }}
      />
    </div>
  );
}

function AccountMenu({
  email,
  locale,
  onSignOut,
  onLocaleChange,
  onChangePassword,
  wide = false,
}: {
  email?: string;
  locale: Locale;
  onSignOut: () => void;
  onLocaleChange: (locale: Locale) => void;
  onChangePassword: () => void;
  wide?: boolean;
}) {
  const { t } = useLocale();
  return (
    <Dropdown
      align={wide ? "start" : "end"}
      // Широкий варіант стоїть унизу бічної панелі, притиснутий до низу
      // екрана. Меню, розкрите вниз, опинялося за межею вікна цілком:
      // на панелі огляду це рятував скрол сторінки, на довгому звіті —
      // ні, бо панель липка й їде разом із вікном.
      side={wide ? "up" : "down"}
      trigger={({ toggle }) =>
        wide ? (
          <button
            onClick={toggle}
            className={cx(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-start text-sm",
              "text-secondary transition-colors duration-fast hover:bg-surface-sunken hover:text-primary",
            )}
          >
            <Icon name="user" />
            <span className="min-w-0 flex-1 truncate">{email ?? t("nav.account")}</span>
            <Icon name="chevron-down" className="size-3.5" />
          </button>
        ) : (
          <IconButton icon="user" label={t("nav.account")} onClick={toggle} />
        )
      }
    >
      <p className="truncate px-2 py-1.5 text-xs text-muted">{email}</p>
      <div className="my-1 border-t border-border" />
      {COMPLETE_LOCALES.map((code) => (
        <MenuItem
          key={code}
          icon={code === locale ? "check" : undefined}
          onClick={() => onLocaleChange(code)}
        >
          {LOCALE_LABEL[code]}
        </MenuItem>
      ))}
      <div className="my-1 border-t border-border" />
      {/* Профіль людини й далі живе тут: окремої сторінки налаштувань
          немає, а пункт навігації, що веде в 404, гірший за відсутній.
          Шостого пункту в нижній смузі не зʼявилося — сітка на пʼять
          лишилась такою, якою була. */}
      <MenuItem icon="settings" onClick={onChangePassword}>
        {t("password.change")}
      </MenuItem>
      <div className="my-1 border-t border-border" />
      <MenuItem icon="logout" tone="danger" onClick={onSignOut}>
        {t("nav.signOut")}
      </MenuItem>
    </Dropdown>
  );
}

/** Шапка сторінки в робочій області. Контекст, а не другий рівень меню. */
export function PageHeader({
  title,
  description,
  breadcrumb,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  breadcrumb?: { href: string; label: string };
  action?: ReactNode;
}) {
  return (
    <div className="mb-6">
      {breadcrumb ? (
        <Link
          href={breadcrumb.href}
          className="mb-2 inline-flex items-center gap-1 text-sm text-secondary hover:text-primary"
        >
          <Icon name="chevron-right" className="size-3.5 rotate-180" />
          {breadcrumb.label}
        </Link>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-primary">{title}</h1>
          {description ? (
            <p className="mt-1 max-w-measure text-sm text-secondary">{description}</p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}

export { Button };
