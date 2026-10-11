import type { Config } from "tailwindcss";

/* Tailwind читає токени, а не дублює їх.
 *
 * Дубль розійшовся б із `tokens.css` на першій же зміні палітри, і
 * половина інтерфейсу лишилася б старого кольору. Назви тут — рівно ті
 * самі ролі, що й там: `bg-surface`, `text-secondary`, `text-severity-critical`.
 *
 * Назв на кшталт `brown` чи `turquoise` немає навмисно: у компоненті має
 * стояти роль, інакше зміна теми знову стає пошуком по всьому коду.
 */
export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          sunken: "var(--surface-sunken)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
          control: "var(--border-control)",
        },
        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        muted: "var(--text-muted)",
        inverse: "var(--text-inverse)",
        brand: {
          DEFAULT: "var(--brand)",
          hover: "var(--brand-hover)",
          ink: "var(--brand-ink)",
          soft: "var(--brand-soft)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          ink: "var(--accent-ink)",
          text: "var(--accent-text)",
          soft: "var(--accent-soft)",
        },
        focus: "var(--focus)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",
        severity: {
          critical: "var(--severity-critical)",
          high: "var(--severity-high)",
          medium: "var(--severity-medium)",
          low: "var(--severity-low)",
          info: "var(--severity-info)",
        },
        band: {
          critical: "var(--band-critical)",
          poor: "var(--band-poor)",
          medium: "var(--band-medium)",
          good: "var(--band-good)",
          unknown: "var(--band-unknown)",
        },
        delta: {
          up: "var(--delta-up)",
          down: "var(--delta-down)",
        },
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        "2xs": ["var(--text-2xs)", { lineHeight: "var(--leading-snug)" }],
        xs: ["var(--text-xs)", { lineHeight: "var(--leading-snug)" }],
        sm: ["var(--text-sm)", { lineHeight: "var(--leading-normal)" }],
        base: ["var(--text-base)", { lineHeight: "var(--leading-normal)" }],
        md: ["var(--text-md)", { lineHeight: "var(--leading-normal)" }],
        lg: ["var(--text-lg)", { lineHeight: "var(--leading-snug)" }],
        xl: ["var(--text-xl)", { lineHeight: "var(--leading-tight)" }],
        "2xl": ["var(--text-2xl)", { lineHeight: "var(--leading-tight)" }],
        "3xl": ["var(--text-3xl)", { lineHeight: "var(--leading-tight)" }],
        "4xl": ["var(--text-4xl)", { lineHeight: "var(--leading-tight)" }],
      },
      letterSpacing: {
        tight: "var(--tracking-tight)",
        wide: "var(--tracking-wide)",
      },
      /* Числову шкалу відступів НЕ перевизначаємо.
       *
       * Спроба зробити `1..9` власними токенами вийшла боком: Tailwind
       * бере ту саму шкалу для `h-`, `w-` і `size-`, тож `h-9` став
       * шістьма ремами, і кнопка в шапці виросла до 98 пікселів. Знайдено
       * знімком екрана — структурна перевірка HTML цього не бачить.
       *
       * Дефолтна шкала Tailwind і так кратна 4px, тобто робить рівно те,
       * заради чого токени вводилися. Змінні `--space-*` лишаються в
       * `tokens.css` для власного CSS, де числової шкали немає.
       */
      maxWidth: {
        measure: "var(--measure)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
      },
      transitionTimingFunction: {
        DEFAULT: "var(--ease)",
      },
      transitionDuration: {
        DEFAULT: "var(--duration)",
        fast: "var(--duration-fast)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { backgroundPosition: "100% 0" },
          to: { backgroundPosition: "-100% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in var(--duration) var(--ease)",
        shimmer: "shimmer 1.4s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
