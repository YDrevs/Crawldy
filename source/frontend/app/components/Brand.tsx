/**
 * Логотип Crawldy.
 *
 * Показує **оригінальні файли дизайнера** з `public/brand/` і нічого з
 * ними не робить: не перефарбовує, не перемальовує, не міняє пропорцій.
 *
 * Це рішення, а не зручність. Колись тут стояла реконструкція знака з
 * опису — вона виглядала «майже так само», і саме тому була гіршою за
 * відсутність знака. Потім горизонтальний локап складався з двох
 * вирізок, бо дизайнерським був лише вертикальний. Обидві ери минули:
 * тепер обидва локапи — файли дизайнера як є.
 *
 * ## Джерела
 *
 * `crawldy-horizontal.png` — горизонтальний локап дизайнера (знак і
 * напис поруч), даунскейл із оригіналу 4348×876 без інших змін.
 *
 * `crawldy-vertical.png` — вертикальний локап дизайнера (знак над
 * написом), даунскейл із оригіналу 4427×2398.
 *
 * `crawldy-mark.png` і `crawldy-wordmark.png` — точні вирізки з
 * горизонтального файлу, розділені по найширшому прозорому проміжку
 * (299px) між знаком і написом. Жоден піксель знака не змінено.
 *
 * ## Де який
 *
 * Горизонтальний — шапки й рядкові контексти: знак супроводжує
 * навігацію. Вертикальний — там, де знак головний: вхід, каса, порожні
 * стани, публічні сторінки звіту. Сам знак — там, де місця нема зовсім
 * (згорнута панель, футер).
 */

import { cx } from "../lib/cx";

/* Власні розміри файлів. Потрібні браузеру, щоб зарезервувати місце до
 * завантаження — інакше сторінка смикається, коли логотип приходить. */
const MARK = { src: "/brand/crawldy-mark.png", w: 400, h: 385 };
const WORDMARK = { src: "/brand/crawldy-wordmark.png", w: 1200, h: 289 };
const HORIZONTAL = { src: "/brand/crawldy-horizontal.png", w: 1600, h: 322 };
const VERTICAL = { src: "/brand/crawldy-vertical.png", w: 1000, h: 542 };

/** Лише знак. Висота задає розмір, ширина рахується з пропорцій файлу. */
export function Logomark({
  height = 28,
  className,
}: {
  height?: number;
  className?: string;
}) {
  return (
    // Не next/image: той керує розмірами сам, а тут пропорції — частина
    // знака. Звичайний <img> із власними width/height лишає їх точними.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={MARK.src}
      alt=""
      aria-hidden
      width={MARK.w}
      height={MARK.h}
      className={cx("shrink-0", className)}
      style={{ height, width: (height * MARK.w) / MARK.h }}
    />
  );
}

/** Лише напис. */
export function Wordmark({
  height = 18,
  className,
}: {
  height?: number;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={WORDMARK.src}
      alt="Crawldy"
      width={WORDMARK.w}
      height={WORDMARK.h}
      className={cx("shrink-0", className)}
      style={{ height, width: (height * WORDMARK.w) / WORDMARK.h }}
    />
  );
}

/**
 * Горизонтальний локап дизайнера — для шапок.
 *
 * Один файл, як його зробив дизайнер: нічого не складено й не
 * переставлено.
 */
export function Logo({
  height = 28,
  className,
}: {
  height?: number;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={HORIZONTAL.src}
      alt="Crawldy"
      width={HORIZONTAL.w}
      height={HORIZONTAL.h}
      className={cx("shrink-0", className)}
      style={{ height, width: (height * HORIZONTAL.w) / HORIZONTAL.h }}
    />
  );
}

/**
 * Вертикальний локап дизайнера — там, де знак головний, а не супровід:
 * вхід, каса, порожні стани, листи.
 */
export function LogoStacked({
  width = 200,
  className,
}: {
  width?: number;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={VERTICAL.src}
      alt="Crawldy"
      width={VERTICAL.w}
      height={VERTICAL.h}
      className={cx("h-auto", className)}
      style={{ width }}
    />
  );
}
