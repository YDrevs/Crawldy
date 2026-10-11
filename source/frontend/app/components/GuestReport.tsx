"use client";

/**
 * Обвʼязка оплаченого гостьового звіту — спільна для двох входів.
 *
 * Той самий куплений звіт відкривається двома дверима: живою гостьовою
 * сесією (`/result`) і постійним платним посиланням (`/report/[token]`),
 * яке переживає сесію. Обвʼязка в них одна — завантаження файлів тим
 * самим токеном і пропозиція акаунта після цінності, — і живе вона
 * тут, щоб два входи не розійшлися у два продукти.
 */

import Link from "next/link";

import { Icon } from "./Icon";
import { Panel } from "./primitives";
import { useLocale } from "../lib/locale";

/**
 * Завантаження гостя — постійним платним посиланням, не маршрутом
 * кабінету: у гостя немає сесії, його право — спроможність. Формати —
 * лише ті, що справді існують: Word і JSON.
 */
export function GuestDownloads({ token }: { token: string }) {
  const { t } = useLocale();
  const formats = [
    { format: "docx-general", label: t("result.downloadGeneral") },
    { format: "docx-technical", label: t("result.downloadTechnical") },
    { format: "json", label: t("result.downloadJson") },
  ];
  return (
    <div className="flex items-center gap-2">
      {formats.map((item) => (
        <a
          key={item.format}
          // Мови в адресі немає навмисно: вона заморожена в самому посиланні
          // при видачі, і сервер її звідти й читає. Параметр лише вдавав би
          // вибір, якого тут не існує.
          href={`/r/${token}?format=${item.format}`}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-secondary transition-colors duration-fast hover:bg-surface-sunken hover:text-primary"
        >
          <Icon name="download" className="size-4" />
          {item.label}
        </a>
      ))}
    </div>
  );
}

/**
 * Акаунт пропонується після цінності, не перед нею. Звіт уже повністю
 * доступний; реєстрація нічого не відмикає й ні до чого не зобовʼязує,
 * і текст не натякає, що посилання зникне без неї.
 */
export function AccountCta() {
  const { t, locale } = useLocale();
  return (
    <Panel className="mt-8 border-accent/40">
      <p className="text-sm text-foreground">{t("free.accountCta")}</p>
      <div className="mt-2">
        {/* Мова їде на форму входу: український гість, що дочитав свій
            звіт, не має реєструватися англійською. */}
        <Link
          href={`/login?lang=${locale}`}
          className="text-sm font-medium text-accent hover:underline"
        >
          {t("free.accountLink")}
        </Link>
      </div>
    </Panel>
  );
}
