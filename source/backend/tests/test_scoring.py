from app.audit.enums import Module, Severity
from app.audit.scoring import (
    MAX_PENALTY_PER_KEY,
    MAX_PENALTY_SHARE_OF_HALF,
    MODULE_HALF_SCALE,
    compute_scores,
    module_penalty,
    module_score,
)
from app.audit.types import Issue


def issue(module=Module.SEO, severity=Severity.CRITICAL, weight=5, code="x", key=""):
    return Issue(
        code=code, module=module, severity=severity, title="t", weight=weight, key=key
    )


def test_clean_site_scores_100():
    overall, scores = compute_scores([])
    assert overall == 100
    assert set(scores) == {m.value for m in Module}


def test_critical_issue_lowers_score():
    assert module_score([issue()], Module.SEO) < 100


def test_repeated_code_penalty_is_capped():
    many = [issue(code="dup") for _ in range(50)]
    few = [issue(code="dup") for _ in range(4)]
    assert module_score(many, Module.SEO) == module_score(few, Module.SEO)


def test_score_stays_in_range_however_broken_the_site():
    issues = [issue(code=f"c{i}") for i in range(200)]
    assert 0 <= module_score(issues, Module.SEO) <= 100


def test_score_never_saturates_so_progress_is_always_visible():
    """Головна властивість шкали: виправлення завжди рухає цифру.

    Лінійна формула з clamp давала 0 будь-якому дуже поганому сайту, тож
    повторний аудит після половини виправлень показував той самий нуль —
    і клієнт не бачив, за що заплатив.
    """
    broken = [issue(code=f"c{i}") for i in range(60)]
    half_fixed = broken[:30]

    assert module_score(broken, Module.SEO) > 0
    assert module_score(half_fixed, Module.SEO) > module_score(broken, Module.SEO)


def test_half_scale_is_the_penalty_that_costs_exactly_half_the_score():
    from app.audit.scoring import MODULE_HALF_SCALE

    penalty = MODULE_HALF_SCALE[Module.SEO]
    # weight × severity_multiplier = 1 × 5 на issue, кожен зі своїм code
    issues = [issue(code=f"c{i}", weight=1) for i in range(int(penalty // 5))]

    assert module_score(issues, Module.SEO) == 50


def test_more_issues_never_raise_the_score():
    growing = [issue(code=f"c{i}") for i in range(20)]
    scores = [module_score(growing[:n], Module.SEO) for n in range(1, 20)]

    assert scores == sorted(scores, reverse=True)


def test_skipped_module_excluded_from_overall():
    issues = [issue(module=Module.SEO)]
    overall_all, _ = compute_scores(issues)
    overall_skip, scores = compute_scores(issues, skipped_modules={Module.PERFORMANCE})
    assert "performance" not in scores
    assert overall_skip < overall_all


def test_info_severity_has_no_penalty():
    assert module_score([issue(severity=Severity.INFO, weight=0)], Module.SEO) == 100


def test_overall_is_absent_when_most_of_the_audit_is_blind():
    """aequo.ua віддав агенту 403. Від аудиту лишились швидкість (її міряє
    Google, і його сайт не блокує) та tech — і сайт, про який ми не знаємо
    нічого, отримав 84 бали, другий результат серед 114 у вибірці.
    """
    blind = {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY}
    overall, scores = compute_scores([issue(module=Module.TECH)], skipped_modules=blind)

    assert overall is None, "бал за меншістю напрямів нічого не означає"
    # Перелік не хардкодимо: він росте разом із продуктом. Важливо, що
    # осліплі модулі зникли, а решта рахується далі.
    assert not {m.value for m in blind} & set(scores), "осліплий модуль не має балу"
    assert "tech" in scores, "самі модулі рахуються далі"


def test_one_missing_module_still_gives_an_overall():
    """Без ключа PSI немає Core Web Vitals — це нормальний, частий випадок,
    і він не має позбавляти клієнта загальної оцінки."""
    overall, _ = compute_scores(
        [issue(module=Module.SEO)], skipped_modules={Module.PERFORMANCE}
    )

    assert overall is not None


def test_band_of_absent_score_is_unknown():
    from app.audit.scoring import band

    assert band(None) == "unknown"


def test_one_repeated_problem_cannot_decide_a_module():
    """`ai.jsonld.missing` (вага 4, high) давав 12 за штуку й 48 у старій
    стелі — при half_scale 30 один цей код опускав модуль зі 100 до 38.
    Наслідок був не теоретичний: занедбаний сайт на WordPress обганяв
    stripe.com, бо CMS роздає розмітку з коробки."""
    from app.audit.scoring import MAX_PENALTY_SHARE_OF_HALF, MODULE_HALF_SCALE

    half = MODULE_HALF_SCALE[Module.AI_READY]
    many = [
        issue(module=Module.AI_READY, severity=Severity.HIGH, weight=4, code="ai.jsonld")
        for _ in range(20)
    ]

    score = module_score(many, Module.AI_READY)
    floor = 100 * half / (half + half * MAX_PENALTY_SHARE_OF_HALF)

    assert score >= round(floor) - 1, "один код усе ще вирішує модуль сам"
    assert score >= 60


def test_a_single_critical_finding_is_never_softened():
    """Стеля приборкує повторення, а не силу проблеми. Одна критична
    знахідка в tech (5×5=25 при half_scale 20) не має обрізатись до 10 —
    інакше чек, який ловить найгірше, важив би менше за пару дрібних."""
    one_critical = [issue(module=Module.TECH, severity=Severity.CRITICAL, weight=5, code="a")]
    two_small = [
        issue(module=Module.TECH, severity=Severity.LOW, weight=1, code="b"),
        issue(module=Module.TECH, severity=Severity.LOW, weight=1, code="c"),
    ]

    assert module_score(one_critical, Module.TECH) < module_score(two_small, Module.TECH)


def test_different_problems_still_add_up():
    """Стеля на код не має перетворитися на стелю для модуля: сайт із
    десятьма різними проблемами мусить стояти нижче за сайт з однією."""
    one = [issue(module=Module.SEO, code="a")]
    ten = [issue(module=Module.SEO, code=f"c{i}") for i in range(10)]

    assert module_score(ten, Module.SEO) < module_score(one, Module.SEO) - 20


def test_version_changes_when_a_check_weight_changes():
    """Ручні рядки версій живуть доти, доки про них памʼятають. Відбиток
    набору чеків міняється сам — саме на тих змінах, які найлегше не
    помітити."""
    from app.audit.checks import REGISTRY
    from app.audit.versions import detector_version

    before = detector_version()
    check = REGISTRY[0]
    original = check.weight
    try:
        check.weight = original + 1
        assert detector_version() != before
    finally:
        check.weight = original
    assert detector_version() == before


def test_version_changes_when_the_scoring_formula_changes():
    """8 серпня друга стеля зсунула бали всієї вибірки, і попередні аудити
    стали непорівнянними мовчки. Ця перевірка робить таке помітним."""
    from app.audit import scoring
    from app.audit.versions import scoring_version

    before = scoring_version()
    original = scoring.MAX_PENALTY_SHARE_OF_HALF
    try:
        scoring.MAX_PENALTY_SHARE_OF_HALF = original + 0.1
        assert scoring_version() != before
    finally:
        scoring.MAX_PENALTY_SHARE_OF_HALF = original
    assert scoring_version() == before


def test_report_language_does_not_change_the_config_version():
    """Мова міняє текст, а не знахідки. Якби вона входила у відбиток,
    той самий аудит двома мовами виглядав би як два різні прогони."""
    from app.audit.orchestrator import AuditOptions
    from app.audit.versions import config_version

    assert config_version(AuditOptions(max_pages=10)) == config_version(AuditOptions(max_pages=10))
    assert config_version(AuditOptions(max_pages=10)) != config_version(AuditOptions(max_pages=25))


def test_model_is_recorded_only_when_it_actually_answered():
    """Заданий ключ ще нічого не означає: виклик міг не відбутися, і тоді
    аудит порахований без семантики."""
    from app.audit.llm.base import SiteBrief
    from app.audit.orchestrator import AuditOptions, _model_used
    from app.audit.types import SiteContext

    ctx = SiteContext(entry_url="https://e.com/", origin="https://e.com")
    options = AuditOptions(llm_model="claude-opus-5")

    assert _model_used(ctx, options) is None
    ctx.brief = SiteBrief(analysed=False, error="ключа немає")
    assert _model_used(ctx, options) is None
    ctx.brief = SiteBrief(analysed=True, name="Acme")
    assert _model_used(ctx, options) == "claude-opus-5"


def test_extra_finding_never_lowers_the_penalty():
    """Більше проблем не може означати кращий бал.

    Стеля рахувалася від значення останнього обробленого issue, тож менш
    серйозна знахідка, додана до тієї самої групи, знижувала штраф: сайт
    із блокуючою вадою доступності мав 57, а той самий сайт із блокуючою
    плюс однією звичайною — 67.
    """
    blocking = issue(code="a11y.failures", module=Module.ACCESSIBILITY,
                      severity=Severity.HIGH, weight=3)
    ordinary = issue(code="a11y.failures", module=Module.ACCESSIBILITY,
                      severity=Severity.MEDIUM, weight=3)
    alone = module_penalty([blocking], Module.ACCESSIBILITY)
    together = module_penalty([blocking, ordinary], Module.ACCESSIBILITY)
    assert together >= alone


def test_penalty_does_not_depend_on_the_order_of_findings():
    """Один і той самий набір знахідок — один і той самий штраф."""
    heavy = issue(code="seo.title", severity=Severity.HIGH, weight=3)
    light = issue(code="seo.title", severity=Severity.LOW, weight=1)
    assert module_penalty([heavy, light], Module.SEO) == module_penalty(
        [light, heavy], Module.SEO
    )



# ── стеля рахується на проблемі, а не на детекторі ─────────────────────────


def cwv(metric, severity=Severity.CRITICAL):
    """Реальна форма проблеми: один код, різні метрики, вага 4."""
    return issue(
        module=Module.PERFORMANCE,
        severity=severity,
        weight=4,
        code="perf.core_web_vitals",
        key=metric,
    )


def test_issue_key_is_the_code_when_the_check_knows_one_problem():
    assert issue(code="seo.sitemap").issue_key == "seo.sitemap"


def test_issue_key_names_the_variant_when_the_check_knows_several():
    assert cwv("lcp").issue_key == "perf.core_web_vitals:lcp"


def test_second_independent_problem_of_one_detector_costs_something():
    """Найдорожчий наслідок стелі на `code`.

    LCP і INP — різні проблеми з різними виправленнями, але жили під одним
    кодом. При критичній метриці (вага 4 × 5 = 20 при стелі 20) друга з них
    коштувала рівно нуль: сайт з однією провальною метрикою й сайт із двома
    отримували однаковий бал модуля. На calendly.com це були LCP 5204 мс і
    INP 652 мс — обидві критичні, обидві реальні.
    """
    one = module_penalty([cwv("lcp")], Module.PERFORMANCE)
    two = module_penalty([cwv("lcp"), cwv("inp")], Module.PERFORMANCE)
    three = module_penalty([cwv("lcp"), cwv("inp"), cwv("cls")], Module.PERFORMANCE)

    assert two > one, "друга незалежна проблема мусить додати штраф"
    assert three > two, "третя теж"
    assert module_score([cwv("lcp"), cwv("inp")], Module.PERFORMANCE) < module_score(
        [cwv("lcp")], Module.PERFORMANCE
    )


def test_the_same_problem_repeated_is_still_capped():
    """Стеля нікуди не поділась: вона приборкує повторення однієї проблеми.

    Двадцять сторінок із поганим LCP — це один дефект, а не двадцять, і
    занулювати модуль він не має.
    """
    one = module_penalty([cwv("lcp")], Module.PERFORMANCE)
    twenty = module_penalty([cwv("lcp") for _ in range(20)], Module.PERFORMANCE)

    assert twenty < one * 20, "двадцять входжень не коштують у двадцять разів більше"
    assert twenty <= one * MAX_PENALTY_PER_KEY, "стеля повторень — не більше 2×"
    assert module_score([cwv("lcp") for _ in range(20)], Module.PERFORMANCE) > 0


def test_a_light_problem_repeated_costs_twice_the_single_one():
    """Саме тут стеля повторень працює як задумано — рівно 2×."""
    light = [
        issue(module=Module.SEO, severity=Severity.MEDIUM, weight=2, code="seo.image_alt")
        for _ in range(20)
    ]
    one = module_penalty(light[:1], Module.SEO)

    assert module_penalty(light, Module.SEO) == one * MAX_PENALTY_PER_KEY


def test_a_heavy_problem_repeated_is_clamped_by_the_module_ceiling():
    """Для важкої знахідки повторення не додає нічого — і це не K4.

    Друга стеля (`MAX_PENALTY_SHARE_OF_HALF` від півшкали модуля) нижча за
    одну критичну знахідку Core Web Vitals: 15 проти 20. `max(worst, ceiling)`
    згортається до самої знахідки, тож ліміт групи дорівнює їй.

    Це властивість взаємодії двох стель, а не поділу на `issue_key`: вона
    існувала й тоді, коли стеля рахувалась на `code`. Зафіксовано тестом,
    щоб наступна зміна параметрів шкали побачила її явно, а не заново
    відкрила на живих даних.
    """
    heavy = [cwv("lcp") for _ in range(20)]
    ceiling = MODULE_HALF_SCALE[Module.PERFORMANCE] * MAX_PENALTY_SHARE_OF_HALF
    single = module_penalty(heavy[:1], Module.PERFORMANCE)

    assert single > ceiling, "одна знахідка вже перевищує другу стелю"
    assert module_penalty(heavy, Module.PERFORMANCE) == single


def test_repetitions_of_different_problems_are_capped_separately():
    """Кожна проблема має власну стелю, і чужі повторення її не з'їдають."""
    lcp = [cwv("lcp") for _ in range(20)]
    inp = [cwv("inp") for _ in range(20)]

    assert module_penalty(lcp + inp, Module.PERFORMANCE) == 2 * module_penalty(
        lcp, Module.PERFORMANCE
    )


def test_degrees_of_one_problem_share_a_cap():
    """Порожній key означає «чек знає одну проблему» — і стеля спільна.

    `tech.security_headers` віддає «бракує кількох» і «немає жодного»: це
    один дефект у двох ступенях, а не два дефекти.
    """
    both = [
        issue(module=Module.TECH, severity=Severity.HIGH, weight=3, code="tech.security_headers"),
        issue(module=Module.TECH, severity=Severity.LOW, weight=3, code="tech.security_headers"),
    ]
    worst_alone = module_penalty(both[:1], Module.TECH)

    assert module_penalty(both, Module.TECH) <= worst_alone * 2


# ── G6 / E-07: межа скорингу зсунулась ПОКОЛІННЯМ, а не формулою ──────
#
# Вилучення `ai.schema.faq` не чіпає жодної константи: сайт, у якого цієї
# знахідки не було, отримує рівно той самий бал. Але аудити по різні боки
# вилучення все одно непорівнянні — той, що був до, ніс штраф, якого
# після не буває. Саме це й називає `SCORING_RULES`: підняв його той, хто
# змінив правило підрахунку, а не той, хто зрушив число.


def test_g6_the_scoring_constants_are_byte_identical_to_the_accepted_baseline():
    """Заморожені константи не зрушив ніхто. Перелічені поіменно.

    Перелік тут не дублює код заради дублювання: `scoring_version()` хешує
    рівно ці величини, і мовчазна зміна будь-якої з них зсунула б бали всієї
    вибірки без жодного рядка в історії поколінь.
    """
    from app.audit import scoring

    assert scoring.SEVERITY_MULTIPLIER == {
        Severity.CRITICAL: 5, Severity.HIGH: 3, Severity.MEDIUM: 2,
        Severity.LOW: 1, Severity.INFO: 0,
    }
    assert scoring.MODULE_WEIGHT == {
        Module.SEO: 0.26, Module.PERFORMANCE: 0.18, Module.AI_READY: 0.16,
        Module.TECH: 0.16, Module.LLM_VISIBILITY: 0.14, Module.ACCESSIBILITY: 0.10,
    }
    assert round(sum(scoring.MODULE_WEIGHT.values()), 10) == 1.0
    assert scoring.MAX_PENALTY_PER_KEY == 2.0
    assert scoring.MAX_PENALTY_SHARE_OF_HALF == 0.5
    assert scoring.MIN_COVERED_WEIGHT == 0.5
    # Межі виключні: band() віддає назву першій смузі, ДО якої бал не дотягнув,
    # тож 40 означає «critical — це 0..39», як і в таблиці документації.
    assert scoring.BANDS == ((40, "critical"), (60, "poor"), (80, "medium"), (101, "good"))
    assert set(scoring.MODULE_HALF_SCALE) == set(Module)


def test_g6_the_scoring_fingerprint_moved_only_because_the_generation_moved():
    """Конструктивний доказ, що формула не змінилась.

    Повертаємо ОДНЕ значення — покоління — до прийнятого G5c і вимагаємо
    прийнятий відбиток назад. Якби разом із ним зрушила бодай одна вага,
    півшкала, стеля, множник чи смуга, рівність не відновилася б.
    """
    from app.audit import versions

    assert versions.SCORING_RULES == "5"
    assert versions.scoring_version() == "aa4ecc62a5a3"

    original = versions.SCORING_RULES
    try:
        versions.SCORING_RULES = "4"
        assert versions.scoring_version() == "c6a1c3fd43d8", (
            "з поколінням G5c відбиток не відновився — зрушила сама формула"
        )
    finally:
        versions.SCORING_RULES = original
    assert versions.scoring_version() == "aa4ecc62a5a3"


def test_g6_removing_a_scored_check_changes_no_score_that_did_not_carry_it():
    """Сайт без цієї знахідки не зрушив ані на бал.

    Це і є причина, чому A/B мусить показати зміни РІВНО на тих сайтах,
    що несли `ai.schema.faq`, і нуль деінде.
    """
    from app.audit.scoring import compute_scores

    others = [
        issue(module=Module.AI_READY, severity=Severity.MEDIUM, weight=3, code="ai.jsonld"),
        issue(module=Module.SEO, severity=Severity.HIGH, weight=2, code="seo.h1"),
    ]
    retired = Issue(code="ai.schema.faq", module=Module.AI_READY,
                    severity=Severity.LOW, title="t", weight=2)

    without_overall, without = compute_scores(others)
    with_overall, carried = compute_scores([*others, retired])

    assert carried[Module.AI_READY.value] < without[Module.AI_READY.value]
    assert carried[Module.SEO.value] == without[Module.SEO.value], (
        "вилучення чека одного модуля не сміє рухати інший"
    )
    # Загальний бал рухається ЛИШЕ як наслідок зсуву ai_ready, і при вазі 2
    # та серйозності LOW цей зсув часто не переживає округлення: тут 94 і 94
    # при різних модульних балах. Вимагати строгої нерівності означало б
    # вимагати, щоб знахідка коштувала більше, ніж вона коштує.
    assert with_overall <= without_overall


def test_g6_every_active_check_keeps_the_price_it_had():
    """Жодна ціна, крім зниклої, не змінилась.

    Доводиться тим самим дайджестом оголошень, що й у E-07: рядки живих
    чеків плюс ПРИЙНЯТИЙ рядок вилученого дають прийнятий відбиток. Ваги,
    серйозності, зусилля й варіанти всіх вісімдесяти чеків входять у цей
    рядок, тож рівність нижче — твердження про кожен із них.
    """
    import hashlib

    from app.audit.checks import REGISTRY

    rows = sorted(f"{c.code}:{c.module.value}:{c.severity.value}:{c.weight}:"
                  f"{c.effort.value}:{','.join(c.variants)}" for c in REGISTRY)
    assert len(rows) == 80
    restored = sorted([*rows, "ai.schema.faq:ai_ready:low:2:medium:"])
    assert hashlib.sha256("\n".join(restored).encode()).hexdigest()[:16] == "e3b391e478f8c347"
