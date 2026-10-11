/**
 * Robots d’IA — page de référence française.
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
        eyebrow="Robots d’IA"
        title="Les robots d’IA ne sont pas un public, ni une seule décision"
        lead="Trois choses différentes arrivent sur votre serveur et s’appellent toutes robots d’IA. Les traiter comme une seule politique est la façon la plus courante de perdre une visibilité qu’on voulait garder."
        primary={{ href: "/result", label: "Auditer un site" }}
      />

      <Section>
        <Heading title="Comment cela fonctionne" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Récupération pour une réponse",
                detail:
                  "Un agent récupère votre page parce que quelqu’un a posé une question à laquelle il veut répondre, souvent en citant la source. C’est le plus proche de la recherche : le renvoi et l’attribution sont la raison de l’autoriser.",
              },
              {
                term: "Collecte pour l’entraînement",
                detail:
                  "Un agent rassemble du contenu dans un jeu de données. Pas de question, pas de citation, pas de visite. L’autoriser est un choix légitime, mais c’est un autre choix, et il mérite d’être fait délibérément.",
              },
              {
                term: "Des robots de recherche qui alimentent aussi l’IA",
                detail:
                  "Le robot qui indexe pour la recherche peut aussi alimenter une fonction d’IA du même produit. Le bloquer vous coûte la recherche.",
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
                term: "Prendre Google-Extended pour un réglage de recherche",
                detail:
                  "Ce n’en est pas un. Il régit l’usage de votre contenu dans les produits d’IA de Google ; il n’affecte ni Googlebot, ni l’indexation, ni le classement. Des sites bloquent Googlebot en croyant se retirer de l’IA, et perdent la recherche.",
              },
              {
                term: "Supposer que le JavaScript sera exécuté",
                detail:
                  "Beaucoup d’agents récupèrent et analysent le HTML sans exécuter de scripts. Si votre contenu n’apparaît qu’après le rendu, il leur manque — et aucun balisage ne répare un contenu jamais reçu.",
              },
              {
                term: "Supposer qu’une règle reste vraie",
                detail:
                  "Les identifiants d’agent changent, de nouveaux apparaissent, et le comportement est documenté de façon inégale. Une politique écrite une fois et jamais revue finit par ne plus vouloir dire ce qu’elle voulait dire.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="À lire aussi"
        links={[
          {
            href: "/fr/audit-geo",
            label: "Audit GEO",
            text: "Ce qui est mesurable, et ce qui ne l’est pas.",
          },
          {
            href: "/fr/visibilite-ia",
            label: "Visibilité IA",
            text: "Ce que nous mesurons sur votre site — et ce que nous ne mesurons pas.",
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
  slug: "robots-ia",
  title: "Robots d’IA — moteurs de réponse, entraînement, et la différence",
  h1: "Les robots d’IA ne sont pas un public, ni une seule décision",
  description:
    "Quels agents récupèrent pour les moteurs de réponse, en quoi ils diffèrent des robots de recherche et des collecteurs d’entraînement, et pourquoi une seule règle ne peut pas exprimer ces trois décisions.",
  navLabel: "Robots d’IA",
  Body,
};
