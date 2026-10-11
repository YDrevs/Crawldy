/**
 * legal-terms — de. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Diese Bedingungen regeln Crawldy, die kostenlose Vorschau, kostenpflichtige Berichte, Konten, Pack, Monthly und Actual AI Presence." },
  { kind: "heading", text: "Parteien" },
  { kind: "para", text: "Crawldy wird von LLC “Accurly”, ukrainische Unternehmenskennzahl 46295102, mit eingetragener Anschrift 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine, betrieben." },
  { kind: "heading", text: "Zustimmung zu den Bedingungen" },
  { kind: "para", text: "„Sie“ bezeichnet die nutzende Person oder Organisation. Wer für eine Organisation handelt, bestätigt seine Vertretungsbefugnis. Durch die Nutzung von Crawldy, die Erstellung eines Kontos oder den Kauf einer Leistung stimmen Sie diesen Bedingungen, der Datenschutzrichtlinie, der Erstattungsrichtlinie und den Regeln zur zulässigen Nutzung zu. Vor der Zahlung muss der Nutzer die jeweils aktuellen Fassungen dieser Dokumente öffnen und speichern können. Konten erstellen und Leistungen kaufen können Nutzer, die rechtlich in der Lage sind, selbstständig verbindliche Verträge zu schließen." },
  { kind: "heading", text: "Leistung" },
  { kind: "para", text: "Crawldy analysiert zugängliche Website-Seiten und erstellt einen Bericht über Sichtbarkeit in Suche und KI, technischen Zustand, Leistung, Barrierefreiheit und beobachtbare grundlegende Schutzsignale. Der Bericht zeigt Abdeckung, Feststellungen, Nachweise, Auswirkungen und Prioritäten. Er bildet den Zustand zum Zeitpunkt der Analyse ab." },
  { kind: "heading", text: "Kostenlose Vorschau" },
  { kind: "para", text: "Die kostenlose Vorschau funktioniert ohne Konto und ohne kommerzielle Begrenzung der Anzahl. Sie zeigt Gesamtbewertung, Abdeckung und wenige Hauptprobleme. Sie schaltet keinen vollständigen Bericht oder bezahlten Anspruch frei und führt Actual AI Presence nicht aus. Technische Schutz- und Ratenbegrenzungen sind keine Tarifquote." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Single ist der einmalige Kauf des vollständigen Berichts für genau ein Audit. Ein Konto ist nicht erforderlich. Nach bestätigter Zahlung erhält der Käufer einen geschützten Link, der 12 Monate verfügbar ist. Eine spätere Kontoerstellung ist freiwillig. Die Zuordnung zum Konto erfolgt nur nach Eigentumsnachweis." },
  { kind: "para", text: "Single enthält die vor Zahlung angezeigte Anzahl Actual AI Presence. In der Startkonfiguration ist es eine Prüfung." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Pack benötigt ein Konto und enthält die vor Zahlung angezeigte Zahl vollständiger Analysen und Actual AI Presence. Ungenutzte Pack-Analysen verfallen nicht und werden durch Monthly nicht entfernt. Pack ist kein Abonnement und verlängert sich nicht automatisch." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly benötigt ein Konto und verlängert sich monatlich zum angezeigten Preis. Es enthält unbegrenzt viele vollständige Website-Analysen und eine gesondert konfigurierte Zahl Actual AI Presence je bezahltem Monat." },
  { kind: "para", text: "„Unbegrenzt“ bedeutet keine kommerzielle Anzahlgrenze. Angemessene technische Raten-, Warteschlangen- und Parallelitätskontrollen dürfen der Sicherheit dienen, aber keine versteckte Tarifquote bilden. Actual AI Presence ist begrenzt und wird zu Beginn jedes bezahlten Zeitraums zurückgesetzt; ungenutzte Mengen werden nicht übertragen, sofern der Plan nichts anderes sagt." },
  { kind: "para", text: "Monthly kann im Kundenbereich oder im verfügbaren Abonnementwerkzeug gekündigt werden. Die Kündigung stoppt die nächste Verlängerung; der Zugang bleibt bis zum Ende des bezahlten Zeitraums. Eine Organisation darf nicht zwei gleichzeitige nicht beendete Monthly-Abonnements haben." },
  { kind: "heading", text: "Zulässige Ziele" },
  { kind: "para", text: "Sie dürfen eine Website analysieren, die Ihnen, Ihrer Organisation oder einem Kunden gehört, der die Analyse ordnungsgemäß autorisiert hat. Öffentliche Seiten dürfen zu einem rechtmäßigen Zweck analysiert werden. Übermitteln Sie keine Passwörter, Token, privaten Links, Kontobereiche, vertraulichen Dokumente oder eine Adresse, deren Analyse gegen Gesetze, Verträge oder Rechte einer anderen Person verstoßen würde." },
  { kind: "heading", text: "Actual AI Presence" },
  { kind: "para", text: "Actual AI Presence stellt externen AI-Anbietern formulierte Fragen und zeichnet die zu einem bestimmten Zeitpunkt erhaltenen Antworten auf. Die Zusammensetzung der Modelle, ihre Verfügbarkeit, die Regeln und die Antworten der Anbieter können sich ändern. Das Ergebnis garantiert nicht, dass die Marke einem anderen Nutzer, zu einem anderen Zeitpunkt, in einem anderen Land oder bei einer anders formulierten Anfrage erwähnt oder nicht erwähnt wird." },
  { kind: "heading", text: "Zahlung über Paddle" },
  { kind: "para", text: "Zahlungen erfolgen über Paddle. Im Standardmodell handelt Paddle als autorisierter Wiederverkäufer und Merchant of Record und bearbeitet Zahlung, anwendbare Steuern und Beleg. LLC “Accurly” betreibt Crawldy und stellt den Servicezugang bereit." },
  { kind: "para", text: "Der Checkout zeigt Produkt, Preis, Währung, Steuern und Verlängerung. Bezahlter Zugang entsteht erst nach bestätigter Zahlung. Ein geschlossenes Checkout-Fenster ist kein Zahlungsnachweis. Bei ungeklärtem Status wird keine zweite Zahlung angeboten, bevor die erste Transaktion abgeglichen ist." },
  { kind: "heading", text: "Fehlgeschlagene Analysen" },
  { kind: "para", text: "Bei einem technischen Fehler von Crawldy können wir die Analyse wiederholen, ein verwendetes Pack- oder Monthly-Recht wiederherstellen oder Single nach der Erstattungsrichtlinie erstatten. Ist die Zielseite nicht verfügbar oder blockiert sie den Zugriff, zeigt Crawldy die tatsächliche Abdeckung und erfindet keine Daten." },
  { kind: "heading", text: "Konto und Sicherheit" },
  { kind: "para", text: "Sie sind für Kontodaten, Anmeldeschutz und Nutzer Ihrer Organisation verantwortlich. Geschützte Gastlinks dürfen nicht an Unbefugte weitergegeben werden." },
  { kind: "heading", text: "Nutzung des Berichts und Eigentum" },
  { kind: "para", text: "Sie dürfen den gekauften Bericht innerhalb Ihrer Organisation nutzen, herunterladen und weitergeben. Eine Agentur oder ein Berater darf die Website eines Kunden analysieren und den Bericht an diesen Kunden weitergeben, wenn dessen Zustimmung vorliegt. Dies berechtigt nicht zum Weiterverkauf von Konten, Guthaben, automatisiertem Zugang oder Crawldy selbst ohne eine gesonderte Vereinbarung. Software, Design, Methodik, Prüfkatalog und Kennzeichen von Crawldy bleiben Eigentum von LLC “Accurly” oder der jeweiligen Rechteinhaber." },
  { kind: "heading", text: "Grenzen" },
  { kind: "para", text: "Crawldy ist ein automatisiertes Informationswerkzeug. Der Bericht ist keine Garantie für Ranking, Indexierung oder AI-Erwähnung, kein Penetrationstest, keine Schwachstellen- oder Sicherheitszertifizierung, keine WCAG-Zertifizierung, keine Rechts- oder Finanzberatung und keine automatische Website-Änderung." },
  { kind: "heading", text: "Verfügbarkeit des Dienstes" },
  { kind: "para", text: "Wir garantieren keinen ununterbrochenen oder fehlerfreien Betrieb." },
  { kind: "heading", text: "Sperrung des Zugangs" },
  { kind: "para", text: "Wir können den Zugang aus Sicherheits-, Rechts-, Missbrauchs-, Betrugs- oder Zahlungsgründen begrenzen. Ein technisches Limit oder eine Monthly-Kündigung löscht keine gesondert gekauften Pack-Rechte, außer nach Erstattung, bestätigtem Betrug, Chargeback oder gesetzlicher Pflicht." },
  { kind: "heading", text: "Haftung" },
  { kind: "para", text: "Unabdingbare Haftung und zwingende Verbraucherrechte bleiben unberührt. Soweit gesetzlich zulässig, haftet LLC “Accurly” nicht für indirekte Schäden, entgangenen Gewinn, verlorene Rankings, erwartete AI-Erwähnungen oder Entscheidungen, die nur auf dem automatisierten Bericht beruhen. Die Gesamthaftung ist bei Single oder Pack auf den dafür gezahlten Betrag und bei Monthly auf die Zahlungen der letzten 12 Monate begrenzt. Dies gilt nicht bei Vorsatz, Betrug, grober Fahrlässigkeit oder sonstiger unabdingbarer Haftung." },
  { kind: "heading", text: "Beendigung der Nutzung" },
  { kind: "para", text: "Sie können Monthly kündigen, die Nutzung beenden und Ihr Konto löschen. Gesetzlich aufzubewahrende Daten bleiben erhalten." },
  { kind: "heading", text: "Anwendbares Recht" },
  { kind: "para", text: "Es gilt ukrainisches Recht. Zuständig sind die zuständigen Gerichte der Ukraine, soweit zwingende Verbraucherschutzvorschriften dem Nutzer nicht das Recht geben, ein anderes Gericht anzurufen oder anderes zwingendes Recht anzuwenden. Zunächst werden die Parteien versuchen, die Angelegenheit über das geschützte Kontaktformular zu klären." },
  { kind: "heading", text: "Änderungen der Bedingungen" },
  { kind: "para", text: "Wesentliche Änderungen gelten nicht rückwirkend für abgeschlossene Einmalkäufe und werden registrierten Nutzern mitgeteilt." },
  { kind: "heading", text: "Kontakt" },
  { kind: "para", text: "LLC “Accurly”, ukrainische Unternehmenskennzahl 46295102." },
  { kind: "para", text: "Nutzen Sie das geschützte Crawldy-Kontaktformular." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Nutzungsbedingungen",
        meta: ["**Gültig ab:** `1. Januar 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Inhalt",
        relatedLabel: "Verwandte Dokumente",
        related: [
    { label: "Datenschutz und Cookies", href: "/de/datenschutz" },
    { label: "Rückerstattungen und Kündigung", href: "/de/rueckerstattungen" },
    { label: "Zulässige Nutzung", href: "/de/zulaessige-nutzung" },
    { label: "Kontakt", href: "/de/kontakt" },
        ],
      }}
    />
  );
}

export const de: LocalizedPage = {
  slug: "nutzungsbedingungen",
  title: "Nutzungsbedingungen — Crawldy",
  h1: "Nutzungsbedingungen",
  description: "Diese Bedingungen regeln Crawldy, die kostenlose Vorschau, kostenpflichtige Berichte, Konten, Pack, Monthly und Actual AI Presence.",
  navLabel: "Nutzungsbedingungen",
  Body,
};
