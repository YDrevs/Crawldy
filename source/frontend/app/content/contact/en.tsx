/**
 * Контакти — en. Єдина цільова дія сторінки: відкрити захищену форму
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
      title={"Get in touch"}
      lead={"Questions about Crawldy, payment or the results of an analysis? Send us a message through the form."}
      action={
        <ContactForm
          locale="en"
          strings={{
            open: "Contact us",
            name: "Name",
            email: "Email",
            site: "Website address",
            siteOptional: "(optional)",
            message: "Message",
            submit: "Send message",
            sending: "Sending…",
            close: "Cancel",
            success: "Message sent. We will reply to the email address you gave.",
            failure: "The message could not be sent. Please try again a little later.",
            invalidName: "Enter your name.",
            invalidEmail: "Enter a valid email address.",
            invalidMessage: "Write a message of at least a few words.",
            invalidSite: "Enter a website address like example.com.",
            rejected: "We could not confirm that the request came from a person. Reload the page and try again.",
            tooMany: "Too many requests. Please try again later."
          }}
        />
      }
    />
  );
}

export const en: LocalizedPage = {
  slug: "contact",
  title: "Contact Crawldy",
  h1: "Get in touch",
  description:
    "Questions about Crawldy, payment or the results of an analysis — send a message through the protected form.",
  navLabel: "Contact",
  Body,
};
