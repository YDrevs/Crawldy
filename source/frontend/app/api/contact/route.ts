/**
 * Ціль форми «Контакти», коли JavaScript не спрацював.
 *
 * ## Навіщо він узагалі
 *
 * Форма без `method` — це `GET` із порожньою дією, і браузер, у якого
 * скрипт не виконався, поклав би імʼя, пошту й текст звернення в адресний
 * рядок: в історію браузера, у `Referer` наступного переходу і в
 * звичайні журнали проксі. Наш власний детектор побачив на сайті Crawldy
 * саме `method: "get"`, `action_scope: "empty"` — тобто ми продавали
 * спостереження, якого не виконували самі.
 *
 * Тому у форми є справжні `method="post"` і `action`, а безпека розмітки
 * не залежить від скрипта. Дія — тут: свій origin, свій сервер, ніяких
 * даних в адресі.
 *
 * ## Що він робить і чого не робить
 *
 * Пересилає поля на бекенд тим самим контрактом, що й `fetch`, і показує
 * людині результат словами. Він **не** обходить жодної перевірки:
 * приманка, челендж, валідація, ліміт частоти й доставка лишаються на
 * сервері, і відповідь тут завжди відповідає його рішенню.
 *
 * Без скриптів челенджу немає, тож у проді бекенд відмовить — і сторінка
 * скаже про це прямо, замість намалювати «надіслано». Це не недоробка
 * запасного шляху, а його єдина чесна поведінка: перевірка справді не
 * виконалась, і звернення справді не збережене.
 *
 * ## Адреса клієнта
 *
 * Лічильник частоти на бекенді ключується адресою. Через проксі до нього
 * доходить адреса цього сервера, тож справжня їде в `X-Forwarded-For` —
 * рівно там, де бекенд її й шукає. Коли він налаштований заголовку не
 * вірити, всі безскриптові звернення потраплять в одне відро: суворіше
 * за потрібне, але не слабше — і це правильний бік помилки.
 */

import { API_URL } from "../../lib/api";
import { CONTACT_FALLBACK, type FallbackStrings } from "../../content/contact/fallback";

/** Сторінка живе на сервері: відповідь залежить від тіла запиту. */
export const dynamic = "force-dynamic";

/** Куди повертатися. Лише свій шлях — і ніколи чужий сайт. */
function safeReturn(raw: string): string {
  // `//evil.example` — теж «починається зі слеша», і саме так роблять
  // відкриті редіректи. Другий символ перевіряється окремо.
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function page(
  strings: FallbackStrings,
  locale: string,
  body: string,
  back: string,
  status: number,
): Response {
  const html = `<!doctype html>
<html lang="${escapeHtml(locale)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${escapeHtml(strings.title)}</title>
<style>
  body { margin: 0; padding: 3rem 1.5rem; font: 16px/1.6 system-ui, sans-serif;
         color: #2b2622; background: #faf8f5; }
  main { max-width: 34rem; margin: 0 auto; }
  p { margin: 0 0 1.5rem; }
  a { color: #0d7c8a; }
</style>
</head>
<body>
<main>
<p>${escapeHtml(body)}</p>
<p><a href="${escapeHtml(back)}">${escapeHtml(strings.back)}</a></p>
</main>
</body>
</html>`;
  return new Response(html, {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

export async function POST(request: Request): Promise<Response> {
  const form = await request.formData();
  const read = (key: string) => String(form.get(key) ?? "");

  const locale = read("lang") || "en";
  const strings = CONTACT_FALLBACK[locale] ?? CONTACT_FALLBACK.en;
  const back = safeReturn(read("return"));

  // Адреса клієнта — для лічильника частоти на бекенді. Заголовок
  // проксі, якщо він уже є; інакше адреса зʼєднання.
  const forwarded =
    request.headers.get("x-forwarded-for") ??
    request.headers.get("x-real-ip") ??
    "";

  let accepted = false;
  let blocked = false;
  try {
    const response = await fetch(`${API_URL}/v1/contact`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(forwarded ? { "x-forwarded-for": forwarded } : {}),
      },
      body: JSON.stringify({
        name: read("name"),
        email: read("email"),
        site_url: read("site_url"),
        message: read("message"),
        company: read("company"),
        lang: locale,
        // Токена немає за побудовою: віджет челенджу малює скрипт, а
        // цей шлях існує саме тому, що скрипта не було.
        token: "",
      }),
    });
    accepted = response.ok;
    if (!accepted) {
      const body = (await response.json().catch(() => ({}))) as {
        detail?: { reason?: string };
      };
      const reason = body.detail?.reason ?? "";
      blocked =
        reason === "contact.antibot_rejected" ||
        reason === "contact.antibot_unavailable";
    }
  } catch {
    accepted = false;
  }

  if (accepted) return page(strings, locale, strings.sent, back, 200);
  // 422 для відмови челенджу читається невірно: запит правильний, це
  // перевірка не виконалась. 403 називає стан як він є.
  if (blocked) return page(strings, locale, strings.blocked, back, 403);
  return page(strings, locale, strings.failed, back, 502);
}
