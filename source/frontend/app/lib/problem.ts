/**
 * Помилка бекенда → ключ каталогу для клієнта.
 *
 * ## Сирий рядок сервера — не текст для людини
 *
 * Бекенд віддає причини машинними кодами (`quota.exhausted`,
 * `checkout.unavailable`), українськими службовими рядками («невірна
 * пошта або пароль») або голими статусами. Жоден із них не можна
 * рендерити як є: код — жаргон, службовий рядок — однією мовою на всі
 * інтерфейси, а UNREACHABLE ще й несе адресу API. Спіймано наживо:
 * гість із вичерпаною квотою бачив на екрані «quota.exhausted».
 *
 * ## Правило одне
 *
 * Відомий код або статус → свій ключ; УСЕ невідоме → короткий
 * локалізований загальний ключ. Невідома помилка ніколи не показує
 * сирого значення — краще сказати «щось пішло не так», ніж навчити
 * клієнта читати наші нутрощі.
 *
 * Це шар подання: HTTP-статус і поведінка застосунку не змінюються,
 * перекладається лише те, що бачить людина.
 */

import { ApiError } from "./api";

/** Машинні коди гостьового API → ключі каталогу.

Коду `quota.exhausted` тут немає, і не тому, що його забули перекласти:
механізм «один безкоштовний аудит на сесію» прибраний із продукту —
превʼю необмежені, а межу зловживання тримає технічний ліміт частоти
зі своїм 429. Контекстні 402 кабінету мапляться overrides викликача. */
const CODE_KEYS: Record<string, string> = {
  "checkout.unavailable": "problem.checkout",
  "already.unlocked": "problem.alreadyUnlocked",
  "not.found": "problem.notFound",
};

/** Статуси, які мають власний зміст без огляду на тіло відповіді. */
const STATUS_KEYS: Record<number, string> = {
  0: "state.offline",
  404: "problem.notFound",
  429: "problem.tooMany",
};

/**
 * Ключ каталогу для помилки. `overrides` — контекстні значення за
 * статусом: 402 на екрані присутності означає «немає перевірок
 * присутності», а не «немає аналізів», і словами це різні речення.
 */
export function problemKey(
  problem: unknown,
  overrides: Record<number, string> = {},
): string {
  const message =
    problem instanceof Error ? problem.message : String(problem ?? "");
  const byCode = CODE_KEYS[message];
  if (byCode) return byCode;
  if (problem instanceof ApiError) {
    const byStatus = overrides[problem.status] ?? STATUS_KEYS[problem.status];
    if (byStatus) return byStatus;
    if (problem.status >= 500) return "problem.server";
  }
  return "problem.generic";
}
