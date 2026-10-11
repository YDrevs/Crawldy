"use client";

/**
 * Мова інтерфейсу для React-дерева.
 *
 * Порядок той самий, що на бекенді, і це не збіг: обидва боки мусять
 * розвʼязувати мову однаково, інакше сторінка виявиться однією мовою, а
 * знахідки на ній — іншою.
 *
 *     явний вибір → користувач → організація → англійська
 *
 * Явний вибір тут — перемикач у шапці. Він живе в стані, а не в адресі:
 * мова не є частиною ресурсу в кабінеті. На публічних сторінках буде
 * інакше — там мова в адресі, бо її має бачити пошуковик.
 */

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import type { Locale } from "./contracts";
import { direction, formatDate, plural, translate } from "./i18n";

interface LocaleState {
  locale: Locale;
  dir: "ltr" | "rtl";
  t: (key: string, params?: Record<string, string | number>) => string;
  /** Рядок із числівником у правильній формі. Див. `i18n.plural`. */
  n: (key: string, count: number, params?: Record<string, string | number>) => string;
  /** Дата мовою інтерфейсу, а не мовою браузера. */
  d: (iso: string) => string;
}

const Context = createContext<LocaleState | null>(null);

export function LocaleProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  const t = useCallback(
    (key: string, params?: Record<string, string | number>) =>
      translate(locale, key, params),
    [locale],
  );
  const value = useMemo<LocaleState>(
    () => ({
      locale,
      dir: direction(locale),
      t,
      n: (key, count, params) => plural(locale, key, count, params),
      d: (iso) => formatDate(locale, iso),
    }),
    [locale, t],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useLocale(): LocaleState {
  const value = useContext(Context);
  if (value === null) {
    // Дефолт замість винятку: примітив, показаний поза провайдером (у
    // сторісі, у тесті), має малюватися, а не валити сторінку.
    return {
      locale: "en",
      dir: "ltr",
      t: (key, params) => translate("en", key, params),
      n: (key, count, params) => plural("en", key, count, params),
      d: (iso) => formatDate("en", iso),
    };
  }
  return value;
}

/** Скорочення для найчастішого випадку. */
export function useT() {
  return useLocale().t;
}
