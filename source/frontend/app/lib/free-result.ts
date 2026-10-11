/**
 * Безкоштовний результат аудиту — контракт `GET /v1/public/audits/{id}`.
 *
 * Тип навмисно не має ані вимірів, ані знахідок, ані порад: межу
 * платного тримає сервер, і фронтенд не може показати те, чого не
 * отримує. Цей файл — дзеркало `app/report/short.py`.
 */

export interface FreeProblem {
  /** Твердження мовою наслідку — перше речення `consequence`. */
  problem: string;
  /** Пояснення, чому це важливо. Порожньо, коли твердження вичерпне. */
  why: string;
  /**
   * Справжня ізольована дельта бала з рушія скорингу — на скільки бал
   * підніметься, якщо виправити САМЕ цю проблему.
   *
   * Сумувати три такі не можна: кожна міряна окремо проти того самого
   * базового бала, і стеля на `issue_key` робить ефект нелінійним.
   * Тому спільного «покращите на N» на екрані немає й не буде.
   */
  impact_points: number;
  /** Приріст округлився до нуля, або загального бала немає взагалі. */
  floored: boolean;
}

export interface FreeCoverage {
  pages_read: number | null;
  pages_known: number | null;
  /**
   * `insufficient` — прочитаного замало для впевненої оцінки, і бал
   * порожній саме тому. Не «сайт поганий», а «ми не змогли виміряти».
   */
  level: "full" | "partial" | "insufficient";
  /**
   * Скільки знайдених адрес не відповіли. Окреме число, а не різниця
   * `known − read`: у знаменнику є й сторінки, до яких краул не дійшов
   * за власним бюджетом, і назвати їх невдачами означало б звинуватити
   * сайт у нашій межі.
   */
  pages_failed: number;
}

export interface FreeAuditResult {
  audit_id: string;
  url: string;
  origin: string;
  status: string;
  generated_at: string;
  /** null — не нуль: бала немає, і малювати нуль означало б збрехати. */
  overall_score: number | null;
  overall_band: string;
  issues_total: number;
  severity: { high: number; medium: number; low: number };
  coverage: FreeCoverage;
  problems: FreeProblem[];
  unlocked: boolean;
}

/**
 * Фікстура для мок-режиму. Числа й тексти — рівня справжньої відповіді:
 * тексти проблем сформульовані як `consequence` з каталогу, без
 * жаргону, адрес і технічних значень.
 */
export const MOCK_FREE_RESULT: FreeAuditResult = {
  audit_id: "9c2e1b40-0000-4000-8000-00000000a001",
  url: "https://example-shop.com/",
  origin: "https://example-shop.com",
  status: "completed",
  generated_at: "2026-08-24T09:12:00Z",
  overall_score: 62,
  overall_band: "medium",
  issues_total: 41,
  severity: { high: 9, medium: 17, low: 15 },
  coverage: { pages_read: 24, pages_known: 31, level: "full", pages_failed: 2 },
  problems: [
    {
      problem:
        "An assistant asked about your products has nothing on these pages it can rely on with confidence.",
      why: "When systems cannot confirm the essentials, they fall back to competitors whose pages they can read.",
      impact_points: 9,
      floored: false,
    },
    {
      problem:
        "In search results people see a random piece of text instead of a reason to click your page.",
      why: "",
      impact_points: 6,
      floored: false,
    },
    {
      problem:
        "The slowest pages lose visitors before any content appears on screen.",
      why: "People rarely wait: most leave within seconds and buy where the page answered first.",
      impact_points: 4,
      floored: false,
    },
  ],
  unlocked: false,
};
