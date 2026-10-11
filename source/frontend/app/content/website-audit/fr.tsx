/**
 * Ce que nous vérifions — français. Structure comme en en.tsx (журнал
 * правок, екран 02) : introduction → six volets (cartes non
 * interactives) → comment se forme le score → quoi corriger en premier
 * → pied de page.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      <Hero
        eyebrow="Audit de site web"
        title="Analyse de site pour la recherche et l’IA"
        lead="Crawldy vérifie votre site sur six dimensions et montre ce qu’il vaut mieux corriger en premier. Pour chaque problème, le rapport donne les preuves et les pages concernées."
      />

      <Section>
        <Heading
          title="Les six volets de la vérification"
          lead="Crawldy vérifie la visibilité du site dans la recherche et l'IA, sa vitesse, la sécurité de base et l'accessibilité."
        />
        <CardGrid
          cards={[
            {
              icon: "search",
              title: "Visibilité dans la recherche",
              text: "Nous vérifions si les moteurs de recherche peuvent trouver et lire vos pages, s’il existe des signaux techniques susceptibles de gêner l’indexation, et si la structure du site et les liens posent problème.",
            },
            {
              icon: "clock",
              title: "Vitesse et confort",
              text: "Nous vérifions la vitesse de chargement des pages, la réponse du serveur et ce qui peut ralentir le site. Quand des données d'utilisateurs réels existent, nous en tenons compte.",
            },
            {
              icon: "globe",
              title: "Préparation à l'IA",
              text: "Nous vérifions si l'IA peut reconnaître correctement votre entreprise, ses pages, ses contacts et d'autres informations importantes.",
            },
            {
              icon: "link",
              title: "Exploitable comme source",
              text: "Nous vérifions si le site contient des réponses claires, une paternité indiquée et assez de contexte pour que l'IA puisse l'utiliser comme source.",
            },
            {
              icon: "alert",
              title: "Bases de sécurité",
              text: "Nous vérifions HTTPS, les réglages de sécurité, la protection des formulaires et le bon traitement des erreurs techniques. Ce n'est pas une recherche de vulnérabilités.",
            },
            {
              icon: "user",
              title: "Accessibilité",
              text: "Nous vérifions les problèmes courants qui peuvent gêner l'utilisation du site. C'est une vérification automatique, pas une certification WCAG.",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Comment se forme le score du site"
          lead="Le résultat dépend non seulement des problèmes trouvés, mais aussi de la part du site qui a pu être vérifiée. C'est pourquoi Crawldy affiche la couverture à côté du score."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "La couverture est visible d'emblée",
                detail:
                  "Nous montrons combien de pages ont été trouvées, chargées et vérifiées, et combien sont restées inaccessibles.",
              },
              {
                term: "Ce qui n'est pas mesuré ne baisse pas le score",
                detail:
                  "Le score n'est calculé que pour les volets mesurés. Quand les données manquent, Crawldy le dit clairement au lieu de mettre un zéro.",
              },
              {
                term: "Pas assez de données — pas de score",
                detail:
                  "Si une part trop faible du site a été vérifiée, Crawldy n'affiche pas de score global peu fiable. Les constats disponibles restent dans le rapport comme observations.",
              },
              {
                term: "Chaque conclusion peut être vérifiée",
                detail:
                  "Pour chaque problème, nous montrons ce que nous attendions, ce que nous avons trouvé et sur quelles pages. Cela permet de vérifier le résultat et de corriger plus vite.",
              },
            ]}
          />
        </div>
      </Section>

      <Section bordered={false}>
        <Heading
          title="Quoi corriger en premier"
          lead="Crawldy classe les problèmes par priorité, selon leur gravité, l'effet attendu, l'effort de correction et l'importance de la page. Vous voyez tout de suite par où commencer."
        />
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
  slug: "audit-de-site-web",
  title: "Audit de site web : un rapport, six dimensions, des preuves",
  h1: "Analyse de site pour la recherche et l’IA",
  description:
    "Un outil d'audit de site web qui couvre la visibilité dans la recherche, la préparation à l'IA, la vitesse, les bases de sécurité et l'accessibilité — avec la couverture et une preuve sous chaque constat.",
  navLabel: "Ce que nous vérifions",
  Body,
};
