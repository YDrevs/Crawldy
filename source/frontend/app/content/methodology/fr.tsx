/**
 * Méthodologie — français. Structure selon la décision du propriétaire
 * (écran 06) : couverture → données vérifiées → preuves → score →
 * priorités, avec les « Règles de calcul exactes » du snapshot réel.
 */

import { ScoringRules } from "../../components/ScoringRules";
import { Heading, Hero, Prose, Section } from "../../components/sections";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      <Hero
        eyebrow="Méthodologie"
        title={"Comment Crawldy établit les résultats de l'analyse"}
        lead={"Crawldy ne tire de conclusions que de ce qu'il a réellement pu vérifier. Pour chaque problème détecté, le rapport montre les preuves, le contexte et la logique de sa priorité."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title="D'abord, la couverture" />
            <Prose
              paragraphs={[
                "Crawldy trouve les pages du site et vérifie lesquelles ont pu être chargées et analysées. Le rapport montre le nombre de pages trouvées, vérifiées et inaccessibles.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Seules les données vérifiées comptent" />
            <Prose
              paragraphs={[
                "Si une partie du site ou un indicateur n'a pas pu être vérifié, Crawldy ne met pas de zéro et n'invente pas de résultat. Ces données restent hors du calcul. Si la couverture est insuffisante, aucun score global n'est affiché.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Chaque problème est prouvé" />
            <Prose
              paragraphs={[
                "Pour chaque constat, le rapport montre ce qui a été vérifié, ce qui a été trouvé et sur quelles pages. Cela permet de vérifier la conclusion et de comprendre ce qu'il faut corriger exactement.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="La formation du score" />
            <Prose
              paragraphs={[
                "Les problèmes pèsent différemment sur le résultat. Les violations graves comptent plus que les mineures. Un problème répété sur de nombreuses pages est pris en compte, mais son impact n'est pas multiplié sans limite.",
                "Le score global ne se forme qu'à partir des volets disposant d'assez de données.",
              ]}
            />
          </div>
          <div>
            <Heading level={2} size="lg" title="Quoi corriger en premier" />
            <Prose
              paragraphs={[
                "Crawldy pèse la gravité du problème, le résultat attendu, l'effort de correction et l'importance de la page. Le rapport montre donc tout de suite par où commencer.",
              ]}
            />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title="Règles de calcul exactes" />
        <ScoringRules
          locale="fr"
          strings={{
            caption: "Règles de notation",
            weightsTitle: "Poids des volets",
            severityTitle: "Multiplicateurs de gravité",
            limitsTitle: "Limites",
            modules: {
              seo: "Visibilité dans la recherche",
              performance: "Vitesse et confort",
              ai_ready: "Préparation à l'IA",
              tech: "Bases de sécurité",
              llm_visibility: "Exploitable comme source",
              accessibility: "Accessibilité",
            },
            severities: {
              critical: "Critique",
              high: "Élevée",
              medium: "Moyenne",
              low: "Faible",
              info: "Informative",
            },
            minCoverageLabel: "Texte minimal pour noter le contenu",
            minCoverageValue: "{n} mots sur tout le site",
            repetitionLabel: "Répétition d'un même problème",
            repetitionValue: "au plus ×{n} d'un seul constat",
            shareLabel: "Impact d'un problème sur un volet",
            shareValue: "au plus {p} de la demi-échelle du volet",
          }}
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
  slug: "methodologie",
  title: "Méthodologie — comment Crawldy établit les résultats de l'analyse",
  h1: "Comment Crawldy établit les résultats de l'analyse",
  description:
    "Couverture, données vérifiées, preuves, score et priorités : comment Crawldy mesure un site, avec les règles de calcul exactes.",
  navLabel: "Méthodologie",
  Body,
};
