/**
 * ai-visibility — fr. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { PresenceModels } from "../../components/PresenceModels";
import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import {
  Bullets,
  Definitions,
  Heading,
  Hero,
  Section,
} from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      <Hero
        eyebrow={"Visibilité dans l'IA"}
        title={"Les systèmes d'IA vous voient-ils et vous mentionnent-ils ?"}
        lead={"Crawldy vérifie si l'IA peut récupérer vos pages, comprendre les informations sur votre entreprise et utiliser le site comme source. Dans le rapport complet, Actual AI Presence montre aussi si ChatGPT, Claude, Perplexity et Gemini citent votre marque."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"Accès pour l'IA"} lead={"Nous vérifions si les systèmes d'IA peuvent charger vos pages et récupérer le contenu principal. Nous tenons compte des restrictions imposées aux robots d'IA, des réponses du serveur et de la dépendance du site au JavaScript."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Compréhension de votre activité"} lead={"Nous vérifions si les pages indiquent clairement qui vous êtes, ce que vous proposez et comment vous joindre. Pour cela, nous analysons la structure du contenu, les informations sur l'entreprise, les contacts et le balisage correspondant."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"Aptitude à servir de source"} lead={"Nous vérifions si le site contient des réponses claires, un contexte suffisant, une paternité indiquée et des affirmations que l'IA peut utiliser correctement dans une réponse."} />
          </div>
        </div>
      </Section>

      <Section>
        <Heading title={"Présence réelle dans les réponses"} />
        <PresenceModels
          intro={"Pour chaque vérification, Crawldy utilise les modèles retenus comme les plus représentatifs de l’expérience utilisateur actuelle de chaque plateforme d’IA."}
          note={"Les modèles des plateformes d’IA évoluent, et des modèles différents peuvent citer les marques, recommander les entreprises et utiliser les sources différemment. Le résultat d’Actual AI Presence porte donc sur les modèles indiqués pour cette vérification précise."}
        />
      </Section>

      <Section bordered={false}>
        <Heading title={"Ce que vous verrez dans le rapport"} />
        <Bullets
          items={[
            "les problèmes qui empêchent l'IA de récupérer ou de comprendre le contenu",
            "les pages et les preuves de chaque conclusion",
            "les mentions de marque et les liens dans les réponses des assistants",
            "les autres domaines que les assistants ont nommés à votre place",
            "les priorités de correction",
          ]}
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
  slug: "visibilite-ia",
  title: "Visibilité dans l'IA — l'IA récupère-t-elle, comprend-elle et cite-t-elle votre site ?",
  h1: "Les systèmes d'IA vous voient-ils et vous mentionnent-ils ?",
  description:
    "Si les systèmes d'IA peuvent récupérer vos pages, comprendre votre activité et utiliser le site comme source, et si ChatGPT, Claude, Perplexity et Gemini citent votre marque.",
  navLabel: "Visibilité dans l'IA",
  Body,
};
