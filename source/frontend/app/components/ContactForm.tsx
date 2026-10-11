"use client";

/**
 * Захищена контактна форма: єдина цільова дія сторінки «Контакти».
 *
 * ## Кнопка відкриває форму, а не поштовий клієнт
 *
 * `mailto:` розкриває адресу поштовим роботам і не працює в людини без
 * налаштованої пошти. Тому кнопка розкриває форму тут-таки, а адреса
 * одержувача живе на сервері й у браузер не потрапляє взагалі.
 *
 * ## Успіх приходить із сервера
 *
 * Стан `sent` виставляється лише після 202 від API — тобто після того,
 * як звернення справді збережене. Намалювати «надіслано» на клієнті
 * було б найдешевшим способом втратити повідомлення людини.
 *
 * ## Форма присутня в розмітці, а кнопка її РОЗКРИВАЄ
 *
 * Не домальовує. Різниця видна рівно нашим власним продуктом: форма,
 * яка зʼявляється в DOM лише після кліку, для краулера й для ШІ не
 * існує — як і оголошений на ній захист. Ми продаємо саме це
 * спостереження, тож на власному сайті поводимося відповідно: розмітка
 * приходить із сервера, `hidden` ховає її від ока й від фокуса, кнопка
 * знімає прапорець.
 *
 * ## Приманка й челендж
 *
 * Поле `company` приховане від людини й порожнє; заповнене — надіслав
 * автомат. Контейнер Turnstile несе `class="cf-turnstile"` і
 * `data-sitekey` одразу — це задокументований спосіб оголосити віджет,
 * і саме він робить захист видимим у розмітці. Сам скрипт провайдера
 * вантажиться лише на відкритті: тримати сторонній запит на кожному
 * перегляді сторінки заради елемента, який ще не показали, — марно.
 * Без ключа не буде ані контейнера, ані скрипта, а перевірка чесно
 * вважається невиконаною (рішення про це ухвалює сервер, не браузер).
 *
 * ## Фокус і клавіатура
 *
 * Форма відкривається кнопкою, фокус їде в перше поле, Escape закриває
 * й повертає фокус на кнопку. Помилки повідомляються `role="alert"`,
 * значення полів переживають невдалу спробу.
 */

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { API_URL } from "../lib/api";
import { cx } from "../lib/cx";

export interface ContactFormStrings {
  open: string;
  name: string;
  email: string;
  site: string;
  siteOptional: string;
  message: string;
  submit: string;
  sending: string;
  close: string;
  success: string;
  failure: string;
  /** Локалізовані причини відмови за стабільним кодом сервера. */
  invalidName: string;
  invalidEmail: string;
  invalidMessage: string;
  invalidSite: string;
  rejected: string;
  tooMany: string;
}

interface Config {
  site_key: string;
  antibot: string;
  delivery_ready: boolean;
}

type Phase = "idle" | "open" | "sending" | "sent" | "error";

/**
 * Код мови сторінки → код мови Turnstile.
 *
 * Мапа явна, а не `locale as string`: перелік мов Cloudflare свій, і
 * збіг із нашими кодами — властивість сьогоднішнього дня, а не
 * контракт. Невідома мова падає в `auto`, тобто в поведінку за
 * замовчуванням, а не в англійську.
 */
/** Ширина звичайного віджета Turnstile. Вужчий контейнер — компактний. */
export const TURNSTILE_NORMAL_WIDTH = 300;

export const TURNSTILE_LANGUAGE: Record<string, string> = {
  en: "en",
  uk: "uk",
  de: "de",
  es: "es",
  fr: "fr",
  ru: "ru",
};

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, options: Record<string, unknown>) => string;
      reset: (id?: string) => void;
    };
  }
}

/** Код сервера → локалізований рядок. Сирий код на екран не потрапляє. */
function messageFor(strings: ContactFormStrings, reason: string): string {
  switch (reason) {
    case "contact.invalid_name":
      return strings.invalidName;
    case "contact.invalid_email":
      return strings.invalidEmail;
    case "contact.invalid_message":
      return strings.invalidMessage;
    case "contact.invalid_site":
      return strings.invalidSite;
    case "contact.antibot_rejected":
      return strings.rejected;
    case "contact.too_many":
      return strings.tooMany;
    default:
      return strings.failure;
  }
}

export function ContactForm({
  locale,
  strings,
}: {
  locale: string;
  strings: ContactFormStrings;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [config, setConfig] = useState<Config | null>(null);
  const [values, setValues] = useState({
    name: "",
    email: "",
    site_url: "",
    message: "",
  });

  // Дорога назад для безскриптового шляху: та сама сторінка, з якої
  // надіслали. Береться зі шляху, а не складається з локалі — слаги в
  // кожної мови свої, і другий спосіб їх обчислити розійшовся б із
  // реєстром сторінок на першій же правці.
  const returnTo = usePathname() || "/";

  const openButton = useRef<HTMLButtonElement>(null);
  const firstField = useRef<HTMLInputElement>(null);
  const widget = useRef<HTMLDivElement>(null);
  const token = useRef<string>("");

  const opened = phase !== "idle";

  // Конфігурація читається на монтуванні, а не на кліку: контейнер
  // челенджу мусить бути в розмітці разом із формою, інакше оголошений
  // захист не видно нікому, хто не натискав кнопку.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(`${API_URL}/v1/contact/config`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error("http");
        const body = (await response.json()) as Config;
        if (!cancelled) setConfig(body);
      } catch {
        // Конфігурація не приїхала — форма лишається робочою: рішення
        // про челендж ухвалює сервер, і без ключа він відповість сам.
        if (!cancelled) setConfig({ site_key: "", antibot: "disabled", delivery_ready: false });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Віджет челенджу — лише коли сервер віддав ключ. Скрипт вантажиться
  // один раз і не блокує форму: без нього поле токена лишається порожнім.
  //
  // Готовність провайдера перевіряється опитуванням, а не наявністю
  // тега скрипта. Тег зʼявляється ДО того, як `window.turnstile` стає
  // доступним, тож при повторному відкритті форми (тег уже є) виклик
  // `render()` мовчки не робив нічого — віджет не зʼявлявся, токена не
  // було, і сервер справедливо відмовляв.
  useEffect(() => {
    if (!opened || !config?.site_key) return;
    let alive = true;

    const render = () => {
      const node = widget.current;
      if (!alive || !window.turnstile || !node || node.dataset.rendered) return;
      node.dataset.rendered = "1";
      window.turnstile.render(node, {
        sitekey: config.site_key,
        // Мова челенджу — мова сторінки. Без цього Cloudflare бере мову
        // браузера, і українська сторінка показувала «Verification
        // failed» та «Troubleshoot» англійською: одна сторінка, дві
        // мови. Значення беремо з пропа локалі, а не з `navigator`.
        language: TURNSTILE_LANGUAGE[locale] ?? "auto",
        // Звичайний віджет має 300px і на 320px-екрані вилазить за межу
        // форми на сорок пікселів — автоматична перевірка ширин спіймала
        // це першим прогоном. Розмір обирається за місцем, яке є: після
        // рендеру віджет не перевбирається, тож міряємо контейнер до.
        size: node.clientWidth < TURNSTILE_NORMAL_WIDTH ? "compact" : "normal",
        callback: (value: string) => {
          token.current = value;
        },
      });
    };

    // Провайдер міг завантажитись раніше — тоді малюємо одразу.
    if (window.turnstile) {
      render();
      return;
    }
    if (!document.getElementById("cf-turnstile-script")) {
      const script = document.createElement("script");
      script.id = "cf-turnstile-script";
      script.src =
        "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      document.head.appendChild(script);
    }
    // Тег є, глобального обʼєкта ще немає: чекаємо саме на нього.
    const timer = window.setInterval(() => {
      if (window.turnstile) {
        window.clearInterval(timer);
        render();
      }
    }, 100);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [opened, config]);

  const close = useCallback(() => {
    setPhase("idle");
    setError("");
    openButton.current?.focus();
  }, []);

  useEffect(() => {
    if (!opened) return;
    firstField.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [opened, close]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPhase("sending");
    setError("");
    try {
      const response = await fetch(`${API_URL}/v1/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...values,
          lang: locale,
          token: token.current,
          // Приманка їде порожньою: її заповнює лише автомат.
          company: (
            document.getElementById("contact-company") as HTMLInputElement | null
          )?.value ?? "",
        }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as {
          detail?: { reason?: string };
        };
        // Значення полів лишаються: людина не має набирати все знову.
        setError(messageFor(strings, body.detail?.reason ?? ""));
        setPhase("error");
        window.turnstile?.reset();
        token.current = "";
        return;
      }
      // Успіх — лише після того, як сервер прийняв звернення.
      setPhase("sent");
      setValues({ name: "", email: "", site_url: "", message: "" });
    } catch {
      setError(strings.failure);
      setPhase("error");
    }
  }

  if (phase === "sent") {
    return (
      // Та сама ширина й те саме місце, що в форми (`max-w-xl`): без неї
      // повідомлення розтягувалось на весь контейнер сторінки, і замість
      // відповіді на дію виходив банер на всю сторінку.
      <div
        role="status"
        className="mt-7 max-w-xl rounded-xl border border-border bg-surface p-5 text-secondary"
      >
        {strings.success}
      </div>
    );
  }

  const field =
    "h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-primary outline-none focus:border-accent";

  return (
    <>
      {!opened ? (
        <button
          ref={openButton}
          type="button"
          onClick={() => setPhase("open")}
          aria-expanded={false}
          aria-controls="contact-form"
          className="mt-7 inline-flex h-12 items-center gap-2 rounded-md bg-brand px-6 text-base font-medium text-brand-ink transition-colors duration-fast hover:bg-brand-hover"
        >
          {strings.open}
          <Icon name="arrow-right" />
        </button>
      ) : null}

      {/* Форма присутня завжди — так її бачать і краулер, і читалка з
          екрана, на відміну від форми, яку домальовує скрипт після
          кліку. Ховається вона КЛАСОМ, а не самим атрибутом `hidden`:
          `display: flex` із класу перебиває стиль браузера для
          `[hidden]`, і форма лишалась на екрані разом із кнопкою. Атрибут
          лишається поруч — він потрібен читалкам і пошуку; ховає екран
          саме клас. */}
      <form
        id="contact-form"
        hidden={!opened}
        // POST і справжня дія — це БЕЗПЕКА РОЗМІТКИ, а не запасний
        // сценарій. Форма без них — це `GET` із порожньою дією, і
        // браузер, у якого скрипт не виконався, поклав би імʼя, пошту й
        // текст звернення в адресний рядок: в історію, у `Referer`
        // наступного переходу й у звичайні журнали проксі. Наш власний
        // детектор побачив на цій сторінці рівно `get` + `empty`.
        //
        // Звичайний шлях лишається на `fetch` нижче: `onSubmit` скасовує
        // подію, тож дія спрацьовує тільки без скриптів.
        method="post"
        action="/api/contact"
        onSubmit={submit}
        noValidate
        className={cx(
          opened ? "flex" : "hidden",
          "mt-7 max-w-xl flex-col gap-4 rounded-xl border border-border bg-surface p-5",
        )}
      >
      {/* Читає їх лише `/api/contact`: у шляху з `fetch` мова приходить
          пропом, а сторінка й так лишається під ногами. */}
      <input type="hidden" name="lang" value={locale} />
      <input type="hidden" name="return" value={returnTo} />

      <label className="flex flex-col gap-1.5">
        <span className="text-sm text-secondary">{strings.name}</span>
        <input
          ref={firstField}
          name="name"
          value={values.name}
          onChange={(e) => setValues({ ...values, name: e.target.value })}
          className={field}
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm text-secondary">{strings.email}</span>
        <input
          type="email"
          name="email"
          autoComplete="email"
          value={values.email}
          onChange={(e) => setValues({ ...values, email: e.target.value })}
          className={field}
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm text-secondary">
          {strings.site} <span className="text-muted">{strings.siteOptional}</span>
        </span>
        <input
          name="site_url"
          inputMode="url"
          value={values.site_url}
          onChange={(e) => setValues({ ...values, site_url: e.target.value })}
          className={field}
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm text-secondary">{strings.message}</span>
        <textarea
          name="message"
          rows={5}
          value={values.message}
          onChange={(e) => setValues({ ...values, message: e.target.value })}
          className="w-full rounded-md border border-border bg-surface p-3 text-base text-primary outline-none focus:border-accent"
        />
      </label>

      {/* Приманка. Схована від людини й від читалки з екрана; автомат
          заповнює все, що схоже на поле. */}
      <div aria-hidden className="hidden">
        <label htmlFor="contact-company">Company</label>
        <input id="contact-company" name="company" tabIndex={-1} autoComplete="off" />
      </div>

      {/* Контейнер челенджу з класом і ключем — задокументоване
          оголошення віджета Turnstile. Він у розмітці одразу: захист,
          який видно лише після кліку, не видно ані краулеру, ані нашому
          власному детектору. Без налаштованого ключа контейнера немає
          зовсім — порожня обіцянка захисту гірша за його відсутність. */}
      {config?.site_key ? (
        <div
          ref={widget}
          className="cf-turnstile"
          data-sitekey={config.site_key}
        />
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

        {/* На вузькому екрані дії стають одна під одною. У рядку
            «Надіслати повідомлення» стискалося сусідом і переносилось на
            два рядки — підпис кнопки не має ламатися, щоб поруч влізла
            другорядна дія. `whitespace-nowrap` тримає його в один рядок,
            `min-h-11` лишає комфортну зону дотику обом. */}
        <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:gap-3">
          <button
            type="submit"
            disabled={phase === "sending"}
            className="inline-flex h-11 w-full items-center justify-center whitespace-nowrap rounded-md bg-brand px-5 text-sm font-medium text-brand-ink transition-colors duration-fast hover:bg-brand-hover disabled:opacity-60 sm:w-auto"
          >
            {phase === "sending" ? strings.sending : strings.submit}
          </button>
          <button
            type="button"
            onClick={close}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-md px-3 text-sm text-secondary hover:text-primary sm:min-h-0 sm:w-auto sm:py-2"
          >
            {strings.close}
          </button>
        </div>
      </form>
    </>
  );
}
