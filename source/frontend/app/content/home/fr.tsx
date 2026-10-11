/**
 * Accueil — français. Structure et limites des affirmations comme en en.tsx.
 * Adresse — «vous»: cohérent avec les autres pages françaises.
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
        title="Les moteurs et l'IA voient-ils vraiment votre site ?"
        action={
          <HeroAuditForm
            lang="fr"
            placeholder="votre-site.fr"
            cta="Analyse gratuite"
            invalid="Saisissez l'adresse d'un site web, par exemple example.com."
          />
        }
        aside={<ScorePreview locale="fr" />}
      />

      <Section>
        <Heading title="Une seule analyse du site répond aux trois questions clés sur votre visibilité dans la recherche et l'IA." />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "La recherche vous trouve-t-elle ?",
              text: "Nous vérifions si Google et les autres moteurs de recherche peuvent trouver et lire vos pages.",
              href: "/fr/audit-seo",
            },
            {
              icon: "globe",
              title: "L'IA comprend-elle votre site ?",
              text: "Nous vérifions si l'IA peut lire votre site et comprendre les informations sur votre activité.",
              href: "/fr/visibilite-ia",
            },
            {
              icon: "link",
              title: "L'IA mentionne-t-elle votre marque ?",
              text: "Nous vérifions si ChatGPT, Claude, Perplexity et Gemini citent votre marque dans les réponses sur votre secteur.",
              href: "/fr/visibilite-ia",
            },
          ]}
        />
        <More
          href="/fr/audit-de-site-web"
          label="Toutes les composantes de l'analyse"
        />
      </Section>

      <Section bordered={false}>
        <Heading
          title="Un score de site transparent"
          lead="Vous voyez quelles pages ont été vérifiées, ce qui a pu être mesuré et sur quoi repose le score final."
        />
        <More href="/fr/methodologie" label="Comment fonctionne la mesure" />
      </Section>
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "",
  title: "Crawldy — les moteurs et l'IA voient-ils votre site ?",
  h1: "Les moteurs et l'IA voient-ils vraiment votre site ?",
  description:
    "Crawldy montre ce qui empêche votre site d'être visible dans la recherche et l'IA — et quoi corriger en premier.",
  navLabel: "Accueil",
  Body,
};
