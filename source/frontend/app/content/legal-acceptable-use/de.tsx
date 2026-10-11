/**
 * legal-acceptable-use — de. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Diese Regeln schützen die Nutzer, Crawldy und die analysierten Websites." },
  { kind: "heading", text: "Zulässige Nutzung" },
  { kind: "para", text: "Sie dürfen öffentliche Seiten eigener, organisatorischer oder autorisierter Kundensites analysieren und Berichte berechtigten Kunden bereitstellen." },
  { kind: "heading", text: "Unzulässige Nutzung" },
  { kind: "para", text: "Sie dürfen Crawldy nicht verwenden, um:" },
  {
    kind: "list",
    items: [
      "eine Website zu rechtswidrigen, betrügerischen, schädlichen oder belästigenden Zwecken zu analysieren;",
      "auf Seiten, Dateien oder Systeme zuzugreifen, die nicht öffentlich sind;",
      "Crawldy Passwörter, Token, private Links, geheime Schlüssel oder andere Zugangsdaten zu übermitteln;",
      "Anmeldung, CAPTCHA, Turnstile, Ratenbegrenzungen, technische Sperren oder andere Schutzmaßnahmen zu umgehen;",
      "Schwachstellen auszunutzen, Penetrationstests durchzuführen, Schadcode zu verbreiten, eine Dienstverweigerung herbeizuführen oder zerstörerische Tests vorzunehmen;",
      "absichtlich übermäßige Last zu erzeugen oder technische Grenzen über mehrere Sitzungen, Konten oder Organisationen zu umgehen;",
      "die Privatsphäre, Urheberrechte, Marken, vertragliche Beschränkungen oder andere Rechte Dritter zu verletzen;",
      "Konten, Guthaben oder automatisierten Zugang weiterzuverkaufen oder Crawldy ohne gesonderte Vereinbarung zu kopieren;",
      "einen Bericht als offizielle Zertifizierung von Sicherheit, Barrierefreiheit, Rechtskonformität, Suchplatzierung oder KI-Empfehlung darzustellen.",
    ],
  },
  { kind: "heading", text: "Wie die Analyse funktioniert" },
  { kind: "para", text: "Crawldy liest beobachtbare Signale öffentlicher Seiten. Ohne eine gesonderte, ausdrücklich vereinbarte Funktion und eine rechtmäßige Grundlage darf der Dienst sich nicht in private Kontobereiche einloggen, Zugangsdaten eingeben, Formulare absenden, Schutzmechanismen umgehen oder intrusive Prüfungen durchführen." },
  { kind: "heading", text: "Schutz des Dienstes" },
  { kind: "para", text: "Wir können eine Analyse stoppen oder verlangsamen, wenn sie ein Risiko für die Zielseite, für Crawldy oder für andere Nutzer darstellt oder gegen das Gesetz verstößt. Der technische Schutz vor Missbrauch ist von den Tarifrechten getrennt." },
  { kind: "para", text: "Maßnahmen sollen sich möglichst auf die problematische Analyse oder den Nutzer beschränken. Eine Kündigung von Monthly oder eine technische Sperre löscht rechtmäßig erworbene Pack-Analysen nicht, sofern sie nicht erstattet wurden und weder bestätigter Betrug noch eine gesetzliche Anforderung vorliegt." },
  { kind: "heading", text: "Missbrauch melden" },
  { kind: "para", text: "Melden Sie vermuteten Missbrauch über das geschützte Kontaktformular mit Domain, Zeitpunkt und verfügbaren technischen Angaben. Senden Sie keine Geheimnisse." },
  { kind: "heading", text: "Folgen eines Verstoßes" },
  { kind: "para", text: "Je nach Schwere können wir den Nutzer warnen, eine Analyse stoppen, den Zugang vorübergehend einschränken oder ein Konto beenden. Wir können erforderliche Nachweise aufbewahren und uns an die zuständigen Behörden wenden, wenn das Gesetz oder die Abwehr einer realen Gefahr dies verlangt." },
  { kind: "heading", text: "Kontakt" },
  { kind: "para", text: "LLC “Accurly”, ukrainische Unternehmenskennzahl 46295102." },
  { kind: "para", text: "Nutzen Sie das geschützte Crawldy-Kontaktformular." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Zulässige Nutzung",
        meta: ["**Gültig ab:** `1. Januar 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Inhalt",
        relatedLabel: "Verwandte Dokumente",
        related: [
    { label: "Datenschutz und Cookies", href: "/de/datenschutz" },
    { label: "Nutzungsbedingungen", href: "/de/nutzungsbedingungen" },
    { label: "Rückerstattungen und Kündigung", href: "/de/rueckerstattungen" },
    { label: "Kontakt", href: "/de/kontakt" },
        ],
      }}
    />
  );
}

export const de: LocalizedPage = {
  slug: "zulaessige-nutzung",
  title: "Zulässige Nutzung — Crawldy",
  h1: "Zulässige Nutzung",
  description: "Sie dürfen öffentliche Seiten eigener, organisatorischer oder autorisierter Kundensites analysieren und Berichte berechtigten Kunden bereitstellen.",
  navLabel: "Zulässige Nutzung",
  Body,
};
