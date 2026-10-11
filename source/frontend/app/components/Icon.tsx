/**
 * Іконки. Один набір, одні правила.
 *
 * Правила, які роблять набір набором, а не колекцією картинок:
 *
 * - сітка 24, обведення 1.5, `currentColor` — іконка бере колір тексту
 *   поруч і не потребує власного токена;
 * - лише обведення, без заливок: змішувати два стилі в одному рядку
 *   інтерфейсу видно навіть тому, хто не знає, що дивиться;
 * - розмір задається класом (`size-4`), а не атрибутом: інакше половина
 *   іконок виявиться на пів пікселя іншою;
 * - декоративна іконка має `aria-hidden`, змістовна — `title`. Іконка,
 *   яка є єдиним підписом кнопки, мусить мати назву, інакше кнопка для
 *   зчитувача екрана безіменна.
 *
 * Набір навмисно малий. Кожна нова іконка — рішення, а не «хай буде»:
 * тридцять іконок, з яких вживаються вісім, роблять інтерфейс схожим на
 * панель керування, а не на продукт.
 */

import type { SVGProps } from "react";

export type IconName =
  | "dashboard"
  | "globe"
  | "list"
  | "clock"
  | "card"
  | "settings"
  | "plus"
  | "search"
  | "filter"
  | "chevron-down"
  | "chevron-right"
  | "arrow-right"
  | "arrow-up"
  | "arrow-down"
  | "check"
  | "close"
  | "alert"
  | "info"
  | "download"
  | "link"
  | "external"
  | "refresh"
  | "trash"
  | "user"
  | "logout";

/** Шляхи в системі координат 24×24. */
const PATHS: Record<IconName, string> = {
  dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  globe: "M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c2.5 2.4 3.8 5.4 3.8 9S14.5 18.6 12 21c-2.5-2.4-3.8-5.4-3.8-9S9.5 5.4 12 3z",
  list: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  clock: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3.5 2",
  card: "M3 7.5A2.5 2.5 0 015.5 5h13A2.5 2.5 0 0121 7.5v9a2.5 2.5 0 01-2.5 2.5h-13A2.5 2.5 0 013 16.5zM3 10h18M7 15h3",
  settings:
    "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7 1.1V21a2 2 0 11-4 0v-.1A1.6 1.6 0 007.5 19.4l-.1.1a2 2 0 11-2.8-2.8l.1-.1A1.6 1.6 0 003 13.9H3a2 2 0 110-4h.1A1.6 1.6 0 004.6 7.5l-.1-.1a2 2 0 112.8-2.8l.1.1A1.6 1.6 0 0010 3.1V3a2 2 0 114 0v.1a1.6 1.6 0 002.7 1.1l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8v.1a1.6 1.6 0 001.5 1h.2a2 2 0 110 4h-.2a1.6 1.6 0 00-1.3 1z",
  plus: "M12 5v14M5 12h14",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3",
  filter: "M3 5h18M6 12h12M10 19h4",
  "chevron-down": "M6 9l6 6 6-6",
  "chevron-right": "M9 6l6 6-6 6",
  "arrow-right": "M5 12h14M13 6l6 6-6 6",
  "arrow-up": "M12 19V5M6 11l6-6 6 6",
  "arrow-down": "M12 5v14M6 13l6 6 6-6",
  check: "M4 12.5l5 5L20 6.5",
  close: "M6 6l12 12M18 6L6 18",
  alert: "M12 8v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  info: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 11v5M12 8h.01",
  download: "M12 3v12M7 11l5 5 5-5M4 20h16",
  link: "M10 13a5 5 0 007.5.5l3-3a5 5 0 00-7-7l-1.7 1.7M14 11a5 5 0 00-7.5-.5l-3 3a5 5 0 007 7L12.2 19",
  external: "M14 4h6v6M20 4l-9 9M18 14v5a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h5",
  refresh: "M20 12a8 8 0 11-2.3-5.6M20 4v5h-5",
  trash: "M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2M6 7l1 13a1 1 0 001 1h8a1 1 0 001-1l1-13",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM5 21a7 7 0 0114 0",
  logout: "M15 12H4M8 8l-4 4 4 4M13 4h5a2 2 0 012 2v12a2 2 0 01-2 2h-5",
};

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  /** Назва для зчитувача екрана. Без неї іконка декоративна. */
  title?: string;
}

export function Icon({ name, title, className = "size-4", ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}

export const ICON_NAMES = Object.keys(PATHS) as IconName[];
