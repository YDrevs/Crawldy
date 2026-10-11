/**
 * Інвентар публічного тексту (E1, редакція 2) — впроваджені рядки.
 *
 * Кожен рядок зі статусом PROPOSED затверджено власником 2026-09-05 і
 * впроваджено як точну заміну. Тест тримає три речі: значення точне;
 * de/es/fr/ru не падають в англійську там, де ключ додано саме проти
 * фолбеку; старе формулювання не рендериться більше ніде.
 *
 * Правила власника за цими рядками: «нічого не списано» каже лише гілка
 * зі звіреним `charged: false`; невдала оплата каже, що Paddle повідомив
 * про незавершену оплату, а не про відмову банку; `notFound` не натякає на
 * строк; `accountCta` обіцяє лише те, що є зараз.
 */

import { describe, expect, it } from "vitest";

import type { Locale } from "./contracts";
import { plural, translate } from "./i18n";

type Row = [Locale, string, string];

/** locale, key, затверджене значення. */
const APPROVED: Row[] = [
  ["en", "free.auditFailedLead", "We could not complete the run. Try the address again, or a different one."],
  ["en", "free.payment.failed.lead", "Paddle reported that the payment was not completed. You can try again with the same or a different card."],
  ["en", "free.payment.unavailable.lead", "This is on our side, not yours. Please try again in a moment."],
  ["en", "free.accountCta", "Create an account to keep this check in your dashboard."],
  ["uk", "free.auditFailedLead", "Прогін не вдався. Спробуйте цю адресу ще раз або іншу."],
  ["uk", "free.payment.failed.lead", "Paddle повідомив, що оплату не завершено. Спробуйте ще раз тією самою або іншою карткою."],
  ["uk", "free.payment.unavailable.lead", "Це на нашому боці, не на вашому. Спробуйте, будь ласка, ще раз за хвилину."],
  ["uk", "free.accountCta", "Створіть акаунт, щоб ця перевірка лишилася у вашому кабінеті."],
  ["de", "free.payment.failed.lead", "Paddle hat gemeldet, dass die Zahlung nicht abgeschlossen wurde. Sie können es mit derselben oder einer anderen Karte erneut versuchen."],
  ["de", "free.payment.unavailable.lead", "Das liegt an uns, nicht an Ihnen. Bitte versuchen Sie es gleich noch einmal."],
  ["de", "free.accountCta", "Erstellen Sie ein Konto, damit diese Prüfung in Ihrem Konto bleibt."],
  ["de", "free.auditFailedTitle", "Die Prüfung wurde nicht abgeschlossen"],
  ["de", "free.auditFailedLead", "Wir konnten die Prüfung nicht abschließen. Versuchen Sie es mit dieser Adresse erneut oder mit einer anderen."],
  ["es", "free.payment.failed.lead", "Paddle ha informado de que el pago no se completó. Puedes intentarlo de nuevo con la misma tarjeta o con otra."],
  ["es", "free.payment.unavailable.lead", "Esto es cosa nuestra, no tuya. Inténtalo de nuevo en un momento."],
  ["es", "free.accountCta", "Crea una cuenta para conservar este análisis en tu panel."],
  ["es", "free.auditFailedTitle", "El análisis no terminó"],
  ["es", "free.auditFailedLead", "No pudimos completar el análisis. Prueba de nuevo con esta dirección o con otra."],
  ["fr", "free.payment.failed.lead", "Paddle a indiqué que le paiement n’a pas abouti. Vous pouvez réessayer avec la même carte ou une autre."],
  ["fr", "free.payment.unavailable.lead", "Cela vient de nous, pas de vous. Réessayez dans un instant."],
  ["fr", "free.accountCta", "Créez un compte pour conserver cette analyse dans votre espace."],
  ["fr", "free.auditFailedTitle", "L’analyse ne s’est pas terminée"],
  ["fr", "free.auditFailedLead", "Nous n’avons pas pu terminer l’analyse. Réessayez avec cette adresse ou une autre."],
  ["ru", "free.payment.failed.lead", "Paddle сообщил, что оплата не завершена. Можно попробовать ещё раз той же или другой картой."],
  ["ru", "free.payment.unavailable.lead", "Это на нашей стороне, а не на вашей. Попробуйте, пожалуйста, через мгновение."],
  ["ru", "free.accountCta", "Создайте аккаунт, чтобы эта проверка осталась в вашем кабинете."],
  ["ru", "free.auditFailedTitle", "Проверка не завершилась"],
  ["ru", "free.auditFailedLead", "Не удалось завершить проверку. Попробуйте этот адрес ещё раз или другой."],
  ["en", "problem.checkout", "We could not open the payment page. Please try again in a moment."],
  ["en", "problem.notFound", "This check is not available in this browser. Start a new check."],
  ["uk", "problem.checkout", "Не вдалося відкрити сторінку оплати. Спробуйте, будь ласка, за хвилину."],
  ["uk", "problem.notFound", "Ця перевірка недоступна в цьому браузері. Запустіть нову перевірку."],
  ["de", "problem.checkout", "Die Zahlungsseite ließ sich nicht öffnen. Bitte versuchen Sie es gleich noch einmal."],
  ["de", "problem.alreadyUnlocked", "Dieser Bericht ist bereits freigeschaltet — laden Sie die Seite neu."],
  ["de", "problem.notFound", "Diese Prüfung ist in diesem Browser nicht verfügbar. Starten Sie eine neue Prüfung."],
  ["es", "problem.checkout", "No pudimos abrir la página de pago. Inténtalo de nuevo en un momento."],
  ["es", "problem.alreadyUnlocked", "Este informe ya está desbloqueado: actualiza la página."],
  ["es", "problem.notFound", "Este análisis no está disponible en este navegador. Inicia una comprobación nueva."],
  ["fr", "problem.checkout", "Nous n’avons pas pu ouvrir la page de paiement. Réessayez dans un instant."],
  ["fr", "problem.alreadyUnlocked", "Ce rapport est déjà débloqué : actualisez la page."],
  ["fr", "problem.notFound", "Cette analyse n’est pas disponible dans ce navigateur. Lancez une nouvelle vérification."],
  ["ru", "problem.checkout", "Не удалось открыть страницу оплаты. Попробуйте, пожалуйста, через минуту."],
  ["ru", "problem.alreadyUnlocked", "Этот отчёт уже открыт — обновите страницу."],
  ["ru", "problem.notFound", "Эта проверка недоступна в этом браузере. Запустите новую проверку."],
  ["de", "action.retry", "Erneut versuchen"],
  ["es", "action.retry", "Intentarlo de nuevo"],
  ["fr", "action.retry", "Réessayer"],
  ["ru", "action.retry", "Попробовать снова"],
  ["en", "checkout.unavailableLead", "This is on our side, not yours. Please try again shortly."],
  ["uk", "checkout.unavailableLead", "Це на нашому боці, не на вашому. Спробуйте, будь ласка, за хвилину."],
  ["de", "checkout.openingTitle", "Sichere Zahlung wird geöffnet"],
  ["de", "checkout.openingLead", "Die Zahlung wickelt Paddle ab. Ihre Kartendaten erreichen Crawldy nie."],
  ["de", "checkout.nothingTitle", "Hier gibt es nichts zu bezahlen"],
  ["de", "checkout.nothingLead", "Diese Seite öffnet eine bereits begonnene Zahlung. Kehren Sie zum Ergebnis Ihrer Prüfung zurück und wählen Sie dort den vollständigen Bericht."],
  ["de", "checkout.unavailableTitle", "Zahlungen sind gerade nicht möglich"],
  ["de", "checkout.unavailableLead", "Das liegt an uns, nicht an Ihnen. Bitte versuchen Sie es in Kürze erneut."],
  ["es", "checkout.openingTitle", "Abriendo el pago seguro"],
  ["es", "checkout.openingLead", "Paddle gestiona el pago. Los datos de tu tarjeta nunca llegan a Crawldy."],
  ["es", "checkout.nothingTitle", "Aquí no hay nada que pagar"],
  ["es", "checkout.nothingLead", "Esta página abre un pago ya iniciado. Vuelve al resultado de tu análisis y elige allí el informe completo."],
  ["es", "checkout.unavailableTitle", "Los pagos no están disponibles ahora mismo"],
  ["es", "checkout.unavailableLead", "Esto es cosa nuestra, no tuya. Inténtalo de nuevo en breve."],
  ["fr", "checkout.openingTitle", "Ouverture du paiement sécurisé"],
  ["fr", "checkout.openingLead", "Paddle gère le paiement. Les données de votre carte n’atteignent jamais Crawldy."],
  ["fr", "checkout.nothingTitle", "Rien à payer ici"],
  ["fr", "checkout.nothingLead", "Cette page ouvre un paiement déjà commencé. Revenez au résultat de votre analyse et choisissez-y le rapport complet."],
  ["fr", "checkout.unavailableTitle", "Les paiements sont indisponibles pour le moment"],
  ["fr", "checkout.unavailableLead", "Cela vient de nous, pas de vous. Réessayez sous peu."],
  ["ru", "checkout.openingTitle", "Открываем защищённую оплату"],
  ["ru", "checkout.openingLead", "Оплату проводит Paddle. Данные карты в Crawldy не попадают."],
  ["ru", "checkout.nothingTitle", "Здесь нечего оплачивать"],
  ["ru", "checkout.nothingLead", "Эта страница открывает уже начатую оплату. Вернитесь к результату проверки и выберите там полный отчёт."],
  ["ru", "checkout.unavailableTitle", "Оплата сейчас недоступна"],
  ["ru", "checkout.unavailableLead", "Это на нашей стороне, а не на вашей. Попробуйте, пожалуйста, чуть позже."],
];

/** locale, key, попереднє значення — не має рендеритися. */
const RETIRED: Row[] = [
  ["en", "free.auditFailedLead", "We could not complete the run. Nothing was charged — try the address again, or a different one."],
  ["en", "free.pagesRead", "{read} of {known} pages"],
  ["en", "free.pagesDone", "{read} pages read"],
  ["en", "free.payment.failed.lead", "Your bank or card provider declined the charge. Nothing was taken, and nothing is blocked — you can try again with the same or a different card."],
  ["en", "free.payment.unavailable.lead", "This is on our side, not yours. Nothing was charged — please try again in a moment."],
  ["en", "free.accountCta", "Create an account to save this audit and track future changes."],
  ["uk", "free.auditFailedLead", "Прогін не вдався. Нічого не списано — спробуйте цю адресу ще раз або іншу."],
  ["uk", "free.pagesRead", "{read} з {known} сторінок"],
  ["uk", "free.pagesDone", "прочитано {read} сторінок"],
  ["uk", "free.payment.failed.lead", "Банк або платіжна система відхилили списання. Гроші не знято, і ніщо не заблоковано — спробуйте ще раз тією самою або іншою карткою."],
  ["uk", "free.payment.unavailable.lead", "Це на нашому боці, не на вашому. Нічого не списано — спробуйте, будь ласка, ще раз за хвилину."],
  ["uk", "free.accountCta", "Створіть акаунт, щоб зберегти цей аудит і відстежувати зміни."],
  ["de", "free.pagesRead", "{read} von {known} Seiten"],
  ["de", "free.pagesDone", "{read} Seiten gelesen"],
  ["de", "free.payment.failed.lead", "Ihre Bank oder Ihr Kartenanbieter hat die Belastung abgelehnt. Es wurde nichts abgebucht und nichts gesperrt — Sie können es mit derselben oder einer anderen Karte erneut versuchen."],
  ["de", "free.payment.unavailable.lead", "Das liegt an uns, nicht an Ihnen. Es wurde nichts abgebucht — bitte versuchen Sie es gleich noch einmal."],
  ["de", "free.accountCta", "Erstellen Sie ein Konto, um diese Prüfung zu speichern und Veränderungen zu verfolgen."],
  ["es", "free.pagesRead", "{read} de {known} páginas"],
  ["es", "free.pagesDone", "{read} páginas leídas"],
  ["es", "free.payment.failed.lead", "Tu banco o tu proveedor de tarjeta rechazó el cargo. No se cobró nada ni se bloqueó nada: puedes intentarlo de nuevo con la misma tarjeta o con otra."],
  ["es", "free.payment.unavailable.lead", "Esto es cosa nuestra, no tuya. No se cobró nada: inténtalo de nuevo en un momento."],
  ["es", "free.accountCta", "Crea una cuenta para guardar este análisis y seguir los cambios futuros."],
  ["fr", "free.pagesRead", "{read} pages sur {known}"],
  ["fr", "free.pagesDone", "{read} pages lues"],
  ["fr", "free.payment.failed.lead", "Votre banque ou votre émetteur de carte a refusé le débit. Rien n’a été prélevé et rien n’est bloqué : vous pouvez réessayer avec la même carte ou une autre."],
  ["fr", "free.payment.unavailable.lead", "Cela vient de nous, pas de vous. Rien n’a été prélevé : réessayez dans un instant."],
  ["fr", "free.accountCta", "Créez un compte pour conserver cette analyse et suivre les changements à venir."],
  ["ru", "free.pagesRead", "{read} из {known} страниц"],
  ["ru", "free.pagesDone", "прочитано {read} страниц"],
  ["ru", "free.payment.failed.lead", "Банк или платёжная система отклонили списание. Ничего не списано и ничего не заблокировано — можно попробовать ещё раз той же или другой картой."],
  ["ru", "free.payment.unavailable.lead", "Это на нашей стороне, а не на вашей. Ничего не списано — попробуйте, пожалуйста, через мгновение."],
  ["ru", "free.accountCta", "Создайте аккаунт, чтобы сохранить эту проверку и следить за изменениями."],
  ["en", "problem.checkout", "We could not open the payment page. Nothing was charged — try again in a moment."],
  ["en", "problem.notFound", "This audit was not found. It may have expired — start a new one."],
  ["uk", "problem.checkout", "Не вдалося відкрити сторінку оплати. Нічого не списано — спробуйте за хвилину."],
  ["uk", "problem.notFound", "Цей аудит не знайдено. Можливо, строк минув — запустіть новий."],
  ["en", "checkout.unavailableLead", "This is on our side, not yours. Nothing was charged — please try again shortly."],
  ["uk", "checkout.unavailableLead", "Це на нашому боці, не на вашому. Нічого не списано — спробуйте, будь ласка, за хвилину."],
];

/** locale, key, форми множини за Intl.PluralRules. */
const PLURALS: [Locale, string, Record<string, string>][] = [
  ["en", "free.pagesRead", {"one": "{read} of {known} page", "other": "{read} of {known} pages"}],
  ["en", "free.pagesDone", {"one": "{read} page read", "other": "{read} pages read"}],
  ["uk", "free.pagesRead", {"one": "{read} з {known} сторінки", "few": "{read} з {known} сторінок", "many": "{read} з {known} сторінок"}],
  ["uk", "free.pagesDone", {"one": "прочитано {read} сторінку", "few": "прочитано {read} сторінки", "many": "прочитано {read} сторінок"}],
  ["de", "free.pagesRead", {"one": "{read} von {known} Seite", "other": "{read} von {known} Seiten"}],
  ["de", "free.pagesDone", {"one": "{read} Seite gelesen", "other": "{read} Seiten gelesen"}],
  ["es", "free.pagesRead", {"one": "{read} de {known} página", "other": "{read} de {known} páginas"}],
  ["es", "free.pagesDone", {"one": "{read} página leída", "other": "{read} páginas leídas"}],
  ["fr", "free.pagesRead", {"one": "{read} page sur {known}", "other": "{read} pages sur {known}"}],
  ["fr", "free.pagesDone", {"one": "{read} page lue", "other": "{read} pages lues"}],
  ["ru", "free.pagesRead", {"one": "{read} из {known} страницы", "few": "{read} из {known} страниц", "many": "{read} из {known} страниц"}],
  ["ru", "free.pagesDone", {"one": "прочитана {read} страница", "few": "прочитано {read} страницы", "many": "прочитано {read} страниц"}],
];

const SIX: Locale[] = ["en", "uk", "de", "es", "fr", "ru"];

describe("інвентар E1: затверджені значення", () => {
  it("кожен PROPOSED-рядок несе точне затверджене значення", () => {
    for (const [locale, key, value] of APPROVED) {
      expect(translate(locale, key), `${locale}/${key}`).toBe(value);
    }
  });

  it("de/es/fr/ru не падають в англійську на впроваджених ключах", () => {
    for (const [locale, key] of APPROVED) {
      if (locale === "en") continue;
      const text = translate(locale, key);
      expect(text, `${locale}/${key}`).not.toBe(key);
      expect(text, `${locale}/${key} = англійська`).not.toBe(translate("en", key));
    }
  });

  it("старі формулювання не рендеряться", () => {
    for (const [locale, key, old] of RETIRED) {
      const text = key.startsWith("free.pages")
        ? plural(locale, key, 2, { read: 2, known: 2 })
        : translate(locale, key);
      expect(text, `${locale}/${key}`).not.toBe(old);
    }
  });

  it("платіжні рядки не кажуть «нічого не списано» поза звіреною гілкою", () => {
    // Єдиний рядок із таким твердженням — `free.payment.canceled.lead`,
    // і його показує лише стан зі звіреним `charged: false`.
    const forbidden = [
      "nothing was charged", "nothing was taken", "нічого не списано", "гроші не знято",
      "nichts abgebucht", "nichts berechnet", "no se cobró", "rien n’a été prélevé",
      "ничего не списано", "declined the charge", "відхилили списання", "abgelehnt",
      "rechazó el cargo", "refusé le débit", "отклонили списание",
    ];
    for (const [locale, key] of APPROVED) {
      if (key === "free.payment.canceled.lead") continue;
      const lower = translate(locale, key).toLowerCase();
      for (const phrase of forbidden) {
        expect(lower.includes(phrase), `${locale}/${key}: «${phrase}»`).toBe(false);
      }
    }
  });

  it("«не знайдено» не натякає на строк, а заклик до акаунта не обіцяє відстеження", () => {
    for (const locale of SIX) {
      const notFound = translate(locale, "problem.notFound").toLowerCase();
      for (const phrase of ["expired", "строк", "abgelaufen", "caducado", "expiré", "истёк", "срок"]) {
        expect(notFound.includes(phrase), `${locale}: «${phrase}»`).toBe(false);
      }
      const account = translate(locale, "free.accountCta").toLowerCase();
      for (const phrase of ["track", "відстеж", "verfolgen", "seguir los cambios", "suivre", "следить"]) {
        expect(account.includes(phrase), `${locale}: «${phrase}»`).toBe(false);
      }
    }
  });
});

describe("інвентар E1: форми множини сторінок", () => {
  /** Число, яке дає рівно цю категорію в цій мові. */
  const COUNT: Record<string, number> = { one: 1, few: 2, many: 5 };

  it("кожна форма мови на місці й підставляє числа", () => {
    for (const [locale, key, forms] of PLURALS) {
      for (const [form, expected] of Object.entries(forms)) {
        const count = form === "other" ? 2 : COUNT[form]!;
        const category = new Intl.PluralRules(locale).select(count);
        if (category !== form) continue; // `other` у мовах із трьома формами — дробові, яких не буває
        const text = plural(locale, key, count, { read: count, known: count });
        expect(text, `${locale}/${key}.${form}`).toBe(
          expected.replace("{read}", String(count)).replace("{known}", String(count)),
        );
      }
    }
  });

  it("представницькі значення: 1 і 2 в усіх мовах, 5 і 21 в українській і російській", () => {
    for (const locale of SIX) {
      const one = plural(locale, "free.pagesDone", 1, { read: 1 });
      const two = plural(locale, "free.pagesDone", 2, { read: 2 });
      expect(one, locale).not.toContain("{");
      expect(two, locale).not.toContain("{");
      expect(one, locale).not.toBe(two.replace("2", "1"));
    }
    for (const locale of ["uk", "ru"] as Locale[]) {
      const five = plural(locale, "free.pagesRead", 5, { read: 5, known: 5 });
      const twentyOne = plural(locale, "free.pagesRead", 21, { read: 21, known: 21 });
      expect(five, locale).not.toBe(twentyOne.replace(/21/g, "5"));
    }
  });
});
