/**
 * about — fr. Структура другого проходу (журнал правок): без
 * перехресних посилань, без повтору шести напрямів і методології,
 * один спільний CTA унизу.
 */


import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { CardGrid, Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      {/* Прикладу звіту тут немає навмисно. Той, що стояв, показував
          сайт `example-shop.com` із балом 62, покриттям і критичною
          знахідкою — усе вигадане. Сторінка «Про нас» — це те місце,
          де читач вирішує, чи вірити нашим числам узагалі; вигадане
          число саме тут коштує найдорожче. Справжній зразок зʼявиться
          після розміщення: ним стане звіт Crawldy про самого себе. */}
      <Hero
        eyebrow={"À PROPOS"}
        title={"Nous aidons à comprendre comment la recherche et l'IA voient votre site"}
        lead={"Crawldy est un service d'analyse de sites web qui réunit la visibilité dans la recherche, la préparation à l'IA, l'état technique du site et les mentions réelles dans les assistants IA en un seul rapport clair."}
      />

      <Section>
        <Heading title={"Pourquoi Crawldy a été créé"} lead={"Crawldy transforme les problèmes trouvés en un plan clair. Le rapport montre l'ampleur du problème, les preuves et la priorité de la correction."} />
      </Section>

      <Section>
        <Heading title={"Notre objectif"} lead={"Rendre la visibilité d'un site dans la recherche et l'IA compréhensible et mesurable. Le propriétaire d'un site doit voir non pas de simples indicateurs techniques, mais des problèmes concrets, leur impact et les étapes suivantes."} />
      </Section>

      <Section bordered={false}>
        <Heading title={"À qui s'adresse Crawldy"} />
        <CardGrid
          cards={[
            {
              title: "Aux propriétaires de sites",
              text: "Pour comprendre ce qui empêche les clients, les moteurs de recherche et l'IA de trouver votre site.",
            },
            {
              title: "Aux équipes marketing",
              text: "Pour voir les problèmes de visibilité, de contenu et d'indexation et fixer les priorités.",
            },
            {
              title: "Aux agences web",
              text: "Pour vérifier les sites clients selon une méthode unique et remettre un rapport clair, appuyé sur des preuves.",
            },
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
  slug: "a-propos",
  title: "À propos de Crawldy — analyse de sites pour la recherche et l'IA",
  h1: "Nous aidons à comprendre comment la recherche et l'IA voient votre site",
  description:
    "Crawldy réunit visibilité dans la recherche, préparation à l'IA, état technique et mentions réelles dans l'IA en un rapport. Pourquoi il existe et pour qui.",
  navLabel: "À propos",
  Body,
};
