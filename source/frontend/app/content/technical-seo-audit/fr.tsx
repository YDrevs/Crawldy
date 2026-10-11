/**
 * technical-seo-audit — fr. Структура затвердженої пропозиції E2
 * (2026-09-05): надзаголовок, H1 і одне речення підводки → пʼять блоків
 * (швидкість і стабільність; HTTPS, редиректи й базовий захист; відповідь
 * сервера проти відрендереного DOM — окремим розділом; форми й обробка
 * помилок; доступність і зручність) → докази й рекомендації із
 * застереженням → спільний нижній CTA.
 *
 * Слова обмежені тим, що вимірюється: порівнюється відрендерений DOM, а не
 * «те, що бачить відвідувач»; доказ дає розробнику точку, з якої почати,
 * а не знімає подальшу діагностику; це не пентест і не сертифікація.
 */

import { SiteCta } from "../../components/SiteCta";
import { ctaOf } from "../cta";
import { Heading, Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  const cta = ctaOf("fr");
  return (
    <>
      <Hero
        eyebrow={"Audit technique du site"}
        title={"Ce qui empêche techniquement le site de fonctionner correctement"}
        lead={"Cette partie de la vérification compare ce que renvoie le serveur avec le résultat après l’exécution des scripts et montre où les deux ne correspondent pas."}
      />

      <Section>
        <div className="flex flex-col gap-10">
          <div>
            <Heading level={2} size="lg" title={"1. Vitesse et stabilité"} lead={"Nous vérifions le temps de réponse du serveur, le poids des pages, les ressources qui bloquent le chargement, les scripts tiers et les Core Web Vitals lorsque des données d’utilisateurs réels existent. Chaque chiffre du rapport porte sa source : données de terrain ou mesure en laboratoire."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"2. HTTPS, redirections et protection de base"} lead={"Nous vérifions le certificat, les passages entre HTTP et HTTPS et entre les versions avec et sans www, les chaînes de redirections longues ou bouclées, les en-têtes de sécurité, la mise en cache et les ressources non protégées sur des pages protégées. Ce sont des signes visibles, pas une recherche de vulnérabilités."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"3. Réponse du serveur contre DOM rendu"} lead={"Nous comparons la réponse HTML du serveur avec le DOM après l’exécution du JavaScript. Cela révèle le contenu, les liens, la navigation ou les données structurées présents dans une seule des deux versions de la page, et nous montrons laquelle."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"4. Formulaires et gestion des erreurs"} lead={"Nous vérifions par quelle méthode les formulaires de contact envoient les données et si des signes de protection contre le spam automatisé sont visibles. Nous vérifions également la façon dont le site répond aux adresses inexistantes. Une page d’erreur doit renvoyer un code d’erreur, pas la réponse « tout va bien »."} />
          </div>
          <div>
            <Heading level={2} size="lg" title={"5. Accessibilité et confort d’utilisation"} lead={"Nous vérifions les obstacles courants pour les personnes qui utilisent le site autrement : contraste, libellés des commandes, structure des titres, zoom sur téléphone et possibilité de toucher un numéro de téléphone. C’est une vérification automatique, pas une certification WCAG."} />
          </div>
        </div>
      </Section>

      <Section bordered={false}>
        <Heading title={"Preuves et recommandations dans le rapport"} lead={"Pour chaque problème, le rapport indique l’adresse de la page, le résultat attendu, la réponse réelle et la preuve technique. Cela donne au développeur un point de départ concret."} />
        <p className="mt-4 max-w-measure text-sm text-muted">{"C’est une vérification technique automatique, pas un test d’intrusion, une recherche de vulnérabilités ni une certification d’accessibilité."}</p>
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
  slug: "audit-technique-seo",
  title: "Audit technique du site — serveur, HTTPS, JavaScript, vitesse",
  h1: "Ce qui empêche techniquement le site de fonctionner correctement",
  description:
    "Les raisons techniques concrètes pour lesquelles un site ne fonctionne pas correctement : réponses du serveur, HTTPS et redirections, contenu rendu, vitesse et réglages de base.",
  navLabel: "Audit technique du site",
  Body,
};
