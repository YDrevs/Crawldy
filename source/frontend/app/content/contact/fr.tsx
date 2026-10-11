/**
 * Контакти — fr. Єдина цільова дія сторінки: відкрити захищену форму
 * й справді надіслати повідомлення. Відкритої адреси пошти немає в
 * жодному стані — її збирають поштові роботи, і живе вона на сервері.
 * CTA перевірки сайту тут немає навмисно (рішення власника, екран 12).
 */

import { ContactForm } from "../../components/ContactForm";
import { Hero } from "../../components/sections";
import type { LocalizedPage } from "../../lib/page-types";

function Body() {
  return (
    <Hero
      eyebrow={"CONTACT"}
      title={"Contactez-nous"}
      lead={"Des questions sur Crawldy, le paiement ou les résultats d'une analyse ? Envoyez-nous un message via le formulaire."}
      action={
        <ContactForm
          locale="fr"
          strings={{
            open: "Nous contacter",
            name: "Nom",
            email: "E-mail",
            site: "Adresse du site",
            siteOptional: "(facultatif)",
            message: "Message",
            submit: "Envoyer le message",
            sending: "Envoi…",
            close: "Annuler",
            success: "Message envoyé. Nous répondrons à l'adresse e-mail indiquée.",
            failure: "Le message n'a pas pu être envoyé. Réessayez un peu plus tard.",
            invalidName: "Saisissez votre nom.",
            invalidEmail: "Saisissez une adresse e-mail valide.",
            invalidMessage: "Écrivez un message d'au moins quelques mots.",
            invalidSite: "Saisissez une adresse de site, par exemple example.com.",
            rejected: "Nous n'avons pas pu confirmer que la demande venait d'une personne. Rechargez la page et réessayez.",
            tooMany: "Trop de requêtes. Réessayez plus tard."
          }}
        />
      }
    />
  );
}

export const fr: LocalizedPage = {
  slug: "contact",
  title: "Contacter Crawldy",
  h1: "Contactez-nous",
  description:
    "Questions sur Crawldy, le paiement ou les résultats d'une analyse : envoyez un message via le formulaire protégé.",
  navLabel: "Contact",
  Body,
};
