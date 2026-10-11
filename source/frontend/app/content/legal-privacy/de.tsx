/**
 * legal-privacy — de. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Diese Richtlinie erläutert, welche Daten Crawldy verarbeitet, warum sie benötigt werden, wer sie erhalten kann und welche Rechte Nutzer haben." },
  { kind: "heading", text: "Verantwortlicher" },
  { kind: "para", text: "Crawldy wird von der LIMITED LIABILITY COMPANY “Accurly” (LLC “Accurly”), ukrainische Unternehmenskennzahl 46295102, betrieben. Eingetragene Anschrift: 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Nutzen Sie für Datenschutzfragen das geschützte Crawldy-Kontaktformular und wählen Sie „Datenschutz und Daten“." },
  { kind: "heading", text: "Geltungsbereich" },
  { kind: "para", text: "Diese Richtlinie gilt für `crawldy.ai und crawldy.com`, die kostenlose Vorschau, kostenpflichtige Analysen, Actual AI Presence, Konten, den Kundenbereich, Zahlungen und das Kontaktformular." },
  { kind: "heading", text: "Verarbeitete Daten" },
  { kind: "para", text: "**Website und Analyse.** Wir verarbeiten die eingegebene URL und Domain, öffentlich zugängliche Seiten, Serverantworten, Header, Metadaten, Links, strukturierte Daten, Leistungswerte, Feststellungen, Nachweise, Abdeckung und Bewertungen." },
  { kind: "para", text: "**Konto.** Bei der Kontoerstellung verarbeiten wir Name, E-Mail-Adresse, Anmeldedaten, Organisationszugehörigkeit, Analyseverlauf, gekaufte Guthaben und Nutzung." },
  { kind: "para", text: "**Zahlung.** Paddle verarbeitet Zahlungsdaten im Checkout. Crawldy erhält keine vollständige Kartennummer. Wir speichern Kunden- oder Transaktionskennung, Produkt, Betrag, Währung, Zahlungs- und Abonnementstatus, Erstattungsdaten und Angaben, die zur Bereitstellung und Abrechnung erforderlich sind." },
  { kind: "para", text: "**Actual AI Presence.** Für eine bezahlte Analyse können wir Anfragen zu Marke, Website, Unternehmen, Markt oder Leistungen erstellen und an OpenAI, Anthropic, Google und Perplexity senden. Wir speichern Anfrage, Antwort, Datum, Modell, Status und Beobachtung. Die kostenlose Vorschau führt Actual AI Presence nicht aus." },
  { kind: "para", text: "**Kontakt und Sicherheit.** Wir verarbeiten Name, Antwortadresse, Betreff, Nachricht, Zustellstatus und das Cloudflare-Turnstile-Ergebnis. Außerdem können IP-Adresse, Browser, Gerät, Sprache, Zeitpunkt, Fehlerprotokolle, Sitzungskennungen, Ratenbegrenzungen und Missbrauchssignale verarbeitet werden." },
  { kind: "heading", text: "Zwecke der Verarbeitung" },
  { kind: "para", text: "Wir verwenden Daten, um die angegebene Website zu analysieren und das Ergebnis zu erstellen, einen gekauften Bericht bereitzustellen, das Pack-Guthaben zu speichern oder Monthly zu verwalten, Actual AI Presence nach der Zahlung auszuführen, ein Konto zu erstellen und zu schützen, Zahlungen, Erstattungen oder Kündigungen zu bestätigen, Anfragen zu beantworten, Fehler, Betrug, automatisierten Missbrauch und Sicherheitsbedrohungen zu erkennen, buchhalterische, steuerliche und andere rechtliche Pflichten zu erfüllen sowie die Zuverlässigkeit und Verständlichkeit von Crawldy auf Grundlage aggregierter oder anonymisierter Daten zu verbessern." },
  { kind: "heading", text: "Rechtsgrundlagen" },
  { kind: "para", text: "Je nach Fall stützen wir die Verarbeitung auf Vertragserfüllung oder vorvertragliche Maßnahmen, gesetzliche Pflichten, berechtigte Interessen am sicheren Betrieb oder Ihre Einwilligung. Eine Einwilligung wird für optionale Analyse- oder Marketing-Cookies verwendet, falls solche Werkzeuge aktiviert werden." },
  { kind: "heading", text: "Automatisierte Analyse" },
  { kind: "para", text: "Crawldy erzeugt automatisch technische Feststellungen, Bewertung, Abdeckung und Prioritäten. Dies ist keine Entscheidung mit rechtlicher oder ähnlich erheblicher Wirkung über eine Person. Bei unzureichenden Daten kann die Gesamtbewertung fehlen." },
  { kind: "heading", text: "Empfänger" },
  { kind: "para", text: "Daten werden nur im erforderlichen Umfang weitergegeben:" },
  {
    kind: "list",
    items: [
      "an Paddle für Checkout, Zahlungen, Steuern, Belege, Abonnements und Erstattungen;",
      "an Cloudflare für Turnstile und aktivierte Sicherheitsfunktionen;",
      "an OpenAI, Anthropic, Google und Perplexity für bezahlte Actual AI Presence;",
      "an Anbieter für Hosting, Datenbank, Speicher, Authentifizierung, E-Mail, Monitoring und Backups;",
      "an Berater, Gerichte oder Behörden, wenn dies rechtlich erforderlich ist.",
    ],
  },
  { kind: "para", text: "Wir verkaufen keine personenbezogenen Daten. Passwörter, Zahlungszugangsdaten und Inhalte privater Seiten werden nicht absichtlich an AI-Anbieter gesendet und dürfen nicht an Crawldy übermittelt werden." },
  { kind: "heading", text: "Speicherdauer" },
  {
    kind: "list",
    items: [
      "Daten der kostenlosen Vorschau: bis zu 30 Tage.",
      "Anonym gekaufter Single-Bericht und Zugriffstoken: 12 Monate.",
      "Konto, Berichtsverlauf, Pack und Monthly: während der Kontolaufzeit; nach bestätigter Löschung grundsätzlich innerhalb von 30 Tagen, Backups bis zu 90 Tage.",
      "Kontaktanfragen: bis zu 24 Monate nach Abschluss.",
      "Sicherheits- und Ratenbegrenzungsprotokolle: bis zu 90 Tage, sofern kein längerer Vorfall untersucht wird.",
      "Zahlungs-, Buchhaltungs- und Steuerdaten: für die gesetzlich vorgeschriebene Dauer.",
      "Daten externer Anbieter: nach deren Bedingungen und der tatsächlichen API-Konfiguration.",
    ],
  },
  { kind: "heading", text: "Cookies und lokaler Speicher" },
  { kind: "para", text: "Crawldy kann technisch notwendige Cookies für den Betrieb der Website, die Anmeldung und das Speichern von Nutzereinstellungen verwenden." },
  { kind: "para", text: "Cloudflare Turnstile verarbeitet Browsersignale, um Menschen von automatisierten Anfragen zu unterscheiden. Laut Cloudflare greift Turnstile nicht auf Formulareingaben zu und überträgt sie nicht. Paddle kann im Checkout eigene notwendige Technologien verwenden." },
  { kind: "heading", text: "Ihre Rechte" },
  { kind: "para", text: "Je nach anwendbarem Recht können Sie Auskunft, Kopie, Berichtigung, Löschung, Einschränkung, Widerspruch, Datenübertragbarkeit oder Widerruf einer Einwilligung verlangen. Sie können sich auch bei einer zuständigen Datenschutzbehörde beschweren." },
  { kind: "para", text: "Nutzen Sie das geschützte Kontaktformular und wählen Sie „Datenschutz und Daten“. Wir können einen Identitäts- oder Vertretungsnachweis verlangen." },
  { kind: "heading", text: "Daten Dritter und Kundenseiten" },
  { kind: "para", text: "Sie benötigen eine rechtmäßige Grundlage, um eine Website einzureichen. Übermitteln Sie keine privaten URLs, Passwörter, Token, privaten Dokumente oder Geheimnisse. Wer für einen Kunden handelt, ist für die erforderliche Erlaubnis und Information verantwortlich." },
  { kind: "heading", text: "Berechtigung zur Nutzung des Dienstes" },
  { kind: "para", text: "Der Dienst richtet sich an Nutzer, die rechtlich in der Lage sind, selbstständig verbindliche Verträge zu schließen." },
  { kind: "heading", text: "Sicherheit" },
  { kind: "para", text: "Wir setzen technische und organisatorische Maßnahmen zum Schutz der Daten ein. Kein System kann absolute Sicherheit garantieren. Im Falle eines Vorfalls handeln wir gemäß dem anwendbaren Recht." },
  { kind: "heading", text: "Änderungen der Richtlinie" },
  { kind: "para", text: "Änderungen dieser Richtlinie werden mit Datum und Version veröffentlicht. Über wesentliche Änderungen informieren wir registrierte Nutzer über einen verfügbaren Kanal." },
  { kind: "heading", text: "Kontakt" },
  { kind: "para", text: "LLC “Accurly”, ukrainische Unternehmenskennzahl 46295102." },
  { kind: "para", text: "59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Nutzen Sie das geschützte Crawldy-Kontaktformular." },
  { kind: "para", text: "---" },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Datenschutz und Cookies",
        meta: ["**Gültig ab:** `1. Januar 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Inhalt",
        relatedLabel: "Verwandte Dokumente",
        related: [
    { label: "Nutzungsbedingungen", href: "/de/nutzungsbedingungen" },
    { label: "Rückerstattungen und Kündigung", href: "/de/rueckerstattungen" },
    { label: "Zulässige Nutzung", href: "/de/zulaessige-nutzung" },
    { label: "Kontakt", href: "/de/kontakt" },
        ],
      }}
    />
  );
}

export const de: LocalizedPage = {
  slug: "datenschutz",
  title: "Datenschutz und Cookies — Crawldy",
  h1: "Datenschutz und Cookies",
  description: "Diese Richtlinie erläutert, welche Daten Crawldy verarbeitet, warum sie benötigt werden, wer sie erhalten kann und welche Rechte Nutzer haben.",
  navLabel: "Datenschutz und Cookies",
  Body,
};
