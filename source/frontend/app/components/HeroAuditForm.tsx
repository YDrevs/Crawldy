"use client";

/**
 * Форма адреси в герої головної.
 *
 * Не другий шлях аудиту, а вхід у канонічний: сабміт веде на
 * `/result?url=…`, і саме той екран відкриває гостьову сесію та ставить
 * аудит — один шлях, один код, одна черга.
 *
 * Адреса нормалізується тут-таки: людина не мусить знати про протокол,
 * `smartkp.com.ua` — валідний вхід. Валідація контрольована застосунком
 * (`noValidate`), бо стандартна браузерна підказка приходить мовою
 * браузера, а не мовою сторінки, — і вимагала б протокол.
 *
 * На вузькому екрані поле і кнопка стають у стовпчик: рядок, у якому
 * кнопка вужча за палець, — це форма, якою не користуються.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icon } from "./Icon";
import { normalizeSiteUrl } from "../lib/site-url";

export function HeroAuditForm({
  placeholder,
  cta,
  invalid,
  lang,
}: {
  placeholder: string;
  cta: string;
  /** Локалізоване повідомлення про непридатну адресу — мовою сторінки. */
  invalid: string;
  /** Мова гостьового екрана — будь-яка з шести мов сайту; без неї екран англійський. */
  lang?: string;
}) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const target = normalizeSiteUrl(url);
    if (target === null) {
      setError(true);
      return;
    }
    const params = new URLSearchParams({ url: target });
    if (lang) params.set("lang", lang);
    router.push(`/result?${params.toString()}`);
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className="w-full max-w-xl"
    >
      <div className="flex w-full flex-col gap-3 sm:flex-row">
        <input
          type="text"
          inputMode="url"
          autoComplete="url"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
            if (error) setError(false);
          }}
          placeholder={placeholder}
          aria-label={placeholder}
          aria-invalid={error || undefined}
          className="h-12 min-w-0 flex-1 rounded-md border border-border bg-surface px-4 text-base text-primary outline-none focus:border-accent"
        />
        <button
          type="submit"
          className="inline-flex h-12 shrink-0 items-center justify-center gap-2 rounded-md bg-brand px-6 text-base font-medium text-brand-ink transition-colors duration-fast hover:bg-brand-hover"
        >
          {cta}
          <Icon name="arrow-right" />
        </button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {invalid}
        </p>
      ) : null}
    </form>
  );
}
