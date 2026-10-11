/**
 * Головна — українська. Побудова та межі тверджень — як в en.tsx.
 * Скорочення — ШІ (не AI): усталена форма решти українських сторінок.
 *
 * Текст — точні формулювання власника (журнал правок, екран 01):
 * без надзаголовка, без пояснення під питанням, три спрощені питання
 * без внутрішньої термінології, «Прозора оцінка сайту».
 */

import { HeroAuditForm } from "../../components/HeroAuditForm";
import { ScorePreview } from "../../components/ScorePreview";
import {
  CardGrid,
  Heading,
  Hero,
  More,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        title="Чи справді пошук і ШІ бачать ваш сайт?"
        action={
          <HeroAuditForm
            placeholder="vash-sait.com"
            cta="Безкоштовна перевірка"
            invalid="Введіть адресу сайту, наприклад example.com."
            lang="uk"
          />
        }
        aside={<ScorePreview locale="uk" />}
      />

      <Section>
        <Heading title="Одна перевірка сайту відповідає на три ключові питання про вашу видимість у пошуку та ШІ." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Чи знаходить вас пошук?",
              text: "Перевіряємо, чи можуть Google та інші пошукові системи знайти й прочитати ваші сторінки.",
              href: "/uk/seo-audit-sajtu",
            },
            {
              icon: "globe",
              title: "Чи розуміє ШІ ваш сайт?",
              text: "Перевіряємо, чи може ШІ прочитати сайт і зрозуміти інформацію про ваш бізнес.",
              href: "/uk/vydymist-v-shi",
            },
            {
              icon: "link",
              title: "Чи згадує ШІ ваш бренд?",
              text: "Перевіряємо, чи називають ваш бренд ChatGPT, Claude, Perplexity і Gemini у відповідях про вашу нішу.",
              href: "/uk/vydymist-v-shi",
            },
          ]}
        />
        <More href="/uk/perevirka-sajtu" label="Усі складові перевірки" />
      </Section>

      <Section bordered={false}>
        <Heading
          title="Прозора оцінка сайту"
          lead="Ви бачите, які сторінки перевірено, що вдалося виміряти та на чому ґрунтується підсумковий бал."
        />
        <More href="/uk/metodolohiia" label="Як влаштоване вимірювання" />
      </Section>
    </>
  );
}

export const uk: LocalizedPage = {
  slug: "",
  title: "Crawldy — чи бачать ваш сайт пошук і ШІ?",
  h1: "Чи справді пошук і ШІ бачать ваш сайт?",
  description:
    "Crawldy показує, що заважає вашому сайту бути видимим у пошуку та ШІ, і що варто виправити насамперед.",
  navLabel: "Головна",
  Body,
};
