"use client";

/**
 * Мова службового кабінету для React-дерева.
 *
 * Окремий модуль, а не layout: Next дозволяє сторінці й макету
 * експортувати лише свій перелік імен, і хук поруч із `default` ламає
 * збірку. Цей урок у проєкті вже записаний (`isStaff` у макеті адмінки).
 */

import { createContext, useContext, type ReactNode } from "react";

import { adminText, type AdminLocale } from "./admin-i18n";

interface AdminLocaleState {
  locale: AdminLocale;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const Context = createContext<AdminLocaleState | null>(null);

export function AdminLocaleProvider({
  locale,
  children,
}: {
  locale: AdminLocale;
  children: ReactNode;
}) {
  const value: AdminLocaleState = {
    locale,
    t: (key, params) => adminText(locale, key, params),
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

/** Мова й перекладач службового кабінету. Поза провайдером — англійська. */
export function useAdmin(): AdminLocaleState {
  const value = useContext(Context);
  if (value === null) {
    return { locale: "en", t: (key, params) => adminText("en", key, params) };
  }
  return value;
}
