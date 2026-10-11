"""Рядки самого звіту: заголовки, підписи, легенди.

Окремо від app/audit/i18n/, бо це інша природа тексту: там формулювання
знахідок, тут каркас документа. Спільне в них лише поняття локалі.
"""

from __future__ import annotations

from app.audit.i18n import DEFAULT_LOCALE, Locale

UK: dict[str, str] = {
    "doc_title": "Аудит сайту",
    "generated": "Згенеровано",
    "status": "Статус",
    "pages_crawled": "Просканованих сторінок",
    "overall": "Загальна оцінка",
    "of_100": "зі 100",
    # Вид документа: чотири файли (аудит і присутність, кожен у двох
    # видах) мусять називати себе на обкладинці, інакше в теці
    # завантажень їх не розрізнити (рішення власника 2026-09-06).
    "kind_general": "Загальний звіт",
    "kind_technical": "Технічний звіт",
    "part1_title": "Частина 1. Коротко про головне",
    "part1_subtitle": (
        "Для керівника: що зі станом сайту й що робити першим. Без технічних деталей."
    ),
    "part2_title": "Частина 2. Технічний розбір",
    "part2_subtitle": (
        "Для розробника або SEO-спеціаліста: усі знахідки з доказами та адресами сторінок."
    ),
    "verdict_critical": (
        "Сайт має системні проблеми: пошукові системи й ШІ-сервіси бачать його значно "
        "гірше, ніж він того вартий. Потрібні зміни в кількох напрямах одразу."
    ),
    "verdict_poor": (
        "Основа працює, але прогалин достатньо, щоб втрачати частину відвідувачів. "
        "Більшість із них виправляється швидко й без переробки сайту."
    ),
    "verdict_medium": (
        "Сайт у робочому стані. Лишилися точкові покращення, які додадуть видимості "
        "в пошуку та в ШІ-сервісах."
    ),
    "verdict_good": (
        "Сайт у доброму стані. Знайдене — це радше шліфування, ніж проблеми, "
        "і його можна робити без поспіху."
    ),
    "verdict_unknown": (
        "Цього разу оцінити сайт не вдалося: більшість перевірок лишилася без даних. "
        "Причини — нижче, у розділі про прогалини даних."
    ),
    "area_performance": "Наскільки швидко сторінки відкриваються у відвідувача.",
    "area_seo": "Наскільки добре сайт розуміють пошукові системи.",
    "area_ai_ready": "Чи має сайт машинний опис себе — те, з чого ШІ-сервіси беруть факти.",
    "area_llm_visibility": (
        "Чи може асистент прочитати сайт, зрозуміти, хто ви, і мати що процитувати. "
        "Чи справді цитує — ми не перевіряємо."
    ),
    "area_tech": "Чи захищений сайт від ботів і чи видно, що на ньому роблять відвідувачі.",
    "area_accessibility": (
        "Чи зручний сайт людям зі слабким зором чи моторикою і на будь-якому пристрої."
    ),
    "col_area_meaning": "Що це означає",
    "col_completeness": "Повнота даних",
    "completeness_full": "повні",
    "completeness_partial": "неповні",
    "section_priorities": "Що робити першим",
    "section_scores": "Оцінки по напрямах",
    # Частина 2 має власні заголовки: однакова назва двічі в одному документі
    # збиває з пантелику й ламає навігацію по документу.
    "section_scores_technical": "Оцінки, ваги й повнота даних",
    "section_missing_technical": "Прогалини в даних",
    "section_missing": "Чого ми не виміряли",
    "section_details": "Повний розбір",
    "section_evidence": "Додаток: що ми побачили на сайті",
    "col_module": "Напрям",
    "col_score": "Оцінка",
    "col_band": "Рівень",
    "col_issues": "Знахідок",
    "col_weight": "Вага в загальній",
    "col_parameter": "Параметр",
    "col_value": "Значення",
    "not_measured": "не вимірювалось",
    "missing_note_excluded": "модуль виключено з overall, ваги перерозподілені між рештою",
    "missing_note_partial": (
        "оцінка порахована на неповному наборі сигналів — трактуйте як орієнтир"
    ),
    "missing_note_incomplete": "скор модуля порахований на неповних даних",
    "impact_note": (
        "Ефект кожного пункту порахований окремо — наскільки виросте загальна оцінка, "
        "якщо виправити саме його. Ці числа не можна додавати між собою."
    ),
    "effect": "Ефект",
    "effort": "Складність",
    "pages_affected": "Сторінок",
    "site_wide": "весь сайт",
    "problem": "У чому проблема",
    "what_to_do": "Що зробити",
    "gives": "Що це дасть",
    "no_priorities": "Термінових дій немає — критичних проблем не знайдено.",
    "part1_missing_intro": "Частину сигналів цього разу зібрати не вдалося, тому оцінка неповна:",
    "evidence": "Доказ",
    "examples": "Приклади сторінок",
    "and_more": "…ще {count}",
    "no_issues": "Проблем не знайдено.",
    "module_not_scored": "Напрям не оцінювався — даних не отримано.",
    "severity": "Критичність",
    "impact_floored": "оцінка напряму вже на мінімумі, тому бал не зросте",
    "affects": "Впливає на",
    "reason": "Причина",
    "band_critical": "критично",
    "band_poor": "слабко",
    "band_medium": "середньо",
    "band_good": "добре",
    "band_unknown": "невідомо",
    "effort_low": "низька",
    "effort_medium": "середня",
    "effort_high": "висока",
    "severity_critical": "критична",
    "severity_high": "висока",
    "severity_medium": "середня",
    "severity_low": "низька",
    "severity_info": "інформація",
    "module_accessibility": "Доступність",
    "section_passed": "Перевірки пройдено: {count}",
    "passed_intro": (
        "Явно підтверджені перевірки. Вони не додають балів і не компенсують знахідок — "
        "це довідка про те, що вже зроблено добре."
    ),
    "passed.seo.https": "HTTPS-зʼєднання пройшло без виявлених помилок TLS",
    "passed.seo.robots_txt": "robots.txt знайдено й прочитано",
    "passed.seo.sitemap": "Карту сайту знайдено; оголошених адрес: {declared}",
    "passed.tech.security_headers": (
        "Усі відстежувані захисні заголовки виявлено на перевіреній відповіді"
    ),
    "passed.tech.analytics": "Систему аналітики виявлено: {found}",
    "passed.tech.form_protection": (
        "Видимі ознаки захисту форм від автоматизованого спаму виявлено "
        "({providers}); форм перевірено: {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD виявлено на {pages} із {total} проаналізованих сторінок",
    "passed.ai.llms_txt": "llms.txt наявний (необовʼязкова конвенція)",
    "scores_weight_gap": (
        "Ваги в таблиці дають {shown}. Решту — {hidden} — досі дає доступність: вона більше не "
        "оцінюється балом, але свій давній вклад у загальну оцінку поки зберігає. Знімок "
        "доступності — нижче."
    ),
    "a11y_still_weighted": (
        "Доступність поки що дає {percent} загальної оцінки — вклад лишився таким, яким був до "
        "переходу на знімок. Це тимчасово: ваги напрямів переглядаються окремо."
    ),
    "a11y_not_weighted": (
        "Доступність не входить до загальної оцінки цього аудиту."
    ),
    "section_a11y_snapshot": "Доступність: знімок перевіреної сторінки",
    "a11y_scope": "Перевірено одну сторінку: {url} (мобільний перегляд).",
    "a11y_counts": (
        "Автоматичних перевірок доступності, які застосувалися до цієї сторінки: {applicable}. "
        "Пройдено: {passed}. Не пройдено: {failed}."
    ),
    "a11y_clean": (
        "Автоматичних проблем доступності не знайдено серед {applicable} перевірок, які "
        "застосувалися до цієї сторінки."
    ),
    "a11y_unavailable": (
        "Доступність не виміряна: зовнішній інструмент не віддав даних для цієї сторінки. Це не "
        "означає, що проблем немає."
    ),
    "a11y_caveat": (
        "Це автоматична перевірка однієї сторінки. Вона не є висновком про відповідність WCAG і не "
        "охоплює сайт цілком. Частину перешкод виявити автоматично неможливо."
    ),
    "a11y_also_reported": "Про це сказано також у напрямі «{module}»",
    "a11y_lighthouse_ref": (
        "Бал доступності Lighthouse для перевіреної сторінки (зовнішній орієнтир, не наша оцінка): "
        "{score}"
    ),
    "col_a11y_check": "Перевірка",
    "col_a11y_impact": "Вплив",
    "col_a11y_also": "Де ще сказано",
    "module_performance": "Швидкість / UX",
    "module_seo": "Базове SEO",
    "module_ai_ready": "Готовність до ШІ / LLMO",
    "module_llm_visibility": "Придатність до цитування",
    "module_tech": "Захист і аналітика",
    "ev_pages_ok": "Сторінок успішно",
    "ev_pages_failed": "Сторінок з помилкою",
    "ev_max_depth": "Максимальна глибина",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Сторінок із JSON-LD",
    "ev_schema_types": "Типи schema.org",
    "ev_url_count": "URL у мапі",
    "ev_blocked_agents": "Заблоковані ШІ-краулери",
    "yes": "так",
    "no": "ні",
    "present": "є",
    "absent": "немає",
    "none": "немає",
}

EN: dict[str, str] = {
    "doc_title": "Site audit",
    "generated": "Generated",
    "status": "Status",
    "pages_crawled": "Pages crawled",
    "overall": "Overall score",
    "of_100": "out of 100",
    "kind_general": "General report",
    "kind_technical": "Technical report",
    "part1_title": "Part 1. The short version",
    "part1_subtitle": (
        "For decision makers: where the site stands and what to fix first. No technical detail."
    ),
    "part2_title": "Part 2. Technical breakdown",
    "part2_subtitle": (
        "For a developer or SEO specialist: every finding with evidence and page addresses."
    ),
    "verdict_critical": (
        "The site has systemic problems: search engines and AI services see it far worse "
        "than it deserves. Several areas need work at once."
    ),
    "verdict_poor": (
        "The foundation works, but there are enough gaps to lose part of your visitors. "
        "Most of them are quick to fix and need no rebuild."
    ),
    "verdict_medium": (
        "The site is in working order. What remains are targeted improvements that add "
        "visibility in search and in AI services."
    ),
    "verdict_good": (
        "The site is in good shape. The findings are polish rather than problems, "
        "and can be handled without urgency."
    ),
    "verdict_unknown": (
        "This time we could not score the site: most checks came back without data. "
        "The reasons are listed in the data gaps section below."
    ),
    "area_performance": "How quickly pages open for a visitor.",
    "area_seo": "How well search engines understand the site.",
    "area_ai_ready": (
        "Whether the site describes itself to machines — where AI services take facts from."
    ),
    "area_llm_visibility": (
        "Whether an assistant can read the site, tell who you are and find something "
        "worth quoting. Whether it actually quotes you is not something we test."
    ),
    "area_tech": (
        "Whether the site is protected from bots and whether you can see what visitors do."
    ),
    "area_accessibility": (
        "Whether the site works for people with limited vision or motor control, "
        "on any device."
    ),
    "col_area_meaning": "What this means",
    "col_completeness": "Data completeness",
    "completeness_full": "complete",
    "completeness_partial": "incomplete",
    "section_priorities": "What to fix first",
    "section_scores": "Scores by area",
    "section_scores_technical": "Scores, weights and data completeness",
    "section_missing_technical": "Gaps in the data",
    "section_missing": "What we could not measure",
    "section_details": "Full breakdown",
    "section_evidence": "Appendix: what we saw on the site",
    "col_module": "Area",
    "col_score": "Score",
    "col_band": "Level",
    "col_issues": "Findings",
    "col_weight": "Weight in overall",
    "col_parameter": "Parameter",
    "col_value": "Value",
    "not_measured": "not measured",
    "missing_note_excluded": (
        "the module is excluded from the overall score; its weight is spread across the rest"
    ),
    "missing_note_partial": (
        "the score is built on an incomplete set of signals — read it as an indication"
    ),
    "missing_note_incomplete": "the module score is built on incomplete data",
    "impact_note": (
        "Each item's effect is measured independently — how much the overall score rises "
        "if you fix that one item. These numbers must not be added together."
    ),
    "effect": "Effect",
    "effort": "Effort",
    "pages_affected": "Pages",
    "site_wide": "site-wide",
    "problem": "What is wrong",
    "what_to_do": "What to do",
    "gives": "What you gain",
    "no_priorities": "No urgent actions — no critical problems were found.",
    "part1_missing_intro": (
        "Some signals could not be collected this time, so the score is incomplete:"
    ),
    "evidence": "Evidence",
    "examples": "Example pages",
    "and_more": "…and {count} more",
    "no_issues": "No problems found.",
    "module_not_scored": "This area was not scored — no data was collected.",
    "severity": "Severity",
    "impact_floored": "the area is already at its minimum, so the score will not rise",
    "affects": "Affects",
    "reason": "Reason",
    "band_critical": "critical",
    "band_poor": "poor",
    "band_medium": "medium",
    "band_good": "good",
    "band_unknown": "unknown",
    "effort_low": "low",
    "effort_medium": "medium",
    "effort_high": "high",
    "severity_critical": "critical",
    "severity_high": "high",
    "severity_medium": "medium",
    "severity_low": "low",
    "severity_info": "info",
    "module_accessibility": "Accessibility",
    "section_passed": "Checks passed: {count}",
    "passed_intro": (
        "Explicitly confirmed checks. They add no points and offset no findings — a "
        "record of what is already done well."
    ),
    "passed.seo.https": "HTTPS connection completed without an observed TLS error",
    "passed.seo.robots_txt": "robots.txt found and readable",
    "passed.seo.sitemap": "Sitemap found; declared URLs: {declared}",
    "passed.tech.security_headers": (
        "All monitored security headers detected on the tested response"
    ),
    "passed.tech.analytics": "Analytics detected: {found}",
    "passed.tech.form_protection": (
        "Visible anti-spam protection detected on your forms "
        "({providers}); forms checked: {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD detected on {pages} of {total} analysed pages",
    "passed.ai.llms_txt": "llms.txt present (optional convention)",
    "scores_weight_gap": (
        "The weights in this table add up to {shown}. The remaining {hidden} still comes from "
        "accessibility: it is no longer given a score, but keeps its former contribution to the "
        "overall figure for now. The accessibility snapshot is below."
    ),
    "a11y_still_weighted": (
        "Accessibility still accounts for {percent} of the overall score — the contribution is "
        "unchanged from before the switch to a snapshot. This is temporary: module weights are "
        "being reviewed separately."
    ),
    "a11y_not_weighted": (
        "Accessibility does not enter the overall score for this audit."
    ),
    "section_a11y_snapshot": "Accessibility: snapshot of the tested page",
    "a11y_scope": "One page was tested: {url} (mobile view).",
    "a11y_counts": (
        "Automated accessibility checks that applied to this page: {applicable}. Passed: {passed}. "
        "Failed: {failed}."
    ),
    "a11y_clean": (
        "No automated accessibility issues were found among the {applicable} checks that applied "
        "to this page."
    ),
    "a11y_unavailable": (
        "Accessibility was not measured: the external tool returned no data for this page. That "
        "does not mean there are no problems."
    ),
    "a11y_caveat": (
        "This is an automated check of a single page. It is not a WCAG conformance assessment and "
        "does not cover the whole site. Some barriers cannot be detected automatically."
    ),
    "a11y_also_reported": "Also reported under “{module}”",
    "a11y_lighthouse_ref": (
        "Lighthouse accessibility score for the tested page (external reference, not our score): "
        "{score}"
    ),
    "col_a11y_check": "Check",
    "col_a11y_impact": "Impact",
    "col_a11y_also": "Also reported",
    "module_performance": "Speed / UX",
    "module_seo": "Core SEO",
    "module_ai_ready": "AI-ready / LLMO",
    "module_llm_visibility": "Fitness to be quoted",
    "module_tech": "Protection and analytics",
    "ev_pages_ok": "Pages OK",
    "ev_pages_failed": "Pages failed",
    "ev_max_depth": "Maximum depth",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Pages with JSON-LD",
    "ev_schema_types": "schema.org types",
    "ev_url_count": "URLs in sitemap",
    "ev_blocked_agents": "Blocked AI crawlers",
    "yes": "yes",
    "no": "no",
    "present": "present",
    "absent": "absent",
    "none": "none",
}

# ── звіт для власника ──────────────────────────────────────────────────────
#
# Тут читач не знає слів «індексація», «розмітка» чи «метадані» — і не
# мусить. Мова та сама, якою він розповідає про свій бізнес: клієнти,
# дзвінки, конкуренти, Google. Кожен рядок перевіряється просто: чи
# зрозуміє це людина, яка ніколи не відкривала код сайту.
UK_OWNER: dict[str, str] = {
    "owner_title": "Що зараз відбувається з вашим сайтом",
    "owner_score_caption": "загальна оцінка сайту зі 100",
    "owner_meaning_title": "Простими словами",
    "owner_meaning_critical": (
        "Ваш сайт зараз майже не працює на вас. Люди, які шукають те, що ви продаєте, "
        "переважно вас не знаходять — вони потрапляють до конкурентів. Гарний вигляд сайту "
        "тут ні до чого: справа в речах, яких відвідувач не бачить, а Google бачить. "
        "Хороша новина в тому, що саме такі сайти зростають найшвидше: тут майже кожне "
        "виправлення дає помітний результат."
    ),
    "owner_meaning_poor": (
        "Сайт у вас працює, але значну частину клієнтів ви не отримуєте. Це схоже на "
        "магазин у гарному місці, вивіску якого видно лише з одного боку вулиці: хто "
        "проходить повз, той зайде, а решта навіть не дізнається, що ви існуєте."
    ),
    "owner_meaning_medium": (
        "Основа закладена нормально, і сайт вас годує. Але між вами й конкурентами зараз "
        "різниця в дрібницях, і саме ці дрібниці вирішують, чиє посилання людина побачить "
        "першим. Кілька точкових виправлень тут дають більше, ніж повний перероблений сайт."
    ),
    "owner_meaning_good": (
        "Сайт зроблено добре — краще, ніж у більшості. Вам не потрібні переробки, потрібне "
        "утримання позицій: конкуренти теж працюють, і перевага втрачається непомітно."
    ),
    "owner_meaning_unknown": (
        "Ваш сайт не пустив нашу програму всередину, тому повної картини ми не отримали. "
        "Найчастіше так налаштовують захист від небажаних відвідувачів — але разом із ними "
        "він відрізає й пошукові системи. Це варто перевірити першим."
    ),
    "owner_meaning_empty": (
        "За вашою адресою ми знайшли сторінку майже без тексту. Так виглядає сайт, "
        "у якого закінчився хостинг або домен, або який ще не наповнили. Оцінювати "
        "тут поки нема чого — спершу треба, щоб сайт відкривався."
    ),
    "owner_meaning_failures": (
        "Більшість сторінок вашого сайту не відповіли на запит. Ми прочитали лише "
        "малу частину, і оцінка за нею була б вигадкою. Найчастіше так буває, коли "
        "сервер перевантажений або частина сайту зламана."
    ),
    "owner_areas_title": "Шість речей, за якими вас оцінюють",
    "owner_area_accessibility": "Чи можуть користуватися всі",
    "owner_area_performance": "Чи швидко відкривається сайт",
    "owner_area_seo": "Чи знаходять вас у пошуку",
    "owner_area_ai_ready": "Чи розуміють ваш сайт програми",
    "owner_area_llm_visibility": "Чи є асистенту що про вас сказати",
    "owner_area_tech": "Чи видно вам, звідки клієнти",
    "owner_areas_note": (
        "Прочерк означає, що цей напрям перевірити не вдалося, а не що там усе погано."
    ),
    "owner_problems_title": "Що ми знайшли",
    "owner_problem_gravity": "Наскільки терміново",
    "owner_problem_what": "Що це означає для вас",
    "owner_gravity_critical": "ТЕРМІНОВО",
    "owner_gravity_high": "ВАЖЛИВО",
    "owner_gravity_poor": "ВАРТО ЗРОБИТИ",
    "owner_gravity_medium": "МОЖНА ПІЗНІШЕ",
    "owner_gravity_unknown": "ДО УВАГИ",
    "owner_problems_note": (
        "Це головне з {total} знайдених зауважень. Повний перелік із технічними "
        "подробицями — в окремому документі для вашого розробника."
    ),
    "owner_gain_title": "Наскільки може бути краще",
    "owner_gain_now": "Зараз",
    "owner_gain_after": "Після виправлення знайденого",
    "owner_gain_note": (
        "Різниця у {points} балів. Це не прогноз продажів, а стан сайту: наскільки легко "
        "пошуковим системам і людям знайти вас і зрозуміти, чим ви корисні."
    ),
    "owner_next_title": "Що далі",
    "owner_next_body": (
        "Цю перевірку ми зробили самі, за самою лише адресою сайту, і вона нічого вам не "
        "коштувала. Кожне зауваження вище має конкретну технічну причину й конкретне "
        "рішення — ми знаємо, у чому справа і скільки часу займе виправлення. "
        "Розкажемо на короткій зустрічі: покажемо, з чого почали б, у якому порядку й що "
        "зміниться після кожного кроку. Повторний аудит через місяць покаже результат "
        "тими самими цифрами, що й цей."
    ),
    "owner_ai_view_title": "Як штучний інтелект описує ваш сайт сьогодні",
    "owner_ai_view_note": (
        "Це не наш переказ. Так ваш сайт зрозуміла програма, до якої "
        "звертається ваш покупець, коли шукає, у кого замовити."
    ),
    "owner_enrich_failed": "Розгорнутих пояснень до цих пунктів у документі немає: {reason}",
}
UK.update(UK_OWNER)

EN_OWNER: dict[str, str] = {
    "owner_title": "What is happening with your website right now",
    "owner_score_caption": "overall site score out of 100",
    "owner_meaning_title": "In plain words",
    "owner_meaning_critical": (
        "Your site is barely working for you. People searching for what you sell mostly "
        "do not find you — they land on competitors instead. How the site looks has "
        "nothing to do with it: the problem is in things visitors never see but Google "
        "does. The good news is that sites in this state grow fastest, because almost "
        "every fix shows up in the results."
    ),
    "owner_meaning_poor": (
        "The site works, but you are missing a large share of your customers. It is like "
        "a shop in a good location whose sign is only visible from one side of the "
        "street: whoever walks past will come in, everyone else never learns you exist."
    ),
    "owner_meaning_medium": (
        "The foundation is sound and the site earns its keep. What separates you from "
        "competitors now is small details — and those details decide whose link a person "
        "sees first. A few targeted fixes here beat a full redesign."
    ),
    "owner_meaning_good": (
        "The site is built well — better than most. You do not need a rebuild, you need "
        "to hold the position: competitors are working too, and an edge is lost quietly."
    ),
    "owner_meaning_empty": (
        "At your address we found a page with almost no text on it. That is what a site "
        "looks like when the hosting or the domain has lapsed, or when it was never "
        "filled in. There is nothing to grade yet — first the site has to open."
    ),
    "owner_meaning_failures": (
        "Most pages of your site did not respond. We read only a small part of it, and "
        "a score based on that would be invention. Usually this means the server is "
        "overloaded or part of the site is broken."
    ),
    "owner_meaning_unknown": (
        "Your site did not let our program in, so we could not see the whole picture. "
        "This is usually protection against unwanted visitors — but it cuts off search "
        "engines along with them. Worth checking first."
    ),
    "owner_areas_title": "Six things you are judged on",
    "owner_area_accessibility": "Whether everyone can use it",
    "owner_area_performance": "How fast the site opens",
    "owner_area_seo": "Whether people find you in search",
    "owner_area_ai_ready": "Whether software understands your site",
    "owner_area_llm_visibility": "Whether an assistant has anything to say about you",
    "owner_area_tech": "Whether you can see where customers come from",
    "owner_areas_note": (
        "A dash means we could not check that area — not that everything there is wrong."
    ),
    "owner_problems_title": "What we found",
    "owner_problem_gravity": "How urgent",
    "owner_problem_what": "What it means for you",
    "owner_gravity_critical": "URGENT",
    "owner_gravity_high": "IMPORTANT",
    "owner_gravity_poor": "WORTH DOING",
    "owner_gravity_medium": "CAN WAIT",
    "owner_gravity_unknown": "NOTE",
    "owner_problems_note": (
        "These are the main items out of {total} findings. The full list with technical "
        "detail is in a separate document for your developer."
    ),
    "owner_gain_title": "How much better it could be",
    "owner_gain_now": "Now",
    "owner_gain_after": "After the findings are fixed",
    "owner_gain_note": (
        "A difference of {points} points. This is not a sales forecast — it is the state "
        "of the site: how easily search engines and people can find you and understand "
        "what you are good for."
    ),
    "owner_next_title": "What next",
    "owner_next_body": (
        "We ran this check ourselves, from your web address alone, and it cost you "
        "nothing. Every finding above has a specific technical cause and a specific fix — "
        "we know what is wrong and how long it takes to put right. We will walk you "
        "through it in a short call: where we would start, in what order, and what "
        "changes after each step. A repeat audit in a month shows the result in the same "
        "numbers as this one."
    ),
    "owner_ai_view_title": "How artificial intelligence describes your site today",
    "owner_ai_view_note": (
        "This is not our summary. It is how your site was understood by the "
        "software your customer asks when looking for someone to hire."
    ),
    "owner_enrich_failed": "This document has no expanded explanations for these points: {reason}",
}
EN.update(EN_OWNER)

from app.report.i18n_extra import DE, ES, FR, RU  # noqa: E402 — після каталогів UK/EN

STRINGS: dict[Locale, dict[str, str]] = {
    Locale.UK: UK,
    Locale.EN: EN,
    Locale.DE: DE,
    Locale.ES: ES,
    Locale.FR: FR,
    Locale.RU: RU,
}


def t(key: str, locale: Locale = DEFAULT_LOCALE, **params: object) -> str:
    template = STRINGS.get(locale, UK).get(key) or STRINGS[DEFAULT_LOCALE].get(key, key)
    return template.format(**params) if params else template


__all__ = ["STRINGS", "t"]


def locale_of(report: object) -> Locale:
    """Мова, якою зібраний документ.

    `ReportDocument.locale` — рядок, бо документ серіалізується в JSON.
    Функція повертає його назад типом і не падає на невідомому значенні:
    звіт зі старим чи зіпсованим кодом мови має відрендеритися англійською,
    а не впасти.
    """
    from app.audit.i18n import parse

    return parse(getattr(report, "locale", None)) or DEFAULT_LOCALE
