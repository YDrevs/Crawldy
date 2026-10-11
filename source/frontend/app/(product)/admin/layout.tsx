"use client";

/**
 * Службові екрани команди Crawldy. Окремий маршрут, окрема оболонка.
 *
 * ## Чому не всередині кабінету
 *
 * Кабінет належить клієнтові, і службова сторінка не має на нього
 * впливати: ані пункту меню, ані зайвого рядка в чужому інтерфейсі
 * (рішення власника 2026-09-05). Тому `/admin` живе поруч із `/app`, а
 * не в ньому: у нього власна оболонка, і кабінет про нього не знає.
 *
 * ## Права дає сервер, а не ця перевірка
 *
 * Тут вирішується лише, що малювати. Кожен службовий маршрут API
 * перевіряє платформну роль сам і віддає 403 незалежно від того, що
 * показав фронтенд, — саме тому вгаданий URL нічого не дає. Людина без
 * ролі бачить чесну відмову, а не порожній екран і не 404.
 *
 * ## Мова
 *
 * Дві: українська й англійська. Вибір зберігається в браузері
 * адміністратора — профіль керує клієнтським кабінетом і публічним
 * сайтом, і службова сторінка не має права його переписувати.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { AdminShell } from "../../components/AdminShell";
import { logout } from "../../lib/api";
import { LogoStacked } from "../../components/Brand";
import { Alert, Spinner } from "../../components/primitives";
import {
  adminText,
  initialAdminLocale,
  rememberAdminLocale,
  type AdminLocale,
} from "../../lib/admin-i18n";
import { AdminLocaleProvider } from "../../lib/admin-locale";
import { publicHomeHref } from "../../lib/i18n";
import { useSiteLocale } from "../../lib/site-locale";
import { isStaff } from "../../lib/landing";
import type { Locale } from "../../lib/contracts";
import { SessionProvider, useSession } from "../../lib/session";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <Guard>{children}</Guard>
    </SessionProvider>
  );
}

/** Мова сайту з профілю, або англійська. */
function Guard({ children }: { children: ReactNode }) {
  const { me, loading, clear } = useSession();
  const router = useRouter();
  const [locale, setLocale] = useState<AdminLocale>("en");
  // Мова САЙТУ (шість), окремо від мови службового кабінету (дві).
  const site = useSiteLocale(me?.user?.locale);

  useEffect(() => {
    // Не увійшов — на форму входу з наміром повернутися сюди й мовою,
    // якою людина дивилася сайт.
    if (!loading && me === null) {
      router.replace(`/login?next=%2Fadmin&lang=${site}`);
    }
  }, [loading, me, router, site]);

  useEffect(() => {
    if (me) setLocale(initialAdminLocale(me.user?.locale));
  }, [me]);

  if (loading || me === null) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const t = (key: string, params?: Record<string, string | number>) =>
    adminText(locale, key, params);

  if (!isStaff(me.user?.platform_role)) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center gap-6 px-6 py-12">
        <div className="flex justify-center">
          <LogoStacked />
        </div>
        <Alert tone="danger">{t("shell.denied")}</Alert>
        {/* Посилання лишається САМЕ тут: людина без платформної ролі
            прийшла не туди, і їй потрібна дорога назад. Тому, хто має
            права, кабінет не потрібен — у нього своя сторінка. */}
        <Link href="/app" className="text-center text-sm text-accent hover:underline">
          {t("shell.back")}
        </Link>
      </main>
    );
  }

  return (
    <AdminLocaleProvider locale={locale}>
      <AdminShell
        email={me.user?.email}
        locale={locale}
        onLocale={(next) => {
          setLocale(next);
          rememberAdminLocale(next);
        }}
        onSignOut={() => {
          // Той самий вихід, що в кабінеті: сесія на сервері закривається,
          // форма входу відкривається мовою, якою людина щойно працювала.
          void logout().then(() => {
            clear();
            router.replace(`/login?lang=${site}`);
          });
        }}
        homeHref={publicHomeHref(site)}
        t={t}
      >
        {children}
      </AdminShell>
    </AdminLocaleProvider>
  );
}
