/**
 * Exploration — page de référence française.
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
        eyebrow="Exploration"
        title="Comment un robot décide quoi récupérer, et ce qui l’arrête"
        lead="La découverte est un parcours de graphe avec un budget. Sitemaps, priorités et cadence modifient ce parcours, ils ne le remplacent pas."
        primary={{ href: "/result", label: "Auditer un site" }}
      />

      <Section>
        <Heading title="Comment cela fonctionne" />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Les liens sont la carte principale",
                detail:
                  "Un robot part de quelque part et suit ce qu’il trouve. Une page vers laquelle rien ne pointe n’est atteignable que si autre chose lui signale son existence — c’est à cela que sert une sitemap, et c’est pourquoi une page orpheline listée s’y comporte quand même autrement qu’une page liée.",
              },
              {
                term: "Une sitemap est une indication",
                detail:
                  "Y figurer ne garantit pas la récupération, en être absent ne l’empêche pas. Les dates de modification ne servent que si elles signifient quelque chose : un fichier où chaque entrée annonce aujourd’hui ne porte aucune information.",
              },
              {
                term: "Les budgets sont réels et finis",
                detail:
                  "Personne ne lit un grand site intégralement à chaque passage. Ce qui est lu est un échantillon, et lequel compte énormément — le début d’une sitemap est ce que le CMS a écrit en premier, soit des milliers d’URL produit sur une boutique et aucune des pages qui expliquent l’activité.",
              },
              {
                term: "La profondeur coûte de la découverte",
                detail:
                  "Les pages éloignées de l’entrée sont récupérées plus tard et moins souvent. Ce n’est pas une règle de classement, c’est de l’arithmétique : un parcours avec budget atteint le proche en premier.",
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
                term: "Les URL à facettes mangent le budget",
                detail:
                  "Les paramètres de filtre et de tri multiplient une page en centaines. Vues de l’extérieur, ce sont des URL distinctes au contenu presque identique, et le robot dépense son budget à prouver que c’est la même chose.",
              },
              {
                term: "Des réponses lentes qui ressemblent à un refus",
                detail:
                  "Un robot avec un délai d’attente traite une page lente comme indisponible. Le temps de réponse du serveur n’est pas qu’une mesure de vitesse — au-delà d’un seuil, il devient un problème de découverte.",
              },
              {
                term: "Les chaînes de redirection",
                detail:
                  "Chaque saut coûte une requête et certains clients abandonnent avant la fin. Une chaîne de trois qui finit en 404 est invisible dans un navigateur, où elle ressemble à un lien mort ordinaire.",
              },
            ]}
          />
        </div>
      </Section>

      <Related
        title="À lire aussi"
        links={[
          {
            href: "/fr/developpeurs/indexabilite",
            label: "Indexabilité",
            text: "Récupérée ne veut pas dire indexée.",
          },
          {
            href: "/fr/audit-technique-seo",
            label: "Audit technique SEO",
            text: "La même mécanique, vérifiée sur votre site.",
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
  slug: "crawl",
  title: "Exploration — comment les robots découvrent et récupèrent vos pages",
  h1: "Comment un robot décide quoi récupérer, et ce qui l’arrête",
  description:
    "Comment fonctionne la découverte, pourquoi une sitemap est une indication et non une instruction, ce qu’un budget de pages signifie sur un grand site, et comment une exploration s’arrête discrètement.",
  navLabel: "Exploration",
  Body,
};
