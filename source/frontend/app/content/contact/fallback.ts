/**
 * Сторінка відповіді для форми, надісланої БЕЗ JavaScript.
 *
 * Її бачить лише той, у кого скрипти не виконались: звичайний шлях
 * форми — `fetch`, і він лишається на сторінці. Але сама форма мусить
 * бути безпечною й без нього, тож у неї є справжні `method="post"` і
 * `action`, а в дії — щось, що вміє відповісти людині словами.
 *
 * Чому окремий модуль, а не рядки зі сторінки: рядки сторінки живуть
 * усередині JSX кожної локалі й тягнуть за собою React, а тут серверний
 * маршрут без розмітки. Дублювання при цьому немає — цих трьох речень
 * не існує більше ніде: вони описують стан, який на звичайному шляху
 * недосяжний.
 */

export interface FallbackStrings {
  /** Заголовок сторінки й вкладки. */
  title: string;
  /** Звернення прийнято. */
  sent: string;
  /**
   * Не прийнято, бо перевірку «ви не робот» неможливо виконати без
   * скриптів. Це чесна відмова, а не порада загального вигляду: сервер
   * справді не отримав підтвердження й справді нічого не зберіг.
   */
  blocked: string;
  /** Не прийнято з іншої причини. */
  failed: string;
  /** Підпис посилання назад на сторінку контактів. */
  back: string;
}

export const CONTACT_FALLBACK: Record<string, FallbackStrings> = {
  en: {
    title: "Contact Crawldy",
    sent: "Your message has been received. We will reply to the email address you gave.",
    blocked:
      "The message was not sent: the anti-spam check needs JavaScript, and it did not run. Turn JavaScript on and send the form again — nothing has been saved.",
    failed:
      "The message was not sent. Please try again a little later — nothing has been saved.",
    back: "Back to Contact",
  },
  uk: {
    title: "Контакти Crawldy",
    sent: "Повідомлення отримано. Ми відповімо на вказану електронну адресу.",
    blocked:
      "Повідомлення не надіслано: перевірка «ви не робот» потребує JavaScript, і вона не виконалась. Увімкніть JavaScript і надішліть форму ще раз — нічого не збережено.",
    failed:
      "Повідомлення не надіслано. Спробуйте, будь ласка, трохи пізніше — нічого не збережено.",
    back: "Повернутися до контактів",
  },
  de: {
    title: "Crawldy kontaktieren",
    sent: "Ihre Nachricht ist eingegangen. Wir antworten an die angegebene E-Mail-Adresse.",
    blocked:
      "Die Nachricht wurde nicht gesendet: Die Spam-Prüfung benötigt JavaScript und wurde nicht ausgeführt. Aktivieren Sie JavaScript und senden Sie das Formular erneut — es wurde nichts gespeichert.",
    failed:
      "Die Nachricht wurde nicht gesendet. Bitte versuchen Sie es etwas später erneut — es wurde nichts gespeichert.",
    back: "Zurück zu Kontakt",
  },
  es: {
    title: "Contacto de Crawldy",
    sent: "Hemos recibido tu mensaje. Responderemos a la dirección de correo indicada.",
    blocked:
      "El mensaje no se envió: la comprobación antispam necesita JavaScript y no se ejecutó. Activa JavaScript y envía el formulario de nuevo: no se ha guardado nada.",
    failed:
      "El mensaje no se envió. Inténtalo de nuevo un poco más tarde: no se ha guardado nada.",
    back: "Volver a Contacto",
  },
  fr: {
    title: "Contacter Crawldy",
    sent: "Votre message nous est bien parvenu. Nous répondrons à l’adresse e-mail indiquée.",
    blocked:
      "Le message n’a pas été envoyé : la vérification anti-spam nécessite JavaScript et ne s’est pas exécutée. Activez JavaScript puis renvoyez le formulaire — rien n’a été enregistré.",
    failed:
      "Le message n’a pas été envoyé. Réessayez un peu plus tard — rien n’a été enregistré.",
    back: "Retour à Contact",
  },
  ru: {
    title: "Контакты Crawldy",
    sent: "Сообщение получено. Мы ответим на указанный адрес электронной почты.",
    blocked:
      "Сообщение не отправлено: проверка «вы не робот» требует JavaScript, и она не выполнилась. Включите JavaScript и отправьте форму ещё раз — ничего не сохранено.",
    failed:
      "Сообщение не отправлено. Попробуйте, пожалуйста, немного позже — ничего не сохранено.",
    back: "Вернуться к контактам",
  },
};
