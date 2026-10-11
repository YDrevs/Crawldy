/**
 * Єдиний CTA інформаційних сторінок — унизу, перед футером.
 *
 * Один блок на шість сторінок замість власної кнопки на кожній: верхні
 * й проміжні заклики прибрані рішенням власника, бо повторний CTA не
 * подвоює переконливості, а робить сторінку схожою на оголошення.
 *
 * Текст навмисно називає МЕЖУ безкоштовного: бал, покриття та три
 * головні проблеми — і прямо каже, що повна аналітика та перевірка
 * згадок у ШІ живуть у повному звіті. Обіцяти превʼю як повний звіт
 * означало б продати те, чого в ньому немає.
 */

import Link from "next/link";

import { Icon } from "./Icon";

export function SiteCta({
  title,
  text,
  cta,
  href,
}: {
  title: string;
  text: string;
  cta: string;
  /** Канонічний шлях запуску перевірки, з мовою сторінки. */
  href: string;
}) {
  return (
    <section className="border-t border-border bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-5 py-12 lg:flex-row lg:items-center lg:justify-between lg:px-8 lg:py-14">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-primary">
            {title}
          </h2>
          <p className="mt-2 max-w-measure text-secondary">{text}</p>
        </div>
        <Link
          href={href}
          className="inline-flex h-12 shrink-0 items-center gap-2 self-start rounded-md bg-brand px-6 text-base font-medium text-brand-ink transition-colors duration-fast hover:bg-brand-hover lg:self-auto"
        >
          {cta}
          <Icon name="arrow-right" />
        </Link>
      </div>
    </section>
  );
}
