/**
 * Базові заголовки безпеки на справжній відповіді.
 *
 * ## Що перевіряється
 *
 * Дві половини, і жодна не замінює другу. Перша читає конфігурацію як
 * КОД — викликає `headers()` і дивиться, що вона повернула. Друга піднімає
 * `next start` на продакшн-збірці й читає справжні відповіді: між
 * конфігурацією й заголовком у відповіді стоїть увесь Next, і твердження
 * про текст файлу про поведінку сервера не свідчить.
 *
 * ## Чого тут немає і чому
 *
 * Немає жодного твердження про `Content-Security-Policy` і
 * `Strict-Transport-Security` — ані що вони є, ані що їх немає. Обидва —
 * законні майбутні задачі: CSP потребує проходу по сторінках (інлайнові
 * стилі, Paddle, Turnstile), HSTS — реального HTTPS і домену. Заборонити
 * їх тестом означало б перетворити межу ЦІЄЇ задачі на властивість
 * продукту й зламати ту роботу, коли вона прийде.
 *
 * З тієї ж причини немає твердження про те, які заголовки стоять на самій
 * 308-відповіді перенаправлення. Зараз їх там немає (`redirects()` відповідає
 * раніше, ніж застосовуються `headers()`) — це виміряно й записано в доказах
 * задачі як стан реалізації, а не як правило. Middleware, edge-хостинг, CSP
 * чи HSTS мають лишатися вільними додати їх туди. Закріплено натомість те,
 * що справді є інваріантом: перенаправлення зберігає свій код і `Location`.
 *
 * ## Чому дублікати рахуються поштучно
 *
 * `res.headers` склеює повтори комою, і `"DENY, DENY"` виглядав би як
 * рядок, що містить `DENY`. Тому лічильник іде по `rawHeaders`, де кожне
 * входження лишається окремим. Це стереже повтор, доданий чимось поза
 * конфігурацією, — middleware, проксі, хостингом.
 *
 * Із самої конфігурації повтор у відповідь НЕ потрапляє: виміряно трьома
 * формами (той самий ключ двічі з тим самим значенням; двічі з різними
 * значеннями; два окремі правила на всі маршрути) — Next щоразу віддає
 * рівно одне входження, і виграє ОСТАННЄ оголошення. Тому небезпека
 * дубльованого оголошення не в повторі, а в тихій підміні: друге правило
 * мовчки замінило б `DENY` на щось слабше. Саме від цього стоїть перевірка
 * точного переліку в `headers()` — вона ловить оголошення, а мережева
 * половина ловить наслідок.
 *
 * ## Мережева половина потребує збірки
 *
 * `next start` без `.next` не запускається, тому ці тести оголошені
 * пропущеними, коли продакшн-збірки немає, — і причина пропуску написана
 * в назві, а не мовчазна. У матриці перевірок збірка робиться до прогону,
 * тож там вони виконуються.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { get } from "node:http";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = join(HERE, "..");
const BUILT = existsSync(join(FRONTEND, ".next", "BUILD_ID"));
const PORT = 3477;

/** Значення, затверджені для цієї задачі. Порядок — той, що в конфігурації. */
const EXPECTED: ReadonlyArray<readonly [string, string]> = [
  ["x-content-type-options", "nosniff"],
  ["referrer-policy", "strict-origin-when-cross-origin"],
  ["x-frame-options", "DENY"],
  ["permissions-policy", "camera=(), geolocation=(), microphone=()"],
];

interface Reply {
  status: number;
  /** Кожне входження окремо: склеєний рядок приховав би дублікат. */
  raw: [string, string][];
  body: string;
}

function head(reply: Reply, name: string): string[] {
  return reply.raw
    .filter(([k]) => k.toLowerCase() === name.toLowerCase())
    .map(([, v]) => v);
}

function fetchRaw(path: string, host?: string): Promise<Reply> {
  return new Promise((resolve, reject) => {
    const req = get(
      {
        host: "127.0.0.1",
        port: PORT,
        path,
        headers: host ? { Host: host } : {},
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c: Buffer) => chunks.push(c));
        res.on("end", () => {
          const raw: [string, string][] = [];
          for (let i = 0; i < res.rawHeaders.length; i += 2) {
            raw.push([res.rawHeaders[i], res.rawHeaders[i + 1]]);
          }
          resolve({
            status: res.statusCode ?? 0,
            raw,
            body: Buffer.concat(chunks).toString("utf8"),
          });
        });
      },
    );
    req.on("error", reject);
    req.setTimeout(30_000, () => req.destroy(new Error("timeout")));
  });
}

let server: ChildProcess | undefined;

async function serve(): Promise<void> {
  if (server) return;
  server = spawn(
    process.execPath,
    [join(FRONTEND, "node_modules", "next", "dist", "bin", "next"), "start",
      "-H", "127.0.0.1", "-p", String(PORT)],
    { cwd: FRONTEND, stdio: "ignore", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" } },
  );
  for (let i = 0; i < 120; i += 1) {
    try {
      await fetchRaw("/robots.txt");
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  throw new Error("next start never answered");
}

afterAll(() => {
  server?.kill();
});

describe("конфігурація оголошує рівно затверджений набір", () => {
  it("headers() віддає чотири заголовки в сталому порядку на всі маршрути", async () => {
    const config = (await import("../next.config.mjs")).default as {
      headers: () => Promise<{ source: string; headers: { key: string; value: string }[] }[]>;
    };
    const rules = await config.headers();
    expect(rules).toHaveLength(1);
    expect(rules[0].source).toBe("/:path*");
    expect(rules[0].headers.map((h) => [h.key.toLowerCase(), h.value])).toEqual(
      EXPECTED.map(([k, v]) => [k, v]),
    );
  });

  it("розкриття фреймворку вимкнено", async () => {
    const config = (await import("../next.config.mjs")).default as {
      poweredByHeader?: boolean;
    };
    expect(config.poweredByHeader).toBe(false);
  });

  it("перенаправлення дзеркальних доменів не зачеплені", async () => {
    const config = (await import("../next.config.mjs")).default as {
      redirects: () => Promise<{ destination: string; permanent: boolean }[]>;
    };
    const rules = await config.redirects();
    expect(rules).toHaveLength(3);
    for (const rule of rules) {
      expect(rule.permanent).toBe(true);
      expect(rule.destination).toBe("https://crawldy.ai/:path*");
    }
  });
});

describe.skipIf(!BUILT)("справжня відповідь next start", () => {
  // Підняття сервера — окремий бюджет, а не частина першої перевірки.
  //
  // `serve()` чекає на відповідь до шістдесяти секунд (120 × 500 мс),
  // але викликався він УСЕРЕДИНІ `it`, а там діє типовий ліміт vitest у
  // пʼять секунд. Тобто закладений бюджет був недосяжний: перша
  // перевірка вмирала за пʼять секунд, поки `next start` ще
  // піднімався, а решта двадцять дві проходили — сервер на той час уже
  // відповідав. Виглядало це як «один тест нестабільний», а насправді
  // ліміт міряв не те: запуск чужого процесу не є частиною перевірки
  // заголовка.
  //
  // Гейт `skipIf` не зачеплений, жодне твердження не змінене: перенесено
  // лише очікування на готовність.
  beforeAll(async () => {
    await serve();
  }, 90_000);

  const ROUTES = ["/", "/pricing", "/uk/tsiny", "/methodology", "/login", "/checkout",
    "/robots.txt", "/sitemap.xml", "/this-route-does-not-exist-header-probe"];

  for (const route of ROUTES) {
    it(`${route}: чотири заголовки присутні, кожен рівно один раз`, async () => {
      await serve();
      const reply = await fetchRaw(route);
      for (const [name, value] of EXPECTED) {
        const seen = head(reply, name);
        expect(seen, `${route} ${name}`).toEqual([value]);
      }
    });

    it(`${route}: версія фреймворку не розкривається`, async () => {
      await serve();
      const reply = await fetchRaw(route);
      expect(head(reply, "x-powered-by")).toEqual([]);
    });
  }

  it("Permissions-Policy забороняє рівно три можливості, без зірочки й без джерел", async () => {
    await serve();
    const reply = await fetchRaw("/");
    const [value] = head(reply, "permissions-policy");
    expect(value).toBe("camera=(), geolocation=(), microphone=()");
    expect(value).not.toContain("*");
    expect(value).not.toContain("self");
    expect(value).not.toMatch(/https?:/);
    expect(value.split(",").map((part) => part.trim().split("=")[0]).sort()).toEqual([
      "camera",
      "geolocation",
      "microphone",
    ]);
  });

  it("перенаправлення дзеркальних доменів зберегли код і ціль", async () => {
    // Інваріант тут один: перенаправлення не зрушило. Скільки заголовків
    // стоїть на самій 308-відповіді — НЕ інваріант: middleware, edge-хостинг,
    // майбутні CSP чи HSTS мають право їх туди додати, і тест, який вимагав
    // би їхньої відсутності, зламав би ту роботу. Поточний стан виміряний і
    // записаний в доказах задачі, а не закріплений тут.
    await serve();
    for (const host of ["crawldy.com", "www.crawldy.com", "www.crawldy.ai"]) {
      for (const [path, target] of [
        ["/", "https://crawldy.ai"],
        ["/pricing", "https://crawldy.ai/pricing"],
        ["/uk/tsiny", "https://crawldy.ai/uk/tsiny"],
      ] as const) {
        const reply = await fetchRaw(path, host);
        expect(reply.status, `${host}${path}`).toBe(308);
        expect(head(reply, "location"), `${host}${path}`).toEqual([target]);
      }
    }
  });

  it("звичайний хост не перенаправляється", async () => {
    await serve();
    const reply = await fetchRaw("/pricing");
    expect(reply.status).toBe(200);
    expect(head(reply, "location")).toEqual([]);
  });

  it("неіснуюча адреса й далі віддає 404", async () => {
    await serve();
    const reply = await fetchRaw("/this-route-does-not-exist-header-probe");
    expect(reply.status).toBe(404);
  });

  it("типи вмісту й тіла службових маршрутів лишились собою", async () => {
    // Це інваріанти продукту, а не межа задачі: robots.txt мусить бути
    // text/plain із рядком user-agent, карта сайту — XML із `<loc>`,
    // сторінка — text/html. Вони мали б триматись і без цієї задачі.
    await serve();
    const robots = await fetchRaw("/robots.txt");
    expect(robots.status).toBe(200);
    expect(head(robots, "content-type")[0]).toContain("text/plain");
    expect(robots.body).toMatch(/User-Agent/i);

    const sitemap = await fetchRaw("/sitemap.xml");
    expect(sitemap.status).toBe(200);
    expect(head(sitemap, "content-type")[0]).toContain("xml");
    expect(sitemap.body).toContain("<loc>");

    const page = await fetchRaw("/pricing");
    expect(head(page, "content-type")[0]).toContain("text/html");
  });

});
