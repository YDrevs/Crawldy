/**
 * Який `X-Forwarded-For` можна передати бекенду від імені клієнта.
 *
 * Ліві записи заголовка пише сам клієнт і підробляє як завгодно; довіряти
 * можна лише тим, що дописали праворуч НАШІ проксі. Тож бекенду їдуть
 * лише останні `trustedProxies` записів — рівно ті, з яких він за тим
 * самим правилом (`TRUSTED_PROXY_COUNT`, N-й справа) візьме справжню
 * адресу. 0 проксі — нічого не пересилаємо: бекенд побачить адресу цього
 * сервера, і всі безскриптові звернення потраплять в одне відро —
 * суворіше за потрібне, але не слабше.
 */
export function trustedForwardedFor(header: string | null, trustedProxies: number): string {
  if (!header || !Number.isInteger(trustedProxies) || trustedProxies <= 0) return "";
  const chain = header
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (chain.length < trustedProxies) return "";
  return chain.slice(-trustedProxies).join(", ");
}

/** `TRUSTED_PROXY_COUNT` із серверного оточення; некоректне — 0. */
export function trustedProxyCount(raw: string | undefined): number {
  const n = Number.parseInt(raw ?? "", 10);
  return Number.isInteger(n) && n >= 0 && n <= 5 ? n : 0;
}
