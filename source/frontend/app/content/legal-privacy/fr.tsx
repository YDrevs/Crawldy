/**
 * legal-privacy — fr. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "La présente politique explique quelles données Crawldy traite, pourquoi elles sont nécessaires, qui peut les recevoir et quels sont les droits des utilisateurs." },
  { kind: "heading", text: "Responsable" },
  { kind: "para", text: "Crawldy est exploité par LIMITED LIABILITY COMPANY “Accurly” (LLC “Accurly”), identifiant ukrainien 46295102. Siège social : 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Pour toute question relative aux données, utilisez le formulaire protégé de Crawldy et choisissez « Confidentialité et données »." },
  { kind: "heading", text: "Champ d’application" },
  { kind: "para", text: "Cette politique s’applique à `crawldy.ai et crawldy.com`, à l’aperçu gratuit, aux analyses payantes, à Actual AI Presence, aux comptes, à l’espace client, aux paiements et au formulaire de contact." },
  { kind: "heading", text: "Données traitées" },
  { kind: "para", text: "**Site et analyse.** Nous traitons l’URL et le domaine saisis, les pages publiques, les réponses du serveur, les en-têtes, les métadonnées, les liens, les données structurées, les mesures de performance, les constats, les preuves, la couverture et les scores." },
  { kind: "para", text: "**Compte.** Lors de la création d’un compte, nous traitons le nom, l’adresse électronique, les données d’authentification, l’appartenance à une organisation, l’historique des analyses, les soldes achetés et l’utilisation du service." },
  { kind: "para", text: "**Paiement.** Paddle traite les informations de paiement dans le checkout. Crawldy ne reçoit pas le numéro complet de la carte. Nous recevons et conservons l’identifiant client ou transaction, le produit, le montant, la devise, l’état du paiement et de l’abonnement, les données de remboursement et les informations nécessaires pour fournir et comptabiliser l’achat." },
  { kind: "para", text: "**Actual AI Presence.** Pour une analyse payante, nous pouvons créer des requêtes sur la marque, le site, l’entreprise, le marché ou les services et les envoyer à OpenAI, Anthropic, Google et Perplexity. Nous conservons la requête, la réponse, la date, le modèle, l’état et l’observation enregistrée. L’aperçu gratuit n’exécute pas Actual AI Presence." },
  { kind: "para", text: "**Contact et sécurité.** Nous traitons le nom, l’adresse de réponse, l’objet, le message, l’état d’envoi et le résultat Cloudflare Turnstile. Nous pouvons aussi traiter l’adresse IP, le navigateur, l’appareil, la langue, l’heure, les journaux d’erreurs, les identifiants de session, les limitations de débit et les signaux anti-abus." },
  { kind: "heading", text: "Finalités du traitement" },
  { kind: "para", text: "Nous utilisons les données pour analyser le site indiqué et générer le résultat, fournir le rapport acheté, conserver le solde Pack ou gérer Monthly, exécuter Actual AI Presence après le paiement, créer et protéger un compte, confirmer les paiements, remboursements ou annulations, répondre aux demandes, détecter les erreurs, la fraude, les abus automatisés et les menaces de sécurité, respecter les obligations comptables, fiscales et autres obligations légales, et améliorer la fiabilité et la clarté de Crawldy à partir de données agrégées ou anonymisées." },
  { kind: "heading", text: "Bases juridiques" },
  { kind: "para", text: "Selon le cas, le traitement repose sur l’exécution d’un contrat ou des mesures précontractuelles, une obligation légale, notre intérêt légitime à sécuriser et exploiter le service, ou votre consentement. Le consentement est utilisé pour les cookies facultatifs d’analyse ou de marketing s’ils sont activés." },
  { kind: "heading", text: "Analyse automatisée" },
  { kind: "para", text: "Crawldy produit automatiquement des constats techniques, un score, une couverture et des priorités. Il ne prend pas de décision juridique ou ayant un effet similaire sur une personne. Le score global peut être absent si les données sont insuffisantes." },
  { kind: "heading", text: "Destinataires" },
  { kind: "para", text: "Nous ne transmettons que les données nécessaires :" },
  {
    kind: "list",
    items: [
      "à Paddle pour le checkout, les paiements, taxes, reçus, abonnements et remboursements ;",
      "à Cloudflare pour Turnstile et les fonctions de sécurité activées ;",
      "à OpenAI, Anthropic, Google et Perplexity pour Actual AI Presence payant ;",
      "aux prestataires d’hébergement, base de données, stockage, authentification, courrier électronique, surveillance et sauvegarde ;",
      "aux conseils, tribunaux ou autorités lorsque la loi l’exige.",
    ],
  },
  { kind: "para", text: "Nous ne vendons pas les données personnelles. Nous n’envoyons pas intentionnellement de mots de passe, d’identifiants de paiement ou de contenu privé aux fournisseurs d’IA. Les utilisateurs ne doivent pas transmettre ces données à Crawldy." },
  { kind: "heading", text: "Conservation" },
  {
    kind: "list",
    items: [
      "Aperçu gratuit : jusqu’à 30 jours.",
      "Rapport Single anonyme et jeton sécurisé : 12 mois après l’achat.",
      "Compte, historique, Pack et Monthly : pendant l’activité du compte ; après suppression vérifiée, les données non exigées par la loi sont supprimées ou anonymisées sous 30 jours, avec des sauvegardes jusqu’à 90 jours.",
      "Messages de contact : jusqu’à 24 mois après clôture.",
      "Journaux de sécurité et de limitation : jusqu’à 90 jours, sauf enquête plus longue.",
      "Données de paiement, comptables et fiscales : pendant la durée exigée par la loi.",
      "Données des prestataires externes : selon leurs conditions et la configuration réelle de l’API.",
    ],
  },
  { kind: "heading", text: "Cookies et stockage local" },
  { kind: "para", text: "Crawldy peut utiliser des cookies techniquement nécessaires au fonctionnement du site, à l’authentification et à l’enregistrement des préférences de l’utilisateur." },
  { kind: "para", text: "Cloudflare Turnstile traite des signaux du navigateur pour distinguer une personne d’une requête automatisée. Cloudflare indique que Turnstile n’accède pas au texte saisi dans un formulaire et ne le transmet pas. Paddle peut utiliser ses propres technologies nécessaires dans le checkout." },
  { kind: "heading", text: "Vos droits" },
  { kind: "para", text: "Selon la loi applicable, vous pouvez demander l’accès, une copie, la rectification, l’effacement, la limitation, l’opposition, la portabilité ou le retrait de votre consentement. Vous pouvez aussi saisir une autorité compétente de protection des données." },
  { kind: "para", text: "Utilisez le formulaire protégé et choisissez « Confidentialité et données ». Nous pouvons demander une preuve d’identité ou de pouvoir de représentation." },
  { kind: "heading", text: "Données de tiers et sites clients" },
  { kind: "para", text: "Vous devez disposer d’une base légale pour soumettre un site. Ne transmettez pas d’URL privées, de mots de passe, de jetons, de documents privés ou de secrets. Si vous agissez pour un client, vous êtes responsable de l’autorisation et de l’information nécessaires." },
  { kind: "heading", text: "Droit d’utiliser le service" },
  { kind: "para", text: "Le service s’adresse aux utilisateurs ayant la capacité juridique de conclure eux-mêmes des contrats contraignants." },
  { kind: "heading", text: "Sécurité" },
  { kind: "para", text: "Nous appliquons des mesures techniques et organisationnelles pour protéger les données. Aucun système ne peut garantir une sécurité absolue. En cas d’incident, nous agirons conformément au droit applicable." },
  { kind: "heading", text: "Modifications de la politique" },
  { kind: "para", text: "Les modifications sont publiées avec une date et une version et les modifications importantes sont communiquées aux utilisateurs inscrits par un canal disponible." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, identifiant ukrainien 46295102." },
  { kind: "para", text: "59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Utilisez le formulaire protégé de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Confidentialité et cookies",
        meta: ["**Date d’entrée en vigueur :** `1er janvier 2026`", "**Version :** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Sommaire",
        relatedLabel: "Documents liés",
        related: [
    { label: "Conditions d’utilisation", href: "/fr/conditions-utilisation" },
    { label: "Remboursements et résiliation", href: "/fr/remboursements" },
    { label: "Utilisation acceptable", href: "/fr/utilisation-acceptable" },
    { label: "Contact", href: "/fr/contact" },
        ],
      }}
    />
  );
}

export const fr: LocalizedPage = {
  slug: "confidentialite",
  title: "Confidentialité et cookies — Crawldy",
  h1: "Confidentialité et cookies",
  description: "La présente politique explique quelles données Crawldy traite, pourquoi elles sont nécessaires, qui peut les recevoir et quels sont les droits des utilisateurs.",
  navLabel: "Confidentialité et cookies",
  Body,
};
