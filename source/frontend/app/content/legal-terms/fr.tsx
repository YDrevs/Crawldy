/**
 * legal-terms — fr. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Ces conditions régissent Crawldy, l’aperçu gratuit, les rapports payants, les comptes, Pack, Monthly et Actual AI Presence." },
  { kind: "heading", text: "Parties" },
  { kind: "para", text: "Crawldy est exploité par LLC “Accurly”, identifiant ukrainien 46295102, dont le siège est situé 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "heading", text: "Acceptation des conditions" },
  { kind: "para", text: "« Vous » désigne l’utilisateur ou l’organisation pour laquelle Crawldy est utilisé. Si vous agissez pour une organisation, vous confirmez votre pouvoir d’accepter ces conditions en son nom. En utilisant Crawldy, en créant un compte ou en achetant un service, vous acceptez ces Conditions, la Politique de confidentialité, la Politique de remboursement et la Politique d’utilisation acceptable. Avant le paiement, l’utilisateur doit pouvoir ouvrir et enregistrer les versions en vigueur de ces documents. Les utilisateurs ayant la capacité juridique de conclure eux-mêmes des contrats contraignants peuvent créer un compte et acheter des services." },
  { kind: "heading", text: "Service" },
  { kind: "para", text: "Crawldy analyse les pages accessibles et génère un rapport sur la visibilité dans la recherche et l’IA, l’état technique, les performances, l’accessibilité et les signaux de protection élémentaires observables. Le rapport indique la couverture, les constats, les preuves, l’impact et les priorités. Il reflète l’état accessible au moment de l’analyse." },
  { kind: "heading", text: "Aperçu gratuit" },
  { kind: "para", text: "L’aperçu gratuit fonctionne sans compte et sans limite commerciale de nombre. Il affiche un score global, la couverture et quelques problèmes principaux. Il ne débloque pas le rapport complet, n’accorde pas de droit payant à une analyse complète et n’exécute pas Actual AI Presence. Les limitations techniques de sécurité et de débit ne sont pas un quota tarifaire." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Single est l’achat unique du rapport complet pour un audit précis. Aucun compte n’est requis. Après confirmation du paiement, l’acheteur reçoit un lien protégé disponible pendant 12 mois. La création ultérieure d’un compte est facultative. Le rapport n’est rattaché à un compte qu’après vérification de la propriété." },
  { kind: "para", text: "Single comprend la quantité d’Actual AI Presence affichée avant le paiement. La configuration de lancement comprend une vérification." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Pack nécessite un compte et accorde le nombre d’analyses complètes et de vérifications Actual AI Presence affiché avant le paiement. Les analyses Pack non utilisées n’expirent pas et ne disparaissent pas lors de l’achat, du renouvellement ou de la résiliation de Monthly. Pack n’est pas un abonnement et ne se renouvelle pas automatiquement." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly nécessite un compte et se renouvelle chaque mois au prix affiché. Il comprend un nombre illimité d’analyses complètes et un nombre distinct d’Actual AI Presence configuré pour chaque période mensuelle payée." },
  { kind: "para", text: "« Illimité » signifie qu’il n’existe pas de limite commerciale du nombre d’analyses complètes. Crawldy peut appliquer des contrôles techniques raisonnables de débit, de file d’attente et de simultanéité pour la sécurité et la stabilité, mais pas de quota payant caché. Actual AI Presence est limité, réinitialisé au début de chaque période et non reporté sauf indication expresse." },
  { kind: "para", text: "Monthly peut être résilié dans l’espace client ou via l’outil de gestion disponible. La résiliation arrête le prochain renouvellement et l’accès continue jusqu’à la fin de la période payée. Une organisation ne peut pas avoir deux abonnements Monthly non terminés en parallèle." },
  { kind: "heading", text: "Sites autorisés" },
  { kind: "para", text: "Vous pouvez analyser un site qui vous appartient, qui appartient à votre organisation ou à un client ayant dûment autorisé l’analyse. Les pages publiques peuvent être analysées dans un but licite. Ne fournissez pas de mots de passe, jetons, liens privés, espaces de compte, documents confidentiels ni une adresse dont l’analyse violerait la loi, un contrat ou les droits d’une autre personne." },
  { kind: "heading", text: "Actual AI Presence" },
  { kind: "para", text: "Actual AI Presence pose des questions formulées à des fournisseurs d’IA externes et enregistre les réponses obtenues à un moment donné. La composition des modèles, leur disponibilité, les règles et les réponses des fournisseurs peuvent changer. Le résultat ne garantit pas que la marque sera ou ne sera pas mentionnée à un autre utilisateur, à un autre moment, dans un autre pays ou avec une formulation différente de la requête." },
  { kind: "heading", text: "Paiement par Paddle" },
  { kind: "para", text: "Les paiements sont effectués par Paddle. Dans son modèle standard, Paddle agit comme revendeur autorisé et Merchant of Record et gère le paiement, les taxes applicables et le reçu. LLC “Accurly” exploite Crawldy et fournit l’accès au service." },
  { kind: "para", text: "Le checkout affiche le produit, le prix, la devise, les taxes et le renouvellement. L’accès payant n’est accordé qu’après confirmation du paiement. Fermer le checkout ne prouve pas que le paiement a réussi. Si l’état reste incertain, Crawldy rapproche d’abord la transaction et ne propose pas un second paiement." },
  { kind: "heading", text: "Analyses échouées" },
  { kind: "para", text: "Si une analyse complète échoue à cause d’une erreur technique de Crawldy, nous pouvons la relancer, restaurer le droit Pack ou Monthly utilisé ou rembourser Single selon la Politique de remboursement. Si le site n’est pas disponible ou bloque l’accès, Crawldy affiche la couverture réelle et n’invente pas de données." },
  { kind: "heading", text: "Compte et sécurité" },
  { kind: "para", text: "Vous êtes responsable des données du compte, de la sécurité de connexion et des utilisateurs de votre organisation. Ne partagez pas un lien invité avec une personne non autorisée." },
  { kind: "heading", text: "Utilisation du rapport et propriété" },
  { kind: "para", text: "Vous pouvez utiliser, télécharger et partager le rapport acheté au sein de votre organisation. Une agence ou un consultant peut analyser le site d’un client et lui transmettre le rapport si ce client a autorisé l’analyse. Cela ne donne pas le droit de revendre des comptes, des crédits, un accès automatisé ou Crawldy lui-même sans accord distinct. Le logiciel, le design, la méthodologie, le catalogue de vérifications et les signes distinctifs de Crawldy restent la propriété de LLC “Accurly” ou des titulaires de droits concernés." },
  { kind: "heading", text: "Limites" },
  { kind: "para", text: "Crawldy est un outil d’information automatisé. Le rapport ne garantit ni classement, ni indexation, ni mention par une IA. Il ne constitue pas un test d’intrusion, une évaluation de vulnérabilités, une certification de sécurité ou WCAG, un conseil juridique ou financier, ni une modification automatique du site." },
  { kind: "heading", text: "Disponibilité du service" },
  { kind: "para", text: "Nous ne garantissons pas un fonctionnement continu ou sans erreur." },
  { kind: "heading", text: "Suspension de l’accès" },
  { kind: "para", text: "Nous pouvons limiter l’accès pour des raisons de sécurité, de droit, d’abus, de fraude ou d’impayé. Une limitation technique ou la résiliation de Monthly n’efface pas les droits Pack achetés séparément, sauf remboursement, fraude confirmée, contestation bancaire ou obligation légale." },
  { kind: "heading", text: "Responsabilité" },
  { kind: "para", text: "Aucune responsabilité ni aucun droit impératif du consommateur ne sont limités lorsque la loi l’interdit. Dans la mesure permise, LLC “Accurly” n’est pas responsable des pertes indirectes, du manque à gagner, de la perte de classement, des mentions AI attendues ou des décisions prises uniquement à partir du rapport. La responsabilité totale est limitée au montant payé pour le Single ou Pack concerné ou, pour Monthly, aux paiements des 12 derniers mois. La limite ne s’applique pas en cas de faute intentionnelle, fraude, négligence grave ou responsabilité non limitable." },
  { kind: "heading", text: "Fin de l’utilisation" },
  { kind: "para", text: "Vous pouvez résilier Monthly, cesser l’utilisation et supprimer le compte. Les données devant être conservées par la loi le restent." },
  { kind: "heading", text: "Droit applicable" },
  { kind: "para", text: "Ces conditions sont régies par le droit ukrainien. Les litiges sont soumis aux tribunaux compétents d’Ukraine, sauf si des règles impératives de protection des consommateurs donnent à l’utilisateur le droit de saisir une autre juridiction ou d’appliquer un autre droit impératif. Les parties tenteront d’abord de résoudre la question au moyen du formulaire de contact protégé." },
  { kind: "heading", text: "Modifications des conditions" },
  { kind: "para", text: "Les modifications importantes ne changent pas rétroactivement un achat unique terminé et sont communiquées aux utilisateurs inscrits." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, identifiant ukrainien 46295102." },
  { kind: "para", text: "Utilisez le formulaire protégé de Crawldy." },
  { kind: "para", text: "---" },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Conditions d’utilisation",
        meta: ["**Date d’entrée en vigueur :** `1er janvier 2026`", "**Version :** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Sommaire",
        relatedLabel: "Documents liés",
        related: [
    { label: "Confidentialité et cookies", href: "/fr/confidentialite" },
    { label: "Remboursements et résiliation", href: "/fr/remboursements" },
    { label: "Utilisation acceptable", href: "/fr/utilisation-acceptable" },
    { label: "Contact", href: "/fr/contact" },
        ],
      }}
    />
  );
}

export const fr: LocalizedPage = {
  slug: "conditions-utilisation",
  title: "Conditions d’utilisation — Crawldy",
  h1: "Conditions d’utilisation",
  description: "Ces conditions régissent Crawldy, l’aperçu gratuit, les rapports payants, les comptes, Pack, Monthly et Actual AI Presence.",
  navLabel: "Conditions d’utilisation",
  Body,
};
