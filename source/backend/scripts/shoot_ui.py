"""Знімки інтерфейсу: десктоп і мобільний.

    python scripts/shoot_ui.py http://localhost:3000 ../design-review

Існує тому, що структурна перевірка HTML не бачить того, що видно оком.
Кнопка в шапці була 98 пікселів заввишки замість 36 — `tsc`, `next build`
і читання дерева доступності про це мовчали, бо з їхнього боку все було
правильно: клас стояв, елемент існував, роль була та сама.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

# Консоль Windows у cp1251 ламає українські шляхи в повідомленнях.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1]
OUT = sys.argv[2]

PAGES = [
    ("home", "/"),
    ("login", "/login"),
    ("dashboard", "/app"),
    # Ідентифікатор — той самий, що в макеті результату: екран звіту
    # найважчий у продукті й найбільше виграє від перегляду оком.
    ("result", "/app/audits/9c2e1b40-0000-4000-8000-00000000a001"),
    ("result-blocked", "/app/audits/9c2e1b40-0000-4000-8000-00000000a004"),
]
VIEWPORTS = [("desktop", 1440, 900), ("mobile", 390, 844)]


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for label, w, h in VIEWPORTS:
            ctx = await browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=2,
                is_mobile=(label == "mobile"),
            )
            page = await ctx.new_page()
            for name, path in PAGES:
                # Не networkidle: у dev-режимі Next тримає websocket HMR,
                # і мережа не стихає ніколи.
                await page.goto(BASE + path, wait_until="domcontentloaded")
                await page.wait_for_selector("h1", timeout=20000)
                await page.wait_for_timeout(700)
                target = f"{OUT}/{name}-{label}.png"
                await page.screenshot(path=target, full_page=(label == "desktop"))
                print("saved", target)
            await ctx.close()
        await browser.close()

asyncio.run(main())
