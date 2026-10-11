/**
 * Hub développeurs — français.
 *
 * Trois pages filles seulement : `crawler web` (1 300/mois),
 * `indexabilité` (KD 11) et l’accès des robots d’IA, porté par la
 * demande large autour de la visibilité dans les moteurs de réponse.
 * robots.txt, rendu, données structurées et notation sont traités ici
 * même — une page fille vide vaudrait moins qu’un parent solide.
 *
 * Файл згенерований із каркаса `scratchpad/core_template.py`: спільною є
 * лише структура, слова написані під цю мову окремо.
 */

import {
  CardGrid,
  Definitions,
  Heading,
  Hero,
  More,
  Prose,
  Related,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero
        eyebrow="Pour les développeurs"
        title="Comment les moteurs et les robots d’IA lisent réellement un site"
        lead="Notes sur la mécanique : ce qu’un robot reçoit, ce qu’il peut analyser, et où les deux publics divergent. À partir de ce que Crawldy observe sur des sites réels, pas de ce que promettent les spécifications."
        primary={{ href: "/result", label: "Auditer un site" }}
      />

      <Section>
        <Heading
          title="Une requête, deux lecteurs très différents"
          lead="Les deux récupèrent la même URL. Ce qui suit n’est pas la même chose, et presque tout constat technique d’un audit vit dans cet écart."
        />
        <Prose
          paragraphs={[
            "Un robot de moteur met votre page en file d’attente pour le rendu, exécute le JavaScript et indexe ce que le navigateur a produit. Un robot d’IA peut ne rien faire de tout cela — beaucoup récupèrent le HTML, l’analysent et passent à la suite. Aucun de ces comportements n’est universel, et les éditeurs les changent sans prévenir.",
            "La question pratique n’est donc pas « mon site fonctionne-t-il » mais « quelle part de mon site survit à chaque chemin ».",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Pages dédiées"
          lead="Trois sujets ont assez de matière propre pour une page à part entière."
        />
        <CardGrid
          cards={[
            {
              icon: "globe",
              title: "Exploration",
              text: "Comment un robot découvre les pages, ce qui le limite, et pourquoi une sitemap est une indication et non une instruction.",
              href: "/fr/developpeurs/crawl",
            },
            {
              icon: "link",
              title: "Robots d’IA",
              text: "Quels agents récupèrent pour les moteurs de réponse, en quoi ils diffèrent de la recherche, et pourquoi bloquer l’un ne bloque pas l’autre.",
              href: "/fr/developpeurs/robots-ia",
            },
            {
              icon: "search",
              title: "Indexabilité",
              text: "noindex, canonical, redirections et codes de statut — les quatre façons dont une page accessible échoue à être indexée.",
              href: "/fr/developpeurs/indexabilite",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="En bref"
          lead="Ces sujets n’ont pas en français de demande propre justifiant une page séparée. Ils ne disparaissent pas pour autant."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "robots.txt",
                detail:
                  "Elle régit la récupération, pas l’indexation : une URL interdite peut apparaître dans les résultats si assez de liens externes y mènent, adresse indexée sans contenu. Les groupes s’appliquent par agent, le plus spécifique l’emporte et n’hérite de rien. La panne la plus fréquente est invisible : une page d’erreur renvoyée avec le statut 200 est analysée comme des directives, n’en trouve aucune, et tout devient autorisé.",
              },
              {
                term: "Rendu JavaScript",
                detail:
                  "Deux versions de chaque page coexistent : le HTML envoyé par votre serveur et le DOM après exécution des scripts. Les moteurs savent rendre ; beaucoup de robots d’IA peut-être pas. Ce qui disparaît le plus souvent : le texte après hydratation, le JSON-LD injecté par script, et la navigation dessinée par le framework.",
              },
              {
                term: "Données structurées",
                detail:
                  "Du JSON-LD dans le HTML, pas ajouté après coup. Organization sert d’ancre, sameAs vous relie à ce qui est déjà connu ailleurs, et des identifiants stables font d’un ensemble de blocs un graphe plutôt que plusieurs choses sans rapport. Un balisage qui contredit la page visible vaut moins que pas de balisage du tout.",
              },
              {
                term: "Notation",
                detail:
                  "La pénalité est le poids multiplié par la gravité ; deux plafonds limitent ce qu’un seul problème peut coûter ; l’échelle est hyperbolique et n’atteint jamais zéro. Une dimension non mesurable quitte le calcul au lieu de devenir zéro. Les poids exacts sont publiés dans la méthodologie.",
              },
            ]}
          />
        </div>
        <More href="/fr/methodologie" label="La notation en détail dans la méthodologie" />
      </Section>

      <Section>
        <Heading
          title="Notre propre robot"
          lead="Si vous regardez vos journaux, c’est nous — et voici ce que nous autorisons sur notre propre site."
        />
        <Prose
          paragraphs={[
            "Notre robot s’identifie dans le User-Agent et respecte robots.txt. Il suit les redirections jusqu’à une petite limite, borne la taille des réponses et n’envoie jamais rien. S’il a été refusé, votre rapport le dit au lieu de deviner un contenu qu’il n’a jamais reçu.",
            "Sur crawldy.ai nous autorisons les robots de recherche et de découverte, autorisons les agents d’IA qui récupèrent pour répondre à une question, et refusons les agents qui collectent du contenu pour l’entraînement de modèles. Google-Extended est traité comme une décision distincte et non comme une partie de la recherche — le bloquer ne coûte rien dans Google Search, et confondre les deux est une erreur courante et coûteuse.",
          ]}
        />
      </Section>
      <Related
        title="À lire aussi"
        links={[
          {
            href: "/fr/methodologie",
            label: "Méthodologie",
            text: "Comment mesure, couverture et confiance s’articulent.",
          },
          {
            href: "/fr/audit-technique-seo",
            label: "Audit technique SEO",
            text: "La même mécanique, vérifiée sur votre site.",
          },
          {
            href: "/fr/visibilite-ia",
            label: "Visibilité IA",
            text: "Accès, compréhension et exploitation comme source.",
          },
        ]}
      />
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "developpeurs",
  title: "Pour les développeurs — comment moteurs et robots d’IA lisent un site",
  h1: "Comment les moteurs et les robots d’IA lisent réellement un site",
  description:
    "Notes de référence sur l’exploration, robots.txt, l’accès des robots d’IA, le rendu JavaScript, l’indexabilité, les données structurées et la notation — d’après ce que Crawldy observe sur des sites réels.",
  navLabel: "Développeurs",
  Body,
};
