/**
 * Нормалізація адреси сайту, яку вводить людина.
 *
 * Людина не зобовʼязана знати про протокол: `smartkp.com.ua`,
 * `www.smartkp.com.ua` і `https://smartkp.com.ua` — одна й та сама
 * адреса. Форма приймає всі рівнозначні варіанти й перед запуском
 * перевірки зводить їх до повного URL.
 *
 * Стандартна браузерна валідація тут не годиться двічі: вона вимагає
 * протокол (і відкидає валідний голий домен), а її повідомлення
 * приходить мовою браузера, а не мовою сторінки. Тому форми викликають
 * цю функцію самі, з `noValidate`, і показують власне локалізоване
 * повідомлення.
 */

/** Ім'я хоста, яке схоже на публічний домен: мітки з крапкою між ними. */
const HOST_PATTERN = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/i;

/**
 * Повний URL для перевірки — або `null`, якщо з введеного адреси не
 * вийшло. Голий домен отримує `https://`; `http://` зберігається, бо
 * сайт без TLS — це те, що аудит і має побачити.
 */
export function normalizeSiteUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed || /\s/.test(trimmed)) return null;

  // Схема, відмінна від http/https, — не сайт: ftp://, mailto:, javascript:.
  const scheme = /^([a-z][a-z0-9+.-]*):\/\//i.exec(trimmed);
  if (scheme && !/^https?$/i.test(scheme[1])) return null;
  const withScheme = scheme ? trimmed : `https://${trimmed}`;

  let url: URL;
  try {
    url = new URL(withScheme);
  } catch {
    return null;
  }
  // Адреса сайту не несе облікових даних: «mailto:hi@example.com» без
  // схеми розбирається як userinfo перед хостом — це не сайт.
  if (url.username || url.password) return null;
  // `URL` переводить IDN у punycode, тож перевірка хоста — по ASCII.
  if (!HOST_PATTERN.test(url.hostname)) return null;
  return url.href;
}
