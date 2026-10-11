/**
 * legal-refunds — de. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Diese freiwilligen Regeln beschränken keine zwingenden gesetzlichen Rechte." },
  { kind: "heading", text: "Geschlossener Checkout" },
  { kind: "para", text: "Wird der Checkout vor Abschluss geschlossen, bleibt das Audit gespeichert. Eine Belastung erfolgt nur nach Bestätigung durch Paddle. Nachdem bestätigt wurde, dass die Zahlung nicht abgeschlossen ist, können Sie die Zahlung für dasselbe Audit wiederholen." },
  { kind: "para", text: "Bei ungeklärtem Status prüft Crawldy zuerst die Transaktion und bietet keine doppelte Zahlung an." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Die Erstellung des vollständigen Berichts beginnt auf Ihren Wunsch unmittelbar nach bestätigter Zahlung. Nach erfolgreicher Erstellung und Öffnung gibt es keine freiwillige Erstattung wegen Meinungsänderung, außer wenn das Gesetz sie verlangt." },
  { kind: "para", text: "Wir erstatten den Betrag oder wiederholen die Analyse ohne zusätzliche Kosten, wenn:" },
  {
    kind: "list",
    items: [
      "eine Zahlung doppelt erfolgt ist;",
      "eine Belastung erfolgt ist, aber kein bezahlter Zugang bereitgestellt wurde;",
      "ein technischer Fehler von Crawldy keinen nutzbaren vollständigen Bericht zulässt und sich nicht durch einen erneuten Lauf in angemessener Zeit beheben lässt.",
    ],
  },
  { kind: "para", text: "Eine niedrige Bewertung, Feststellungen oder eine fehlende erwartete AI-Erwähnung sind allein kein technischer Fehler." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Ein vollständig ungenutztes Pack kann innerhalb von 14 Kalendertagen erstattet werden. Nach Nutzung einer vollständigen Analyse oder Actual AI Presence gibt es keine freiwillige Gesamterstattung, außer nach zwingendem Recht." },
  { kind: "para", text: "Bei einem Crawldy-Fehler wird das verbrauchte Recht wiederhergestellt. Ungenutzte Pack-Rechte verfallen nicht." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly kann jederzeit für zukünftige Verlängerungen gekündigt werden. Der Zugang bleibt bis zum Ende des bezahlten Zeitraums." },
  { kind: "para", text: "Die erste Zahlung kann innerhalb von 14 Kalendertagen erstattet werden, wenn danach keine vollständige Analyse und kein Actual AI Presence ausgeführt wurde." },
  { kind: "para", text: "Die letzte automatische Verlängerung kann innerhalb von 7 Kalendertagen erstattet werden, wenn im neuen Zeitraum keine dieser Leistungen genutzt wurde. Nach Nutzung gibt es keine freiwillige anteilige Erstattung, außer nach zwingendem Recht." },
  { kind: "para", text: "Eine Kündigung entfernt keine Pack-Rechte." },
  { kind: "heading", text: "Technische Probleme der Zielseite" },
  { kind: "para", text: "Ist die Zielseite nicht verfügbar, blockiert sie die Analyse, ist die angegebene Adresse fehlerhaft oder antwortet die Website nur teilweise, zeigt Crawldy die tatsächliche Abdeckung. Wir prüfen einen erneuten Lauf oder eine Erstattung, wenn das Ergebnis nicht als nutzbar angesehen werden kann und die Einschränkung vor dem Kauf nicht erkennbar war." },
  { kind: "heading", text: "Antrag stellen" },
  { kind: "para", text: "Nutzen Sie das geschützte Kontaktformular und wählen Sie „Zahlung, Rückerstattung oder Abonnement“. Geben Sie Antwortadresse, Domain, ungefähres Kaufdatum und Transaktions- oder Belegkennung an." },
  { kind: "para", text: "Senden Sie keine Kartennummer, keine Prüfziffer und keine Bankzugangsdaten." },
  { kind: "para", text: "Wir bestätigen den Eingang Ihrer Anfrage und teilen die Entscheidung oder die noch benötigten Angaben mit. Genehmigte Erstattungen erfolgen über Paddle an die ursprüngliche Zahlungsmethode. Wie lange die Gutschrift dauert, hängt von Paddle, der Bank und der Zahlungsmethode ab." },
  { kind: "heading", text: "Chargebacks und Betrug" },
  { kind: "para", text: "Wird eine Zahlung ohne vorherige Kontaktaufnahme angefochten, können wir die damit verbundenen Rechte für die Dauer der Prüfung aussetzen. Zwingende Rechte des Nutzers bleiben davon unberührt. Eine bestätigte Erstattung, ein Chargeback oder eine betrügerische Zahlung kann zur Aufhebung des entsprechenden ungenutzten Zugangs führen." },
  { kind: "heading", text: "Kontakt" },
  { kind: "para", text: "LLC “Accurly”, ukrainische Unternehmenskennzahl 46295102." },
  { kind: "para", text: "Nutzen Sie das geschützte Crawldy-Kontaktformular." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Rückerstattungen und Kündigung",
        meta: ["**Gültig ab:** `1. Januar 2026`", "**Version:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Inhalt",
        relatedLabel: "Verwandte Dokumente",
        related: [
    { label: "Datenschutz und Cookies", href: "/de/datenschutz" },
    { label: "Nutzungsbedingungen", href: "/de/nutzungsbedingungen" },
    { label: "Zulässige Nutzung", href: "/de/zulaessige-nutzung" },
    { label: "Kontakt", href: "/de/kontakt" },
        ],
      }}
    />
  );
}

export const de: LocalizedPage = {
  slug: "rueckerstattungen",
  title: "Rückerstattungen und Kündigung — Crawldy",
  h1: "Rückerstattungen und Kündigung",
  description: "Diese freiwilligen Regeln beschränken keine zwingenden gesetzlichen Rechte.",
  navLabel: "Rückerstattungen und Kündigung",
  Body,
};
