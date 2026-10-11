/**
 * legal-acceptable-use — fr. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Ces règles protègent les utilisateurs, Crawldy et les sites analysés." },
  { kind: "heading", text: "Utilisation autorisée" },
  { kind: "para", text: "Vous pouvez analyser les pages publiques de votre site, de votre organisation ou d’un client ayant autorisé l’analyse et transmettre le rapport à ce client." },
  { kind: "heading", text: "Utilisation interdite" },
  { kind: "para", text: "Vous ne devez pas utiliser Crawldy pour :" },
  {
    kind: "list",
    items: [
      "analyser un site à des fins illégales, frauduleuses, nuisibles ou de harcèlement ;",
      "accéder à des pages, fichiers ou systèmes qui ne sont pas publics ;",
      "transmettre à Crawldy des mots de passe, jetons, liens privés, clés secrètes ou autres identifiants ;",
      "contourner une connexion, un CAPTCHA, Turnstile, une limitation de débit, un blocage technique ou toute autre protection ;",
      "exploiter des vulnérabilités, effectuer des tests d’intrusion, diffuser du code malveillant, provoquer un déni de service ou réaliser des tests destructifs ;",
      "créer intentionnellement une charge excessive ou contourner les limites techniques au moyen de plusieurs sessions, comptes ou organisations ;",
      "porter atteinte à la vie privée, aux droits d’auteur, aux marques, à des restrictions contractuelles ou à d’autres droits de tiers ;",
      "revendre des comptes, des crédits ou un accès automatisé, ni copier Crawldy sans accord distinct ;",
      "présenter le rapport comme une certification officielle de sécurité, d’accessibilité, de conformité légale, de position dans les moteurs de recherche ou de recommandation par une IA.",
    ],
  },
  { kind: "heading", text: "Comment fonctionne l’analyse" },
  { kind: "para", text: "Crawldy lit des signaux observables sur des pages publiques. Sans fonction distincte expressément convenue et sans base juridique valable, le service ne doit pas se connecter à des espaces privés, saisir des identifiants, envoyer des formulaires, contourner des protections ni effectuer des tests intrusifs." },
  { kind: "heading", text: "Protection du service" },
  { kind: "para", text: "Nous pouvons arrêter ou ralentir une analyse si elle crée un risque pour le site analysé, pour Crawldy ou pour d’autres utilisateurs, ou si elle enfreint la loi. La protection technique contre les abus est distincte des droits liés à l’offre." },
  { kind: "para", text: "Dans la mesure du possible, la mesure se limite à l’analyse ou à l’utilisateur concerné. La résiliation de Monthly ou un blocage technique n’efface pas les analyses Pack légalement achetées, sauf remboursement, fraude confirmée ou obligation légale." },
  { kind: "heading", text: "Signaler un problème" },
  { kind: "para", text: "Pour signaler un abus, utilisez le formulaire protégé et indiquez le domaine, l’heure et les informations techniques disponibles. N’envoyez aucun secret." },
  { kind: "heading", text: "Conséquences d’une violation" },
  { kind: "para", text: "Selon la gravité, nous pouvons avertir l’utilisateur, arrêter une analyse, limiter temporairement l’accès ou fermer un compte. Nous pouvons conserver les preuves nécessaires et nous adresser aux autorités compétentes lorsque la loi ou la défense contre une menace réelle l’exige." },
  { kind: "heading", text: "Contact" },
  { kind: "para", text: "LLC “Accurly”, identifiant ukrainien 46295102." },
  { kind: "para", text: "Utilisez le formulaire protégé de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Utilisation acceptable",
        meta: ["**Date d’entrée en vigueur :** `1er janvier 2026`", "**Version :** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Sommaire",
        relatedLabel: "Documents liés",
        related: [
    { label: "Confidentialité et cookies", href: "/fr/confidentialite" },
    { label: "Conditions d’utilisation", href: "/fr/conditions-utilisation" },
    { label: "Remboursements et résiliation", href: "/fr/remboursements" },
    { label: "Contact", href: "/fr/contact" },
        ],
      }}
    />
  );
}

export const fr: LocalizedPage = {
  slug: "utilisation-acceptable",
  title: "Utilisation acceptable — Crawldy",
  h1: "Utilisation acceptable",
  description: "Vous pouvez analyser les pages publiques de votre site, de votre organisation ou d’un client ayant autorisé l’analyse et transmettre le rapport à ce client.",
  navLabel: "Utilisation acceptable",
  Body,
};
