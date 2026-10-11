/**
 * Оболонка публічних сторінок.
 *
 * Той самий бренд, ті самі токени й примітиви, що в кабінеті: перехід
 * «головна → реєстрація → кабінет» має відчуватися продовженням одного
 * продукту, а не переїздом у чужий застосунок.
 *
 * Відмінності від кабінету лише ті, що випливають із задачі. Тут шапка
 * зверху, а не збоку: у публічної сторінки немає робочої області, яку
 * треба берегти, зате є перший екран, який має бути широким. І тут є
 * підвал із перелінковкою — не для краси, а тому що сторінка без
 * вихідних посилань лишається сиротою, і це наш власний чек про неї й
 * скаже.
 *
 * ## Погоджена архітектура футера (2026-09-03)
 *
 * Продукт: Що перевіряємо · Методологія · Ціни. Матеріали: Видимість у
 * ШІ · SEO-аудит · Технічний аудит сайту. Компанія: Про нас · Контакти.
 *
 * У колонці «Матеріали» погоджено ще й пункт FAQ, але загальної
 * довідкової сторінки поки не існує — а посилання, що веде в нікуди,
 * гірше за відсутнє. FAQ зʼявиться тут разом із погодженим вмістом
 * сторінки. Колонки «Розробникам» немає: Crawldy не надає окремого
 * продукту для розробників, і колонка створювала хибне очікування.
 *
 * Серверний компонент навмисно: публічні сторінки мають приходити
 * готовим HTML.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { Logo, Logomark } from "./Brand";
import { PublicHeader } from "./PublicHeader";
import type { Locale } from "../lib/contracts";
import { BRAND } from "../lib/entity";
import type { PageGroup, PageKey } from "../lib/page-types";
import { navOf, pathOf } from "../lib/pages";

/**
 * Меню й підвал будуються з реєстру сторінок: посилання не може вести
 * туди, де сторінки немає, — воно і є сторінкою. Розділ, ще не
 * написаний цією мовою, просто не зʼявляється в меню цієї мови.
 */

const FOOTER_TEXT: Partial<Record<Locale, string>> = {
  en: "Crawldy shows what keeps your site from being visible in search and AI, and what to fix first.",
  de: "Crawldy zeigt, was Ihre Website daran hindert, in Suche und KI sichtbar zu sein — und was zuerst zu beheben ist.",
  es: "Crawldy muestra qué impide que tu sitio sea visible en buscadores y en la IA, y qué corregir primero.",
  fr: "Crawldy montre ce qui empêche votre site d’être visible dans la recherche et l’IA, et quoi corriger en premier.",
  ru: "Crawldy показывает, что мешает вашему сайту быть видимым в поиске и ИИ, и что стоит исправить в первую очередь.",
  uk: "Crawldy показує, що заважає вашому сайту бути видимим у пошуку та ШІ, і що варто виправити насамперед.",
};

const GROUP_TITLE: Record<PageGroup, Partial<Record<Locale, string>>> = {
  product: {
    en: "Product", de: "Produkt", es: "Producto",
    fr: "Produit", ru: "Продукт", uk: "Продукт",
  },
  materials: {
    en: "Resources", de: "Materialien", es: "Materiales",
    fr: "Ressources", ru: "Материалы", uk: "Матеріали",
  },
  company: {
    en: "Company", de: "Unternehmen", es: "Empresa",
    fr: "Entreprise", ru: "Компания", uk: "Компанія",
  },
  // Підписи — з таблиці §3 затвердженого пакета, дослівно.
  legal: {
    en: "Legal", de: "Rechtliches", es: "Información legal",
    fr: "Informations légales", ru: "Правовая информация",
    uk: "Правова інформація",
  },
};

/**
 * Застереження про права поруч із копірайтом.
 *
 * Рядок, а не юридичний блок: юридичні сторінки зʼявляться разом із
 * юридичною особою, і посилатися на ненаписані умови рано. Але сам знак
 * охорони прав від цього не залежить — він стосується вмісту сайту,
 * який уже опублікований.
 */
const RIGHTS: Partial<Record<Locale, string>> = {
  en: "All rights reserved.",
  de: "Alle Rechte vorbehalten.",
  es: "Todos los derechos reservados.",
  fr: "Tous droits réservés.",
  ru: "Все права защищены.",
  uk: "Усі права захищено.",
};

/** Вхід у кабінет. Той самий напис у шапці й у меню на вузькому екрані. */
const SIGN_IN: Partial<Record<Locale, string>> = {
  en: "Sign in", de: "Anmelden", es: "Entrar",
  fr: "Se connecter", ru: "Войти", uk: "Увійти",
};

/**
 * Меню людини, яка вже увійшла.
 *
 * «Особистий кабінет», а не «Кабінет»: у продукті є ще службові екрани
 * команди, і пункт мусить називати саме те місце, яке належить людині.
 * Куди він веде насправді, вирішує роль — правило одне з формою входу.
 */
const CABINET: Partial<Record<Locale, string>> = {
  en: "My account", de: "Mein Konto", es: "Mi cuenta",
  fr: "Mon compte", ru: "Личный кабинет", uk: "Особистий кабінет",
};

const SIGN_OUT: Partial<Record<Locale, string>> = {
  en: "Sign out", de: "Abmelden", es: "Cerrar sesión",
  fr: "Se déconnecter", ru: "Выйти", uk: "Вийти",
};

/**
 * Підписи для читалок з екрана.
 *
 * Їх не видно оком, і саме тому вони найчастіше лишаються англійськими
 * на всіх мовах. Для того, хто користується сайтом на слух, це єдиний
 * спосіб зрозуміти, що це за кнопка, — тож вони перекладаються так само,
 * як видимий текст.
 */
const ARIA: Partial<Record<Locale, { nav: string; language: string; menu: string }>> = {
  en: { nav: "Product", language: "Language", menu: "Menu" },
  de: { nav: "Produkt", language: "Sprache", menu: "Menü" },
  es: { nav: "Producto", language: "Idioma", menu: "Menú" },
  fr: { nav: "Produit", language: "Langue", menu: "Menu" },
  ru: { nav: "Продукт", language: "Язык", menu: "Меню" },
  uk: { nav: "Продукт", language: "Мова", menu: "Меню" },
};

export function PublicShell({
  children,
  locale,
  pageKey,
  locales,
}: {
  children: ReactNode;
  locale: Locale;
  /** Сторінка, на якій ми зараз: перемикач мов веде на неї ж. */
  pageKey: PageKey;
  /**
   * Мови, якими існує **ця** сторінка. Не всі випущені: перемикач, що
   * веде на 404, гірший за відсутній перемикач.
   */
  locales: Locale[];
}) {
  // Підвал — три погоджені колонки; шапка повторює колонку «Продукт»
  // у тому самому порядку: Що перевіряємо → Методологія → Ціни.
  const product = navOf("product", locale);
  const materials = navOf("materials", locale);
  const company = navOf("company", locale);
  const legal = navOf("legal", locale);
  const headerProduct = navOf("product", locale, { header: true });

  return (
    // `lang` і `dir` стоять на `<html>` у кореневому layout, а не тут:
    // корінь публічного сайту живе під динамічним сегментом і бачить
    // мову з адреси. Дублювати атрибут на обгортці нема потреби.
    <div className="flex min-h-screen flex-col">
      <PublicHeader
        product={headerProduct}
        locale={locale}
        locales={locales}
        pageKey={pageKey}
        home={pathOf("home", locale) ?? "/"}
        account={{
          signIn: SIGN_IN[locale] ?? SIGN_IN.en!,
          cabinet: CABINET[locale] ?? CABINET.en!,
          signOut: SIGN_OUT[locale] ?? SIGN_OUT.en!,
        }}
        aria={ARIA[locale] ?? ARIA.en!}
      />

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border bg-surface">
        {/* Колонок стало пʼять — знак із рядком плюс чотири переліки.
            На чотиришпальтовій сітці остання з них падала в другий
            ряд сама, і «Правова інформація» читалась як загублена. */}
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:grid-cols-2 lg:grid-cols-5 lg:px-8">
          <div>
            <Logo />
            <p className="mt-3 max-w-measure text-sm text-secondary">
              {FOOTER_TEXT[locale] ?? FOOTER_TEXT.en}
            </p>
          </div>

          {/* Колонка зʼявляється тоді, коли в ній є хоч одне посилання.
              Порожній заголовок «Продукт» без пунктів під ним — те саме
              посилання в нікуди, тільки без адреси. */}
          <FooterColumn title={GROUP_TITLE.product[locale]} links={product} />
          <FooterColumn title={GROUP_TITLE.materials[locale]} links={materials} />
          <FooterColumn title={GROUP_TITLE.company[locale]} links={company} />
          <FooterColumn title={GROUP_TITLE.legal[locale]} links={legal} />
        </div>

        <div className="border-t border-border">
          {/* Знак і копірайт — одна пара, і рухаються вони разом.
              `justify-end` замість `ms-auto` на самому написі: інакше
              значок лишається біля лівого краю, і рядок читається як
              два різні елементи замість одного підпису. */}
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-end gap-x-4 gap-y-2 px-5 py-4 text-xs text-muted lg:px-8">
            <Logomark height={16} />
            {/* Юридичні сторінки зʼявляться тут разом із юридичною
                особою: посилання на ненаписані умови — обіцянка,
                якої немає. Бренду в копірайті поки достатньо.

                Відкритої адреси пошти тут немає навмисно: її збирають
                поштові роботи, а публічний канал звʼязку — захищена
                форма на сторінці «Контакти». */}
            <span>
              © {new Date().getFullYear()} {BRAND}. {RIGHTS[locale] ?? RIGHTS.en}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title?: string;
  links: { href: string; label: string }[];
}) {
  if (links.length === 0 || !title) return null;
  return (
    <div>
      {/* Заголовок колонки відрізняється від посилань під ним вагою й
          кольором, а не лише регістром: у `text-muted` тим самим кеглем
          він читався як ще один пункт, тільки блідіший. Темний
          основний текст (15:1) і напівжирний — це підпис групи;
          посилання лишаються звичайними й вторинного кольору. Без
          підкреслення: заголовок нікуди не веде. */}
      <h2 className="text-xs font-semibold uppercase tracking-wide text-primary">
        {title}
      </h2>
      <ul className="mt-4 flex flex-col gap-2 text-sm">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-secondary hover:text-primary">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
