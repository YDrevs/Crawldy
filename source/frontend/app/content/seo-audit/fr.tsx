/**
 * seo-audit — fr. Структура затвердженої пропозиції E2 (2026-09-05):
 * надзаголовок, H1 і одне речення підводки → три етапи, кожен — питання
 * і два речення (що перевіряємо / що покаже звіт) → «Що дає звіт» двома
 * реченнями → спільний нижній CTA. Три етапи більше не називаються тричі.
 *
 * Розведено те, що спостерігається: доступність для обходу й сигнали
 * індексованості. Фактичну індексацію Crawldy не бачить — сторінка каже
 * це прямо й не називає виключену сторінку «випадково» виключеною:
 * сигнал ми читаємо, намір — ні.
 */

import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      <Hero
        eyebrow={"Audit SEO"}
        title={"Les moteurs de recherche peuvent-ils trouver et comprendre votre site ?"}
        lead={"Cette partie de la vérification répond à trois questions dans l’ordre : le moteur atteint-il la page, la page porte-t-elle des signaux contre l’indexation, et est-il clair de quoi elle parle."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Le moteur peut-il atteindre vos pages"} lead={"Nous vérifions robots.txt, les liens internes, la profondeur des pages, les réponses du serveur, HTTPS et les chaînes de redirections. Le rapport liste les adresses précises qu’un moteur risque de ne pas atteindre, avec la raison pour chacune."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. Y a-t-il des signaux qui gênent l’indexation"} lead={"Nous vérifions noindex, canonical, le plan du site et les contradictions entre ces signaux. Ils montrent s’il existe des indices techniques susceptibles de gêner l’indexation. Si une page est réellement indexée, Crawldy ne le détermine pas."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Est-il clair de quoi parle la page"} lead={"Nous vérifions les titres, les descriptions, le H1, la structure du texte, les textes des liens et les pages au contenu trop mince. Pour chaque problème, le rapport indique sur quelles pages il a été trouvé."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Ce que le rapport vous apporte"} lead={"Sous chaque constat, nous montrons ce que nous attendions, ce que nous avons réellement vu et sur quelles pages cela a été trouvé. Nous classons les problèmes par priorité en tenant compte de la gravité, de l’effet attendu, de l’effort de correction et de l’importance de la page."} />
      </Section>

      <SiteCta
        title={cta.title}
        text={cta.text}
        cta={cta.cta}
        href={cta.href}
      />
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "audit-seo",
  title: "Audit SEO — exploration, indexation et compréhension de vos pages",
  h1: "Les moteurs de recherche peuvent-ils trouver et comprendre votre site ?",
  description:
    "Trois étapes de la visibilité dans la recherche en un rapport : si les moteurs peuvent atteindre vos pages, les indexer et les comprendre — avec une preuve par constat.",
  navLabel: "Audit SEO",
  Body,
};
