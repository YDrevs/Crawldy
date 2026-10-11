/**
 * Audit GEO — français.
 *
 * La France est le seul marché de l’échantillon où `audit GEO` (210,
 * KD 10) et `audit IA` (480, KD 16) sont à la fois réels et peu
 * disputés. La page nomme donc ces termes directement, là où l’allemand
 * devait encore expliquer la catégorie.
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
        eyebrow="Audit GEO"
        title="L’optimisation pour moteurs génératifs, sans ce que personne ne peut mesurer"
        lead="GEO est un nom nouveau pour une vieille question : une machine peut-elle obtenir votre contenu, le comprendre et s’en servir dans une réponse. Crawldy vérifie la part qui vit sur votre site — et dit clairement quelle part n’y vit pas."
        primary={{ href: "/result", label: "Vérifier mon site" }}
      />

      <Section>
        <Heading
          title="Il n’y a pas de note GEO séparée, et c’est délibéré"
          lead="Sous le terme se trouvent les mêmes faits techniques qu’un audit mesure déjà. Un chiffre distinct ne mesurerait rien de neuf : il renommerait l’existant en laissant croire à un second jugement indépendant."
        />
        <Prose
          paragraphs={[
            "Ce que l’on désigne par GEO se décompose en trois choses : un robot d’IA peut-il récupérer votre page, votre balisage dit-il qui vous êtes, et votre contenu est-il formé pour qu’une réponse précise puisse en être extraite. Crawldy mesure les trois, sous les noms de préparation à l’IA et d’exploitation comme source.",
            "Cette page n’est donc pas un autre produit. C’est la même mesure, expliquée à quelqu’un arrivé avec un autre mot.",
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Ce qui est vérifiable sur votre propre site"
          lead="Tout ici produit un constat avec sa preuve : ce que nous attendions, ce que nous avons trouvé, et où."
        />
        <CardGrid
          cards={[
            {
              icon: "globe",
              title: "Récupération",
              text: "Si un agent d’IA est refusé par une règle ou un filtre, et quelle part de la page existe avant l’exécution du JavaScript.",
              href: "/fr/developpeurs/robots-ia",
            },
            {
              icon: "list",
              title: "Compréhension",
              text: "Des données structurées qui disent qui vous êtes, ce que vous proposez et comment vous joindre — et qui se référencent entre elles au lieu de rester isolées.",
              href: "/fr/developpeurs/indexabilite",
            },
            {
              icon: "link",
              title: "Exploitation comme source",
              text: "Si une page répond directement, indique qui l’a écrite, et avance des affirmations réellement présentes plutôt que sous-entendues.",
              href: "/fr/visibilite-ia",
            },
          ]}
        />
      </Section>

      <Section>
        <Heading
          title="Ce qui n’est pas vérifiable en lisant votre site"
          lead="C’est la ligne qu’il vaut la peine de tracer précisément, car la plupart du discours de la catégorie la franchit."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "Si un assistant vous recommande",
                detail:
                  "Cela demande d’interroger l’assistant, de façon répétée, sur plusieurs formulations et dans la durée. C’est une mesure réelle et véritablement différente : elle observe un système externe, pas votre site. Crawldy la réalise sous le nom d'Actual AI Presence, incluse dans les analyses payantes, et ses chiffres sont rapportés à part du score de votre audit — jamais à sa place.",
              },
              {
                term: "Si un modèle donné détient votre contenu",
                detail:
                  "Ce qu’un modèle a absorbé à l’entraînement ne s’observe pas de l’extérieur, et cela ne change pas quand vous corrigez votre site. Ce qui change, c’est la capacité d’un système de récupération à lire vos pages maintenant.",
              },
              {
                term: "Un classement à l’intérieur des réponses générées",
                detail:
                  "Il n’y a pas de liste stable où occuper une position. Les réponses sont assemblées par question, et la même requête une heure plus tard peut citer d’autres sources.",
              },
            ]}
          />
        </div>
        <Prose
          paragraphs={[
            "La mesure des mentions externes existe désormais : Actual AI Presence — des prompts définis, des exécutions répétées auprès des API des fournisseurs, des résultats rapportés comme observations avec leurs dénominateurs. Elle est décrite pour ce qu’elle est — interroger d’autres systèmes — et reste séparée de tout ce qui se mesure sur votre site.",
          ]}
        />
        <More href="/fr/methodologie" label="Comment la part mesurable est mesurée" />
      </Section>

      <Section>
        <Heading
          title="Par où commencer"
          lead="En pratique l’ordre est presque toujours le même, car le premier point rend les autres sans objet quand il est faux."
        />
        <div className="mt-6">
          <Definitions
            items={[
              {
                term: "1. Assurez-vous que le contenu arrive",
                detail:
                  "Vérifiez que les agents ne sont pas refusés et que votre texte existe dans le HTML avant l’exécution des scripts. Le balisage ne peut rien pour un contenu jamais reçu.",
              },
              {
                term: "2. Dites qui vous êtes, en données",
                detail:
                  "Balisage Organization et liens vers vos profils ailleurs. C’est ce qui permet à un système de relier une mention sur votre site à ce qu’il sait par ailleurs.",
              },
              {
                term: "3. Répondez tôt dans la page",
                detail:
                  "Une page qui énonce sa réponse avant le préambule est une page dont un système peut citer un paragraphe. C’est un travail de contenu, pas de balisage, et c’est la partie que la plupart des sites sautent.",
              },
            ]}
          />
        </div>
      </Section>
      <Related
        title="À lire aussi"
        links={[
          {
            href: "/fr/visibilite-ia",
            label: "Visibilité IA",
            text: "Le tableau complet : accès, compréhension, exploitation comme source.",
          },
          {
            href: "/fr/developpeurs/robots-ia",
            label: "Robots d’IA",
            text: "Quels agents récupèrent quoi, et pourquoi une règle ne suffit pas.",
          },
          {
            href: "/fr/methodologie",
            label: "Méthodologie",
            text: "Comment constats, couverture et confiance s’articulent.",
          },
        ]}
      />
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "audit-geo",
  title: "Audit GEO — ce qui est réellement mesurable dans l’optimisation générative",
  h1: "L’optimisation pour moteurs génératifs, sans ce que personne ne peut mesurer",
  description:
    "Ce qu’un audit GEO peut vérifier sur votre propre site — récupération, données structurées, contenu répondable — et ce qu’il ne peut pas, y compris savoir si les assistants vous mentionnent aujourd’hui.",
  navLabel: "Audit GEO",
  Body,
};
