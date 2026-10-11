"use client";

/**
 * Кабінет: усе за входом.
 *
 * Оболонка не показує нічого, поки не знає, хто перед нею. Це не
 * обережність заради обережності: інтерфейс, що встиг намалювати
 * порожній кабінет до відповіді `/v1/auth/me`, показує людині її дані
 * після блимання чужим виглядом.
 *
 * Приховування від індексації — теж тут: приватні дані аудитів не мають
 * потрапляти в пошук ані сторінкою, ані шматком.
 *
 * Макетного режиму більше немає: кабінет говорить із живим бекендом, а
 * порожній акаунт показує чесні порожні стани, а не вигадані сайти.
 */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { Spinner } from "../../components/primitives";
import { logout } from "../../lib/api";
import type { Locale } from "../../lib/contracts";
import { LocaleProvider } from "../../lib/locale";
import { asSiteLocale, withNotice } from "../../lib/i18n";
import { rememberSiteLocale, useSiteLocale } from "../../lib/site-locale";
import { SessionProvider, useSession } from "../../lib/session";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <Guard>{children}</Guard>
    </SessionProvider>
  );
}

function Guard({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();

  const { me, loading, refresh, clear } = session;
  // Мова сайту потрібна ще до `me`: сторож відправляє на форму входу й
  // тоді, коли профілю немає взагалі.
  const site = useSiteLocale(me?.user?.locale);

  // Що сказати на формі входу про те, чому людина там опинилась.
  // Стан, а не аргумент переходу, і на це є причина нижче.
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    // Мова їде з людиною: зашите «/login» показувало німцеві англійську
    // форму й вело на англійську головну, хоча він прийшов з /de.
    //
    // Новина про зміну пароля їде ТУТ САМО, а не з обробника кнопки.
    // Власний `router.replace` звідти не виживав: `clear()` обнуляє
    // `me`, цей сторож спрацьовує наступним і перекриває адресу своєю —
    // рівно та сама халепа, що колись з'їдала мову при повністю
    // правильному коді виходу. Перехід тут один, тож перекривати нема
    // чому.
    if (!loading && me === null) {
      const back = `/login?lang=${site}`;
      router.replace(notice ? withNotice(back, notice) : back);
    }
  }, [loading, me, notice, router, site]);

  // Профіль — свідомий вибір людини, і памʼять браузера мусить його
  // знати. Писав її ДОСІ лише публічний header, тож той, хто перемкнув
  // мову всередині кабінету, памʼяті не лишав. На виході `clear()`
  // обнуляє `me`, сторож вище перезапускається вже з порожнім профілем,
  // падає на порожню памʼять — і німець виходив на АНГЛІЙСЬКУ форму
  // входу при повністю правильному коді самого виходу.
  useEffect(() => {
    const chosen = asSiteLocale(me?.user?.locale ?? null);
    if (chosen) rememberSiteLocale(chosen);
  }, [me?.user?.locale]);

  if (loading || me === null) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const locale = (me.user?.locale || "en") as Locale;

  async function changeLocale(next: Locale) {
    // Мова зберігається в профілі, а не в стані вкладки: людина, яка
    // обрала українську на ноутбуці, не має обирати її знову на телефоні.
    await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/v1/auth/me`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale: next }),
    });
    await refresh();
  }

  return (
    <LocaleProvider locale={locale}>
      <AppShell
        email={me.user?.email}
        profileLocale={me.user?.locale}
        onSignOut={() => {
          void logout().then(() => {
            clear();
            // Вихід не перемикає мови. Мова САЙТУ, а не кабінету: форма
            // входу існує шістьма, і людина з /de має побачити німецьку.
            router.replace(`/login?lang=${site}`);
          });
        }}
        onLocaleChange={(next) => void changeLocale(next)}
        onPasswordChanged={() => {
          // Зміна пароля відкликає ВСІ сесії, включно з цією: лишатися
          // в кабінеті нема на чому. Переходу тут немає навмисно — його
          // зробить сторож вище, коли побачить порожній профіль. Наше
          // діло назвати причину, щоб форма входу сказала про успіх:
          // після відкликання сесії сказати про нього більше нема кому.
          setNotice("changed");
          clear();
        }}
      >
        {children}
      </AppShell>
    </LocaleProvider>
  );
}
