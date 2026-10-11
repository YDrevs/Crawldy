"use client";

/**
 * Хто ти, коли ти вже увійшов — у шапці публічного сайту.
 *
 * Сесія кабінету жила невидимо: сайт показував «Увійти» тому, хто вже
 * увійшов, і кнопки, що ведуть у касу, поводились інакше, ніж людина
 * очікувала, — без жодної підказки чому. Власник спіймав це на собі:
 * «був виконаний вхід в кабінет, про який я не знав і не бачив на
 * екрані». Стан, який змінює поведінку продукту, мусить бути видимим.
 *
 * ## Читання, яке нічого не вирішує
 *
 * `GET /v1/auth/me` тут — лише підпис у шапці. Прав він не дає й дати
 * не може: кожен маршрут кабінету перевіряє сесію сам, і 401 приходить
 * незалежно від того, що намалював фронтенд. Тому будь-яка відмова —
 * мережа, вимкнений API, протухла сесія — це просто «Увійти», без
 * повідомлень про помилку: публічна сторінка не має ставати гіршою
 * від того, що кабінет недоступний.
 *
 * ## Куди веде «Особистий кабінет»
 *
 * У `landingFor` — те саме правило, що й після входу: команда Crawldy
 * потрапляє в службові екрани, решта в кабінет. Другого місця з цим
 * рішенням бути не має, інакше меню й форма входу розійдуться.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { getMe, logout } from "../lib/api";
import { landingFor } from "../lib/landing";
import type { Locale } from "../lib/contracts";

export interface AccountLabels {
  /** Напис, поки ми не знаємо людину. */
  signIn: string;
  cabinet: string;
  signOut: string;
}

/** Підпис людини: імʼя, а якщо його немає — пошта до «@». */
function nameOf(user: { display_name: string; email: string }): string {
  const named = user.display_name.trim();
  if (named) return named;
  return user.email.split("@")[0] ?? user.email;
}

export function PublicAccount({
  locale,
  labels,
  onNavigate,
  variant = "bar",
}: {
  locale: Locale;
  labels: AccountLabels;
  /** Закрити меню вузького екрана, коли з нього кудись пішли. */
  onNavigate?: () => void;
  /** `bar` — шапка широкого екрана, `menu` — список на вузькому. */
  variant?: "bar" | "menu";
}) {
  const [who, setWho] = useState<{ name: string; landing: string } | null>(null);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    void getMe()
      .then((me) => {
        if (!alive || !me.user) return;
        setWho({
          name: nameOf(me.user),
          landing: landingFor(me.user.platform_role, null),
        });
      })
      // Не увійшов, сесія протухла, API мовчить — усі три виглядають
      // однаково: у шапці «Увійти».
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  // Клік повз меню закриває його. Без цього воно лишається розкритим і
  // перекриває сторінку, на яку людина щойно натиснула.
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const leave = async () => {
    // Виходимо й лишаємось на цій самій сторінці: людина натиснула
    // «Вийти», а не «піти з сайту». Перезавантаження перемальовує
    // шапку тим, чим вона й має бути, — посиланням «Увійти».
    await logout().catch(() => undefined);
    window.location.reload();
  };

  const signInLink = (
    <Link
      href={`/login?lang=${locale}`}
      onClick={onNavigate}
      className={
        variant === "menu"
          ? "block rounded-md px-2 py-2.5 text-base text-secondary hover:bg-surface-sunken hover:text-primary"
          : "hidden whitespace-nowrap rounded-md px-3 py-2 text-sm text-secondary transition-colors duration-fast hover:text-primary sm:inline-flex"
      }
    >
      {labels.signIn}
    </Link>
  );

  if (!who) return signInLink;

  if (variant === "menu") {
    return (
      <>
        <p className="px-2 pb-1 pt-2 text-xs uppercase tracking-wide text-muted">
          {who.name}
        </p>
        <Link
          href={who.landing}
          onClick={onNavigate}
          className="block rounded-md px-2 py-2.5 text-base text-secondary hover:bg-surface-sunken hover:text-primary"
        >
          {labels.cabinet}
        </Link>
        <button
          type="button"
          onClick={() => void leave()}
          className="block w-full rounded-md px-2 py-2.5 text-start text-base text-secondary hover:bg-surface-sunken hover:text-primary"
        >
          {labels.signOut}
        </button>
      </>
    );
  }

  return (
    <div ref={box} className="relative hidden sm:block">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="inline-flex max-w-40 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-2 text-sm text-secondary transition-colors duration-fast hover:text-primary"
      >
        <span className="truncate">{who.name}</span>
        <Icon name="chevron-down" className="size-4 shrink-0" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute end-0 z-30 mt-1 min-w-48 rounded-lg border border-border bg-surface py-1 shadow-lg"
        >
          <Link
            href={who.landing}
            role="menuitem"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-sm text-secondary hover:bg-surface-sunken hover:text-primary"
          >
            {labels.cabinet}
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={() => void leave()}
            className="block w-full px-3 py-2 text-start text-sm text-secondary hover:bg-surface-sunken hover:text-primary"
          >
            {labels.signOut}
          </button>
        </div>
      ) : null}
    </div>
  );
}
