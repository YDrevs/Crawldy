/**
 * Indexabilité — page de référence française.
 *
 * L’une des trois qui méritent en français une page à part : les autres
 * sujets sont traités sur le hub, où ils tiennent en un paragraphe
 * complet. Une page fille vide vaudrait moins qu’un parent solide.
 *
 * Файл згенерований: `scratchpad/content_fr_children.py`.
 */

import {
  Definitions,
  Heading,
  Hero,
  Related,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        eyebrow="Indexabilité"
        title="Quatre façons dont une page accessible échoue à être indexée"
        lead="Être récupérée n’est que le début. Une page peut être accessible, rapide et bien écrite et n’être jamais indexée, pour des raisons toutes invisibles dans un navigateur."
        primary={{ href: "/result", label: "Auditer un site" }}
      />

      <Section>
        <Heading title="Comment cela fonctionne" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Une directive noindex est une instruction, pas un défaut",
                detail:
                  "Elle est respectée, et elle est souvent juste : préproduction, variantes internes, archives minces. Ce qui compte est de savoir si elle était voulue — vous seul pouvez le dire. Le cas qui mérite un second regard est une page que vous liez par ailleurs en évidence.",
              },
              {
                term: "Canonical est une indication forte sur l’identité",
                detail:
                  "Elle dit quelle adresse représente ce contenu. Des signaux contradictoires — une canonical d’un côté, une redirection de l’autre, une sitemap d’un troisième — laissent la décision au robot, et le choix peut ne pas être le vôtre.",
              },
              {
                term: "Les codes de statut portent du sens",
                detail:
                  "Une page introuvable renvoyée en 200 crée une page indexable qui ne dit rien. Une redirection temporaire là où une permanente était voulue laisse les deux adresses vivantes.",
              },
              {
                term: "HTTPS n’est plus optionnel",
                detail:
                  "Une page servie en HTTP simple est un problème critique, pas une remarque : les navigateurs avertissent, et cela sape tous les autres signaux de la page.",
              },
            ]}
          />
        </div>
      </Section>

      <Section>
        <Heading
          title="Là où cela se passe mal"
          lead="Chacun de ces points est signalé par Crawldy sur des sites réels, pas une hypothèse."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Lier une page que vous avez interdite",
                detail:
                  "Un lien interne vers une page que vous avez dit aux moteurs d’ignorer est une contradiction visible seulement quand on vérifie les deux signaux ensemble.",
              },
              {
                term: "Sitemap et canonical en désaccord",
                detail:
                  "Lister une adresse qui se canonicalise vers une autre dit au robot deux choses différentes du même contenu.",
              },
              {
                term: "Des paramètres qui créent une identité",
                detail:
                  "Les paramètres de suivi et de tri produisent des URL distinctes pour le même document, sauf si la canonical dit le contraire.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="À lire aussi"
        links={[
          {
            href: "/fr/developpeurs/crawl",
            label: "Exploration",
            text: "Être récupérée, d’abord.",
          },
          {
            href: "/fr/audit-technique-seo",
            label: "Audit technique SEO",
            text: "Tout cela vérifié sur votre site.",
          },
          {
            href: "/fr/developpeurs",
            label: "Pour les développeurs",
            text: "Les autres notes techniques.",
          },
        ]}
      />
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "indexabilite",
  title: "Indexabilité — noindex, canonical, redirections et codes de statut",
  h1: "Quatre façons dont une page accessible échoue à être indexée",
  description:
    "Pourquoi une page qui répond 200 peut rester absente d’un index : directives robots, conflits de canonical, comportement des redirections et codes de statut qui ne veulent pas dire ce qu’ils semblent dire.",
  navLabel: "Indexabilité",
  Body,
};
