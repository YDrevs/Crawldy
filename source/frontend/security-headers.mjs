/**
 * Заголовки безпеки фронтенду. Окремий модуль, щоб їх бачив тест.
 *
 * Next обчислює `headers()` під час ЗБІРКИ і вшиває результат у маніфест
 * маршрутів, тож `HSTS_ENABLED` і `NEXT_PUBLIC_API_URL` мусять бути в
 * оточенні `next build`, а не лише `next start`.
 *
 * Порядок масиву — це порядок у відповіді, і він навмисно сталий:
 * інакше порівняння двох збірок показувало б різницю там, де її немає.
 *
 * `X-Frame-Options` стосується того, чи може ЧУЖИЙ сайт показати нашу
 * сторінку в рамці. Накладна каса Paddle і віджет Turnstile — це їхні
 * рамки в нашій сторінці, і `DENY` на наших відповідях їх не торкається.
 *
 * Три дозволи в `Permissions-Policy` порожні, бо жодна функція продукту
 * не просить камери, мікрофона чи геолокації.
 */

const PADDLE = ["https://cdn.paddle.com", "https://*.paddle.com"];
const TURNSTILE = "https://challenges.cloudflare.com";

/**
 * CSP у два шари.
 *
 * Примусово — лише директиви, які не залежать від переліку джерел і тому
 * не можуть мовчки зламати касу чи челендж: заборона показувати нас у
 * чужій рамці, підміни `<base>`, плагінів і відправки форм на чужий
 * домен.
 *
 * Повна політика з переліком джерел іде як `Report-Only`: сторінки
 * віддають інлайнові стилі й інлайновий бутстрап Next, тягнуть Paddle і
 * Turnstile, і вмикати її примусово можна лише після того, як консоль
 * браузера на живому домені покаже, що порушень немає.
 */
const ENFORCED_CSP = [
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "object-src 'none'",
  "form-action 'self'",
].join("; ");

function originOf(url) {
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

function fullCsp(apiUrl) {
  const api = originOf(apiUrl ?? "");
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline' ${PADDLE[0]} ${TURNSTILE}`,
    `style-src 'self' 'unsafe-inline' ${PADDLE[0]}`,
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    `connect-src 'self'${api ? ` ${api}` : ""} ${PADDLE.join(" ")} ${TURNSTILE}`,
    `frame-src ${PADDLE.join(" ")} ${TURNSTILE}`,
    ENFORCED_CSP,
  ].join("; ");
}

/**
 * @param {{ hsts?: boolean, apiUrl?: string }} options
 * @returns {{ key: string, value: string }[]}
 */
export function securityHeaders({ hsts = false, apiUrl } = {}) {
  const headers = [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=()" },
    { key: "Content-Security-Policy", value: ENFORCED_CSP },
    { key: "Content-Security-Policy-Report-Only", value: fullCsp(apiUrl) },
  ];
  // HSTS — лише на справжньому домені з HTTPS: поставлений наосліп, він
  // або не робить нічого, або замикає браузер на схему, якої сайт не
  // віддає. Без `preload`: включення в список браузерів — окреме рішення.
  if (hsts) {
    headers.push({ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" });
  }
  return headers;
}
