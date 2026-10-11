/**
 * Главная — русская. Структура и границы утверждений — как в en.tsx.
 * Сокращение — ИИ: единая форма остальных русских страниц.
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
        title="Видят ли поиск и ИИ ваш сайт на самом деле?"
        action={
          <HeroAuditForm
            lang="ru"
            placeholder="vash-sajt.com"
            cta="Бесплатная проверка"
            invalid="Введите адрес сайта, например example.com."
          />
        }
        aside={<ScorePreview locale="ru" />}
      />

      <Section>
        <Heading title="Одна проверка сайта отвечает на три ключевых вопроса о вашей видимости в поиске и ИИ." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Находит ли вас поиск?",
              text: "Проверяем, могут ли Google и другие поисковые системы найти и прочитать ваши страницы.",
              href: "/ru/seo-audit-sajta",
            },
            {
              icon: "globe",
              title: "Понимает ли ИИ ваш сайт?",
              text: "Проверяем, может ли ИИ прочитать сайт и понять информацию о вашем бизнесе.",
              href: "/ru/vidimost-v-ii",
            },
            {
              icon: "link",
              title: "Упоминает ли ИИ ваш бренд?",
              text: "Проверяем, называют ли ChatGPT, Claude, Perplexity и Gemini ваш бренд в ответах о вашей нише.",
              href: "/ru/vidimost-v-ii",
            },
          ]}
        />
        <More href="/ru/proverka-sajta" label="Все составляющие проверки" />
      </Section>

      <Section bordered={false}>
        <Heading
          title="Прозрачная оценка сайта"
          lead="Вы видите, какие страницы проверены, что удалось измерить и на чём основан итоговый балл."
        />
        <More href="/ru/metodologiya" label="Как устроено измерение" />
      </Section>
    </>
  );
}

export const ru: LocalizedPage = {
  slug: "",
  title: "Crawldy — видят ли ваш сайт поиск и ИИ?",
  h1: "Видят ли поиск и ИИ ваш сайт на самом деле?",
  description:
    "Crawldy показывает, что мешает вашему сайту быть видимым в поиске и ИИ, — и что исправлять первым.",
  navLabel: "Главная",
  Body,
};
