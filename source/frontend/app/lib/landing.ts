/**
 * Хто ця людина для інтерфейсу і куди її вести після входу.
 *
 * Живе окремим модулем, а не в сторінці: Next дозволяє сторінці
 * експортувати лише свій перелік імен, і допоміжна функція поруч із
 * `default` ламає збірку. Плюс так її видно тесту без DOM.
 *
 * Прав ці функції не дають. Кожен службовий маршрут API перевіряє
 * платформну роль сам і віддає 403 незалежно від того, що намалював
 * фронтенд, — тому вгадана адреса нічого не відкриває.
 */

/** Чи має ця людина права команди Crawldy. Порожня роль — ні. */
export function isStaff(role: string | null | undefined): boolean {
  return typeof role === "string" && role.length > 0;
}

// Будь-яке походження, якого не буває насправді: потрібне лише як база,
// щоб побачити, куди браузер розвʼяже відносну адресу.
const PROBE_ORIGIN = "https://local.invalid";

/**
 * Чи це власний шлях сайту, а не чужа адреса.
 *
 * Перевірки «починається з `/`, але не з `//`» мало: браузер читає `\`
 * як `/`, а табуляцію й перенос рядка викидає з адреси, тож `/\evil.com`
 * і `/<TAB>/evil.com` стають `//evil.com`. Тому відкидаємо ці символи й
 * звіряємо, куди адреса розвʼязується насправді.
 */
export function isLocalPath(raw: string): boolean {
  if (!raw.startsWith("/") || raw.startsWith("//")) return false;
  // eslint-disable-next-line no-control-regex
  if (/[\\\u0000-\u001f\u007f]/.test(raw)) return false;
  try {
    return new URL(raw, PROBE_ORIGIN).origin === PROBE_ORIGIN;
  } catch {
    return false;
  }
}

/**
 * Куди йти після входу. Лише власні відносні адреси: зовнішня або
 * протокольно-відносна (`//host`) ціль перетворила б форму входу на
 * відкритий редиректор.
 */
export function safeNext(raw: string | null): string {
  if (!raw || !isLocalPath(raw)) return "/app";
  return raw;
}

/**
 * Куди веде успішний вхід.
 *
 * Явний намір сильніший за роль: людина, яка прийшла з `?next=`, хотіла
 * саме туди — навіть якщо вона з команди, і саме так продовжується
 * перервана входом покупка. Без наміру той, у кого є платформна роль,
 * потрапляє одразу на службову сторінку: окремий кабінет клієнта йому
 * не потрібен (рішення власника 2026-09-05).
 */
export function landingFor(
  role: string | null | undefined,
  requestedNext: string | null,
): string {
  if (!requestedNext) return isStaff(role) ? "/admin" : "/app";
  const target = safeNext(requestedNext);
  // Намір у чужі двері — не намір. Вихід із адмінки лишає в адресі
  // `next=/admin`, і форма входу переживає зміну людини: хто створив
  // НОВИЙ акаунт на тому самому екрані, потрапляв на службову сторінку й
  // бачив «доступно лише команді Crawldy» замість кабінету.
  if (target.startsWith("/admin") && !isStaff(role)) return "/app";
  return target;
}
