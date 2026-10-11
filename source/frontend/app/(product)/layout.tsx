import type { Metadata } from "next";

import { Document } from "../document";

/**
 * Корінь кабінету й входу.
 *
 * Мова тут не в адресі: вона в профілі людини й перемикається без зміни
 * URL, бо мова не є частиною ресурсу в кабінеті. Тому `<html lang>`
 * лишається англійським — це мова каркаса до того, як ми дізналися, хто
 * увійшов. Мову вмісту виставляє `LocaleProvider` нижче.
 *
 * Окремий корінь від публічного сайту навмисно: там мова визначається
 * адресою й мусить бути видимою пошуковику, тут — ні. Один корінь на
 * обидва випадки мусив би вгадувати, і вгадував би неправильно для
 * половини сторінок.
 */

export const metadata: Metadata = {
  title: {
    default: "Crawldy",
    template: "%s · Crawldy",
  },
  // Не індексувати, але посилання лишити живими: `nofollow` на сторінці
  // входу обрізав би шлях назад на публічний сайт без жодного виграшу.
  // Приватні сторінки кабінету й так за автентифікацією та за
  // забороною в robots.txt.
  robots: { index: false, follow: true },
};

export default function ProductRootLayout({ children }: { children: React.ReactNode }) {
  return <Document lang="en">{children}</Document>;
}
