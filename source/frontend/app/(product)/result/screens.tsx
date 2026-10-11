"use client";

/**
 * Екрани результату без вмісту сайту: оболонка, стан виконання і хід.
 *
 * Живуть окремим модулем, а не в `page.tsx`, бо модуль сторінки App Router
 * може експортувати лише те, що дозволяє Next — `default`, `metadata` і
 * подібне. `Running` мусить бути досяжним ззовні: сторожа сирої помилки не
 * можна написати по тексту файла, тест РЕНДЕРИТЬ цей компонент. Поки він
 * жив у сторінці, цей експорт валив `next build`.
 *
 * Компоненти перенесено без жодної зміни розмітки, тексту, класів і логіки.
 */

import type * as React from "react";
import Link from "next/link";

import { LogoStacked } from "../../components/Brand";
import { Panel, Spinner } from "../../components/primitives";
import {
  auditIsRunning,
  type AuditProgress,
  type StartedAudit,
} from "../../lib/guest-payment";
import { publicHomeHref } from "../../lib/i18n";
import { useLocale } from "../../lib/locale";

/**
 * Оболонка технічного екрана: логотип по центру й панель під ним.
 *
 * Технічними тут звуться екрани без вмісту сайту — запуск, очікування,
 * каса. У них немає ні шапки, ні колонок, тож притиснутий до лівого
 * краю знак виглядає недоробкою. Оболонка одна саме тому, що інакше
 * центрування доводиться памʼятати в кожному стані окремо — і на
 * «Читаємо сайт» його вже забули.
 */
export function TechnicalScreen({ children }: { children: React.ReactNode }) {
  const { locale } = useLocale();
  return (
    // Вміст цих екранів короткий — форма, спінер, повідомлення, — і
    // притиснутий до верху він лишає під собою порожній екран.
    // `justify-center` тримає його посередині; довший вміст просто
    // росте вниз, як і всюди.
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center px-6 py-12">
      <header className="mb-10 flex justify-center">
        <Link href={publicHomeHref(locale)} aria-label="Crawldy">
          <LogoStacked />
        </Link>
      </header>
      {children}
    </main>
  );
}

/** Аудит ще працює — або вже не працює. Чесний стан, а не звіт із нулями.
 *
 * Коли він не працює, причину каже БЕКЕНД: `failure_reason` — готове
 * речення мовою запиту, складене з нормалізованого класу невдачі. Екран
 * його лише показує й ніколи не тлумачить: власного каталогу пʼяти
 * станів тут немає, бо другий переклад розійшовся б із першим.
 *
 * `free.auditFailedLead` лишається запасним. Він потрібен саме тоді, коли
 * поля немає: старий збережений стан, аудит, що впав до появи контракту,
 * або відповідь, у якій клас нам невідомий. Загальне речення в такому разі
 * чесніше за порожнє місце — і воно вже перекладене всіма мовами екрана.
 */
/**
 * Термінальний і робочий стан анонімного екрана.
 *
 * Експортується навмисно: сторожа сирої помилки не можна написати
 * по тексту файла — попередня версія саме так і була написана, і
 * приведення типу пройшло повз неї. Тест РЕНДЕРИТЬ цей компонент і
 * дивиться на те, що вийшло, тож він мусить бути досяжним ззовні.
 */
export function Running({ started }: { started: StartedAudit }) {
  const { t } = useLocale();
  const failed = !auditIsRunning(started.status);
  const reason = started.failure_reason?.trim();
  return (
    <TechnicalScreen>
      <Panel>
        <div className="flex items-center gap-3">
          {failed ? null : <Spinner className="size-5" />}
          <div>
            <h1 className="text-base font-semibold text-foreground">
              {t(failed ? "free.auditFailedTitle" : "free.auditRunningTitle")}
            </h1>
            <p className="mt-0.5 text-sm text-muted">
              {failed
                ? reason || t("free.auditFailedLead")
                : t("free.auditRunningLead")}
            </p>
          </div>
        </div>
        {failed ? null : <Progress progress={started.progress} />}
      </Panel>
    </TechnicalScreen>
  );
}

/**
 * Скільки вже зроблено — справжніми числами або нічим.
 *
 * Смужка, яка повзе до 90% і чекає, тут неможлива за побудовою: частка
 * рахується з того, що бекенд справді прочитав, а поки чисел немає,
 * лишається сам підпис стадії. Вигадане число з анімацією порушило б
 * те саме правило, на якому тримається весь звіт.
 *
 * Знаменник росте, поки краул знаходить нові адреси, тож частка може
 * і зменшитись — це властивість чесного вимірювання, а не збій. Саме
 * тому головне тут число прочитаних сторінок, а смужка при ньому
 * друга.
 */
function Progress({ progress }: { progress?: AuditProgress }) {
  const { t, n } = useLocale();
  const stage = progress?.stage;
  if (!stage) return null;

  const read = progress?.pages_read;
  const known = progress?.pages_known;
  const measured =
    typeof read === "number" && typeof known === "number" && known > 0;
  // Смужка живе рівно доти, доки сторінки ще додаються. Далі та сама
  // повна смужка означала б «лишилось нуль», тоді як попереду ще
  // перевірки й бал: після краулу число сторінок — доведений факт, а не
  // міра ходу, і подавати його мірою було б тим самим вигаданим рухом,
  // від якого ми відмовились на початку.
  const counting = measured && stage === "crawl";
  const share = counting ? Math.min(1, read / known) : 0;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-foreground">{t(`free.stage.${stage}`)}</p>
        {measured ? (
          <p className="text-sm tabular-nums text-muted">
            {/* Форма іменника узгоджується зі знаменником, поки він є, і
                з прочитаним, коли лишився лише факт: «1 з 1 сторінки»,
                «прочитано 1 сторінку». Одне закінчення на всі числа давало
                «1 pages». */}
            {counting
              ? n("free.pagesRead", known, { read, known })
              : n("free.pagesDone", read, { read })}
          </p>
        ) : null}
      </div>
      {counting ? (
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-sunken"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={known}
          aria-valuenow={read}
        >
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-500"
            style={{ width: `${Math.round(share * 100)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
