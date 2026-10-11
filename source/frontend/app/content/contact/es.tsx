/**
 * Контакти — es. Єдина цільова дія сторінки: відкрити захищену форму
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
      eyebrow={"CONTACTO"}
      title={"Ponte en contacto con nosotros"}
      lead={"¿Tienes preguntas sobre Crawldy, el pago o los resultados de un análisis? Envíanos un mensaje a través del formulario."}
      action={
        <ContactForm
          locale="es"
          strings={{
            open: "Contactar con nosotros",
            name: "Nombre",
            email: "Email",
            site: "Dirección del sitio",
            siteOptional: "(opcional)",
            message: "Mensaje",
            submit: "Enviar mensaje",
            sending: "Enviando…",
            close: "Cancelar",
            success: "Mensaje enviado. Responderemos a la dirección de correo indicada.",
            failure: "No se pudo enviar el mensaje. Inténtalo de nuevo un poco más tarde.",
            invalidName: "Introduce tu nombre.",
            invalidEmail: "Introduce un correo electrónico válido.",
            invalidMessage: "Escribe un mensaje de al menos unas pocas palabras.",
            invalidSite: "Introduce una dirección como example.com.",
            rejected: "No pudimos confirmar que la solicitud la envió una persona. Recarga la página e inténtalo de nuevo.",
            tooMany: "Demasiadas solicitudes. Inténtalo de nuevo más tarde."
          }}
        />
      }
    />
  );
}

export const es: LocalizedPage = {
  slug: "contacto",
  title: "Contacto de Crawldy",
  h1: "Ponte en contacto con nosotros",
  description:
    "Preguntas sobre Crawldy, el pago o los resultados de un análisis: envía un mensaje mediante el formulario protegido.",
  navLabel: "Contacto",
  Body,
};
