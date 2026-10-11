/**
 * Ціни — fr. Композиція повернута до стану `164a74d` (рішення власника
 * 2026-09-05): H1 → одне пояснювальне речення → чотири рівні блоки в ряд:
 * Безкоштовне превʼю, Разова, Пакет, Місячний план. Перебудова «смуга
 * превʼю + три картки» була пропозицією без затвердження і знята.
 *
 * Рядки — затверджений вміст блоків; числа — ціни, кількість перевірок,
 * кількість Actual AI Presence — рендерить <PricingCards/> з комерційної
 * конфігурації бекенда; у цьому файлі їх немає, і тест це стереже для
 * всіх мов одразу. Форми множини постачає ця сторінка: закінчень у коді
 * компонента не зашито.
 */

import { PricingCards } from "../../components/PricingCards";
import { Hero, Section } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <>
      <Hero title="Combien coûte l’analyse d’un site ?" compact lead="Toutes les formules donnent accès au même rapport complet. Vous pouvez payer une analyse unique, acheter un pack à un prix inférieur par site ou choisir un forfait mensuel." />

      <Section tight>
        <PricingCards
          locale="fr"
          strings={{
            free: {
              heading: "Aperçu gratuit",
              bullets: [
                "Score global du site",
                "Couverture de l’analyse",
                "Trois problèmes ayant le plus d’impact",
              ],
              cta: "Vérifier le site",
            },
            single: {
              kind: "Analyse unique",
              analyses: {
                one: "{n} analyse complète du site",
                other: "{n} analyses complètes de sites",
              },
              scores: "Un score pour chaque domaine analysé",
              issues: "Tous les problèmes détectés avec leurs preuves",
              pages: "Pages concernées par chaque problème",
              order: "Les corrections à effectuer et leur ordre",
              download: "Rapport complet à télécharger",
              presence: {
                one: "Actual AI Presence : {n} vérification",
                other: "Actual AI Presence : {n} vérifications",
              },
              note: "Sans inscription",
              cta: "Obtenir le rapport",
            },
            pack: {
              kind: "Pack d’analyses",
              analyses: {
                one: "{n} analyse complète du site",
                other: "{n} analyses complètes de sites",
              },
              includesSingle: "Le même rapport complet pour chaque analyse",
              presence: {
                one: "Actual AI Presence : {n} vérification",
                other: "Actual AI Presence : {n} vérifications",
              },
              unitPrice: "{unit_price} par analyse",
              noExpiry: "Sans date d’expiration",
              manage: "Gestion des analyses et du solde depuis le compte",
              note: "Un compte Crawldy est requis",
              cta: "Acheter le pack",
            },
            monthly: {
              badge: "Pour une utilisation régulière",
              kind: "Forfait mensuel",
              unlimited: "Analyses complètes de sites illimitées",
              analysesPerMonth: {
                one: "{n} analyse complète par mois",
                other: "{n} analyses complètes par mois",
              },
              includesSingle: "Le même rapport complet pour chaque analyse",
              presencePerMonth: {
                one: "Actual AI Presence : {n} vérification par mois",
                other: "Actual AI Presence : {n} vérifications par mois",
              },
              renews: "Les quotas sont renouvelés chaque mois",
              manage: "Gestion des analyses et du solde depuis le compte",
              note: "Un compte Crawldy est requis",
              cta: "S’abonner",
            },
            perMonth: "/ mois",
            priceOnRequest: "Prix sur demande",
            loadFailed: "Impossible de charger les offres actuelles. La vérification gratuite fonctionne malgré tout — réessayez cette page plus tard.",
          }}
        />
      </Section>
    </>
  );
}

export const fr: LocalizedPage = {
  slug: "tarifs",
  title: "Tarifs Crawldy — une analyse de site, trois modes de paiement",
  h1: "Combien coûte l’analyse d’un site ?",
  description:
    "Une analyse à l'unité, un pack qui n'expire pas ou un plan mensuel — chaque option est la même analyse complète du site pour la recherche et l'IA, avec Actual AI Presence inclus dans les formats payants.",
  navLabel: "Tarifs",
  Body,
};
