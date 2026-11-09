/**
 * Чи є рядок власним шляхом сайту — ціллю, на яку можна перенаправити.
 *
 * Перевірки «починається з `/`, але не з `//`» замало: браузер нормалізує
 * `\` у `/` (`/\evil.example` → `//evil.example`) і викидає табуляцію й
 * переноси рядка (`/\t/evil.example`). Тому вирішує не префікс, а те,
 * куди браузер насправді піде: шлях розвʼязується відносно умовного
 * origin, і результат мусить лишитися на ньому.
 */
const PROBE_ORIGIN = "https://origin.invalid";

// Керуючі символи (C0 і DEL): браузер їх мовчки вирізає з адреси.
// eslint-disable-next-line no-control-regex
const CONTROL = /[\u0000-\u001f\u007f]/;

export function localPath(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  if (raw.includes("\\") || CONTROL.test(raw)) return null;
  let resolved: URL;
  try {
    resolved = new URL(raw, PROBE_ORIGIN);
  } catch {
    return null;
  }
  if (resolved.origin !== PROBE_ORIGIN) return null;
  return resolved.pathname + resolved.search + resolved.hash;
}
