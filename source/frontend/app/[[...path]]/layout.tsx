import type { Metadata } from "next";

import { Document } from "../document";
import { ORIGIN } from "../lib/entity";
import { localeOfPath } from "../lib/pages";
import { RTL_LOCALES } from "../lib/i18n";

/**
 * Корінь публічного сайту — і причина, чому він стоїть саме тут.
 *
 * `<html lang>` мусить називати мову сторінки: `lang="en"` над
 * українським текстом бреше і читалці з екрана, і пошуковику. Але
 * кореневий layout у теці `app/` не бачить параметрів маршруту, тож
 * узяти мову йому нізвідки.
 *
 * Вихід — той самий, що в офіційному підході Next до багатомовності:
 * кореневий layout живе **під динамічним сегментом**. Тоді він отримує
 * шлях і виводить мову з нього. Різниця лише в тому, що сегмент у нас
 * необовʼязковий, — саме це й лишає англійську в корені без `/en/`.
 *
 * Кабінет має власний корінь (`app/(product)/layout.tsx`): там мова
 * береться з профілю, а не з адреси, і спільний корінь мусив би вгадати
 * обидва випадки одним значенням.
 */

export const metadata: Metadata = {
  // База для відносних адрес у метаданих (og:image тощо): без неї Next
  // не може зібрати абсолютну адресу картки на статичній збірці.
  metadataBase: new URL(ORIGIN),
  title: {
    default: "Crawldy",
    template: "%s · Crawldy",
  },
};

export default async function PublicRootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ path?: string[] }>;
}) {
  const { path } = await params;
  const locale = localeOfPath(path ?? []);
  return (
    <Document lang={locale} dir={RTL_LOCALES.includes(locale) ? "rtl" : "ltr"}>
      {children}
    </Document>
  );
}
