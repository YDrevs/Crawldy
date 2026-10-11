/**
 * Єдиний маршрут публічного сайту.
 *
 * Усі мови й усі сторінки проходять тут. Це не економія файлів, а те,
 * що робить розширення дешевим: додати мову або сторінку означає
 * дописати вміст у реєстр — маршрутизацію при цьому не чіпають ніколи.
 * Дерево з окремою текою на локаль довелося б переписувати на кожній
 * новій мові, а слаги в ньому були б іменами тек, тобто перекладом
 * англійських слів замість пошукового наміру.
 *
 * `generateStaticParams` перелічує реальні адреси з реєстру, тож кожна
 * сторінка збирається наперед: публічний вміст має приходити готовим
 * HTML, і це та сама вимога, яку ми ставимо клієнтам.
 *
 * Адреси, якої в реєстрі немає, не існує — 404, а не англійський
 * запасний варіант під чужомовною адресою.
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PublicShell } from "../components/PublicShell";
import { JsonLd } from "../components/JsonLd";
import { alternatesOf, canonicalOf, localesOf, resolvePath } from "../lib/pages";
import { allRoutes } from "../lib/pages";
import { pageGraph } from "../lib/schema";

export const dynamicParams = false;

export function generateStaticParams(): { path: string[] }[] {
  return allRoutes().map(({ path }) => ({
    // Порожній масив — корінь. Next очікує саме його для `/`.
    path: path.split("/").filter(Boolean),
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ path?: string[] }>;
}): Promise<Metadata> {
  const { path } = await params;
  const found = resolvePath(path ?? []);
  if (found === null) return {};

  const { key, locale, page } = found;
  return {
    // `absolute`, бо публічні заголовки написані цілком: у них уже є
    // бренд там, де він потрібен. Шаблон кореня додавав другий, і
    // виходило «… ? · Crawldy» — брендів два, місця у видачі менше.
    title: { absolute: page.title },
    description: page.description,
    alternates: {
      canonical: canonicalOf(key, locale) ?? undefined,
      languages: alternatesOf(key),
    },
    openGraph: {
      type: "website",
      locale,
      siteName: "Crawldy",
      url: canonicalOf(key, locale) ?? undefined,
      title: page.title,
      description: page.description,
      // Єдиний офіційний брендовий асет із репозиторію. Пропорція
      // близька до очікуваної OG (1.85:1 проти 1.91:1) — краще за
      // відсутню картку й чесніше за згенерований банер.
      images: [
        {
          url: "/brand/crawldy-vertical.png",
          width: 1000,
          height: 542,
          alt: "Crawldy",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: page.title,
      description: page.description,
      images: ["/brand/crawldy-vertical.png"],
    },
  };
}

export default async function PublicPage({
  params,
}: {
  params: Promise<{ path?: string[] }>;
}) {
  const { path } = await params;
  const found = resolvePath(path ?? []);
  if (found === null) notFound();

  const { key, locale, page } = found;
  const Body = page.Body;

  return (
    <PublicShell locale={locale} pageKey={key} locales={localesOf(key)}>
      <JsonLd graph={pageGraph(key, locale)} />
      <Body />
    </PublicShell>
  );
}
