/**
 * Контакти — de. Єдина цільова дія сторінки: відкрити захищену форму
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
      eyebrow={"KONTAKT"}
      title={"Kontaktieren Sie uns"}
      lead={"Fragen zu Crawldy, zur Zahlung oder zu den Ergebnissen einer Prüfung? Senden Sie uns eine Nachricht über das Formular."}
      action={
        <ContactForm
          locale="de"
          strings={{
            open: "Kontakt aufnehmen",
            name: "Name",
            email: "E-Mail",
            site: "Website-Adresse",
            siteOptional: "(optional)",
            message: "Nachricht",
            submit: "Nachricht senden",
            sending: "Wird gesendet…",
            close: "Abbrechen",
            success: "Nachricht gesendet. Wir antworten an die angegebene E-Mail-Adresse.",
            failure: "Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es etwas später erneut.",
            invalidName: "Geben Sie Ihren Namen ein.",
            invalidEmail: "Geben Sie eine gültige E-Mail-Adresse ein.",
            invalidMessage: "Schreiben Sie eine Nachricht von mindestens ein paar Wörtern.",
            invalidSite: "Geben Sie eine Website-Adresse ein, z. B. example.com.",
            rejected: "Wir konnten nicht bestätigen, dass die Anfrage von einem Menschen kam. Laden Sie die Seite neu und versuchen Sie es erneut.",
            tooMany: "Zu viele Anfragen. Bitte versuchen Sie es später erneut."
          }}
        />
      }
    />
  );
}

export const de: LocalizedPage = {
  slug: "kontakt",
  title: "Kontakt zu Crawldy",
  h1: "Kontaktieren Sie uns",
  description:
    "Fragen zu Crawldy, zur Zahlung oder zu Prüfergebnissen — senden Sie eine Nachricht über das geschützte Formular.",
  navLabel: "Kontakt",
  Body,
};
