/**
 * legal-refunds — fr. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Ces règles volontaires ne limitent aucun droit légal impératif." },
  { kind: "heading", text: "Checkout fermé" },
  { kind: "para", text: "Si vous fermez le checkout avant de terminer le paiement, l’audit reste enregistré. Aucun débit n’a lieu sans confirmation de Paddle. Une fois confirmé que le paiement n’a pas abouti, vous pouvez le renouveler pour le même audit." },
  { kind: "para", text: "Si le statut reste incertain, Crawldy vérifie d’abord la transaction et ne propose pas un paiement en double." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Le rapport complet commence à être traité immédiatement après confirmation du paiement, à la demande de l’acheteur. Une fois le rapport produit et ouvert, aucun remboursement volontaire pour changement d’avis n’est accordé, sauf obligation légale." },
  { kind: "para", text: "Nous remboursons le montant ou relançons l’analyse sans frais supplémentaires si :" },
  {
    kind: "list",
    items: [
      "le paiement a été dupliqué ;",
      "le débit a eu lieu sans que l’accès payant ait été fourni ;",
      "une erreur technique de Crawldy n’a pas permis de produire un rapport complet utilisable et le problème ne peut pas être corrigé par une nouvelle exécution dans un délai raisonnable.",
    ],
  },
  { kind: "para", text: "Un score faible, des constats ou l’absence d’une mention AI attendue ne constituent pas à eux seuls une erreur technique." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Un Pack entièrement inutilisé peut être remboursé dans les 14 jours calendaires suivant l’achat. Après toute utilisation d’une analyse complète ou d’Actual AI Presence, aucun remboursement volontaire total n’est accordé sauf obligation légale." },
  { kind: "para", text: "Un droit consommé par une erreur technique de Crawldy est restauré. Les droits Pack non utilisés n’expirent pas." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly peut être résilié à tout moment pour arrêter les renouvellements futurs. L’accès continue jusqu’à la fin de la période payée." },
  { kind: "para", text: "Le premier paiement peut être remboursé sous 14 jours calendaires si aucune analyse complète ni Actual AI Presence n’a été utilisé." },
  { kind: "para", text: "Le dernier renouvellement automatique peut être remboursé sous 7 jours calendaires si aucune de ces fonctions n’a été utilisée dans la nouvelle période. Après utilisation, aucun remboursement volontaire au prorata n’est accordé, sauf obligation légale." },
  { kind: "para", text: "La résiliation de Monthly ne supprime pas les analyses Pack achetées séparément." },
  { kind: "heading", text: "Problèmes techniques du site cible" },
  { kind: "para", text: "Si le site est indisponible, bloque l’analyse, si l’adresse indiquée est incorrecte ou si le site ne répond que partiellement, Crawldy affiche la couverture réelle. Nous examinerons une nouvelle exécution ou un remboursement si le résultat ne peut pas être considéré comme utilisable et si cette limitation n’était pas évidente avant l’achat." },
  { kind: "heading", text: "Comment envoyer une demande" },
  { kind: "para", text: "Utilisez le formulaire protégé et choisissez « Paiement, remboursement ou abonnement ». Indiquez l’adresse de réponse, le domaine, la date approximative de l’achat et l’identifiant de la transaction ou du reçu, si vous l’avez." },
  { kind: "para", text: "N’envoyez jamais de numéro de carte, de code de sécurité ni d’identifiants bancaires." },
  { kind: "para", text: "Nous accusons réception de la demande et communiquons la décision ou les informations manquantes. Les remboursements approuvés sont effectués par Paddle vers le moyen de paiement initial. Le délai de crédit dépend de Paddle, de la banque et du moyen de paiement." },
  { kind: "heading", text: "Contestations bancaires et fraude" },
  { kind: "para", text: "Si un paiement est contesté sans prise de contact préalable, nous pouvons suspendre les droits associés pendant l’examen du dossier. Cela ne prive pas l’utilisateur de ses droits impératifs. Un remboursement confirmé, une contestation bancaire ou un paiement frauduleux peut entraîner l’annulation de l’accès inutilisé correspondant." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, identifiant ukrainien 46295102." },
  { kind: "para", text: "Utilisez le formulaire protégé de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Remboursements et résiliation",
        meta: ["**Date d’entrée en vigueur :** `1er janvier 2026`", "**Version :** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Sommaire",
        relatedLabel: "Documents liés",
        related: [
    { label: "Confidentialité et cookies", href: "/fr/confidentialite" },
    { label: "Conditions d’utilisation", href: "/fr/conditions-utilisation" },
    { label: "Utilisation acceptable", href: "/fr/utilisation-acceptable" },
    { label: "Contact", href: "/fr/contact" },
        ],
      }}
    />
  );
}

export const fr: LocalizedPage = {
  slug: "remboursements",
  title: "Remboursements et résiliation — Crawldy",
  h1: "Remboursements et résiliation",
  description: "Ces règles volontaires ne limitent aucun droit légal impératif.",
  navLabel: "Remboursements et résiliation",
  Body,
};
