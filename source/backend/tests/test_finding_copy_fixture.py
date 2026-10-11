"""Затверджені тексти знахідок — шістьма мовами, за ідентифікатором чека.

Свіжий аудит не ставить у трійку всі виправлені знахідки: що потрапить
у топ, вирішують дані сайту. Знімок екрана тому доводить лише те, що
на ньому видно, — а прив'язка тексту до `check_id` мусить бути доведена
незалежно від того, чи спрацював чек на конкретному клієнті.

Тут це доводиться на детермінованих фікстурах: кожен ключ береться з
каталогу за іменем, а не з позиції в переліку, і жодного домену в
перевірці немає.

Фіксується ще й прив'язка до ДОКАЗУ: текст не має стверджувати ширше за
те, що чек справді бачить.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.audit.i18n import CATALOG_FIELDS, CATALOGS, Locale, plural_form, render

LOCALES = (Locale.EN, Locale.UK, Locale.DE, Locale.ES, Locale.FR, Locale.RU)

#: Ключ каталогу → поле → мова → точний рядок, затверджений власником.
APPROVED: dict[str, dict[str, dict[str, str]]] = {
    "a11y.blocking": {
        "consequence": {
            "en": "Some visitors may be unable to use parts of the page. "
            "Accessibility problems affect buttons, links or form fields.",
            "uk": "Деякі відвідувачі можуть не скористатися окремими елементами "
            "сторінки. Проблеми з доступністю стосуються кнопок, посилань або "
            "полів форми.",
            "de": "Einige Besucher können Teile der Seite möglicherweise nicht "
            "bedienen. Barrierefreiheitsprobleme betreffen Schaltflächen, Links "
            "oder Formularfelder.",
            "es": "Es posible que algunos visitantes no puedan utilizar partes de "
            "la página. Los problemas de accesibilidad afectan a botones, enlaces "
            "o campos de formulario.",
            "fr": "Certains visiteurs risquent de ne pas pouvoir utiliser certaines "
            "parties de la page. Des problèmes d’accessibilité concernent des "
            "boutons, des liens ou des champs de formulaire.",
            "ru": "Некоторые посетители могут не суметь воспользоваться отдельными "
            "элементами страницы. Проблемы с доступностью затрагивают кнопки, "
            "ссылки или поля формы.",
        }
    },
    "perf.core_web_vitals.ttfb": {
        "consequence": {
            "en": "The server responds too slowly, delaying the rest of the page.",
            "uk": "Сервер відповідає надто повільно, через що затримується "
            "завантаження сторінки.",
            "de": "Der Server antwortet zu langsam und verzögert dadurch das Laden "
            "der Seite.",
            "es": "El servidor responde demasiado lento, lo que retrasa la carga de "
            "la página.",
            "fr": "Le serveur répond trop lentement, ce qui retarde le chargement de "
            "la page.",
            "ru": "Сервер отвечает слишком медленно, из-за чего загрузка страницы "
            "задерживается.",
        }
    },
    "tech.form_protection.no_visible_marker": {
        "title": {
            "en": "No visible anti-bot protection was detected in the form.",
            "uk": "У формі не виявлено видимих ознак захисту від ботів.",
            "de": "Im Formular wurde kein sichtbarer Schutz vor Bots erkannt.",
            "es": "No se detectó protección visible contra bots en el formulario.",
            "fr": "Aucune protection visible contre les robots n’a été détectée dans "
            "le formulaire.",
            "ru": "В форме не обнаружено видимых признаков защиты от ботов.",
        },
        "description": {
            "en": "No visible protection was found in the initial HTML or the "
            "rendered form. Server-side protection may still exist and cannot be "
            "confirmed by this passive check.",
            "uk": "Видимого захисту не знайдено ні у вихідному HTML, ні у "
            "відображеній формі. Серверний захист може існувати, але пасивна "
            "перевірка не може його підтвердити.",
            "de": "Weder im ursprünglichen HTML noch im gerenderten Formular wurde "
            "sichtbarer Schutz gefunden. Serverseitiger Schutz kann dennoch "
            "vorhanden sein und lässt sich mit dieser passiven Prüfung nicht "
            "bestätigen.",
            "es": "No se encontró protección visible ni en el HTML inicial ni en el "
            "formulario renderizado. Puede existir protección en el servidor, pero "
            "esta comprobación pasiva no puede confirmarla.",
            "fr": "Aucune protection visible n’a été trouvée dans le HTML initial ni "
            "dans le formulaire rendu. Une protection côté serveur peut néanmoins "
            "exister, sans pouvoir être confirmée par cette vérification passive.",
            "ru": "Видимая защита не найдена ни в исходном HTML, ни в отображённой "
            "форме. Серверная защита может существовать, но пассивная проверка не "
            "может её подтвердить.",
        },
    },
}

#: Ключ → мова → кількість → точний заголовок у формі множини.
APPROVED_PLURAL: dict[str, dict[str, dict[int, str]]] = {
    "tech.form_protection.get_method": {
        "en": {1: "1 form submits data via GET", 5: "5 forms submit data via GET"},
        "uk": {
            1: "1 форма надсилає дані методом GET",
            2: "2 форми надсилають дані методом GET",
            5: "5 форм надсилають дані методом GET",
            21: "21 форма надсилає дані методом GET",
        },
        "de": {1: "1 Formular sendet Daten per GET", 5: "5 Formulare senden Daten per GET"},
        "es": {
            1: "1 formulario envía datos mediante GET",
            5: "5 formularios envían datos mediante GET",
        },
        "fr": {
            1: "1 formulaire envoie des données avec GET",
            5: "5 formulaires envoient des données avec GET",
        },
        "ru": {
            1: "1 форма отправляет данные методом GET",
            2: "2 формы отправляют данные методом GET",
            5: "5 форм отправляют данные методом GET",
            21: "21 форма отправляет данные методом GET",
        },
    }
}

#: Ключі, які свіжий аудит може й не показати, але текст яких затверджено
#: раніше. Тут доводиться лише те, що вони існують шістьма мовами й не
#: падають у чужу — самих рядків власник цього разу не переглядав.
COVERED_KEYS = (
    "seo.meta_description.missing",
    "tech.nap.phone_mismatch",
    "ai.schema.contact.missing",
    "a11y.blocking",
    "perf.core_web_vitals.ttfb",
    "tech.form_protection.no_visible_marker",
    "tech.form_protection.get_method",
)

#: Параметри, без яких шаблон лишив би видимий плейсхолдер.
PARAMS: dict[str, dict[str, object]] = {
    "seo.meta_description.missing": {"visible": 160},
    "tech.nap.phone_mismatch": {"count": 3},
    "a11y.blocking": {"count": 3},
    "tech.form_protection.get_method": {"count": 2},
    "perf.core_web_vitals.ttfb": {
        "value": "1.2",
        "unit": " s",
        "strategy": "mobile",
        "threshold": "0.8",
    },
}


@pytest.mark.parametrize("key", sorted(APPROVED))
def test_the_approved_text_is_bound_to_the_check_id(key: str) -> None:
    """Текст береться за ідентифікатором, а не за місцем у переліку."""
    for field, per_locale in APPROVED[key].items():
        for locale in LOCALES:
            got = render(key, PARAMS.get(key, {}), locale)
            assert getattr(got, field) == per_locale[locale.value], f"{locale.value}/{field}"


@pytest.mark.parametrize("key", sorted(APPROVED_PLURAL))
def test_plural_titles_match_the_approved_forms(key: str) -> None:
    for locale in LOCALES:
        for count, expected in APPROVED_PLURAL[key][locale.value].items():
            got = render(key, {"count": count}, locale).title
            assert got == expected, f"{locale.value}/{count}"


@pytest.mark.parametrize("key", COVERED_KEYS)
def test_every_covered_key_speaks_all_six_locales(key: str) -> None:
    """Жодна мова не падає в чужу й не показує сирого плейсхолдера."""
    for locale in LOCALES:
        got = render(key, PARAMS.get(key, {}), locale)
        assert not got.fell_back, f"{locale.value}/{key}: фолбек в англійську"
        assert got.title, f"{locale.value}/{key}: порожній заголовок"
        for field in CATALOG_FIELDS:
            text = getattr(got, field)
            assert "{" not in text, f"{locale.value}/{key}/{field}: плейсхолдер лишився"
            assert key not in text, f"{locale.value}/{key}/{field}: сирий ключ у тексті"


@pytest.mark.parametrize("key", COVERED_KEYS)
def test_no_locale_repeats_another_locale_word_for_word(key: str) -> None:
    """Збіг двох мов — ознака мовчазного фолбеку, а не перекладу.

    Порівнюється `consequence`, а не `title`: заголовок частини
    вимірювальних знахідок — це сама величина (`TTFB = 1.2 s (mobile)`),
    і вона однакова всіма мовами за задумом. Проза мусить різнитися,
    число — ні.
    """
    texts = {
        loc.value: render(key, PARAMS.get(key, {}), loc).consequence for loc in LOCALES
    }
    assert len(set(texts.values())) == len(texts), f"{key}: {texts}"


def test_the_fixture_covers_every_key_the_review_named() -> None:
    """Перелік ключів — частина доказу, і він не має тихо схуднути."""
    named = {
        "seo.meta_description.missing",
        "tech.nap.phone_mismatch",
        "ai.schema.contact.missing",
        "a11y.blocking",
        "perf.core_web_vitals.ttfb",
    }
    assert named <= set(COVERED_KEYS)


def test_the_catalogue_entry_exists_in_every_locale() -> None:
    """Рендер має фолбек; сам каталог — ні. Прогалину видно лише тут."""
    for key in COVERED_KEYS:
        for locale in LOCALES:
            assert key in CATALOGS[locale], f"{locale.value}: немає {key}"


def test_the_machine_readable_fixture_can_be_written(tmp_path: Path) -> None:
    """Той самий доказ у машиночитаному вигляді — для пакета власника.

    Файл будується з КАТАЛОГУ, а не з окремого переліку: розійтися їм
    ніде.
    """
    packet = {
        key: {
            locale.value: {
                field: getattr(render(key, PARAMS.get(key, {}), locale), field)
                for field in CATALOG_FIELDS
            }
            | (
                {
                    "title_plural": {
                        str(n): render(key, {"count": n}, locale).title
                        for n in (1, 2, 5, 21)
                    },
                    "plural_forms": {
                        str(n): plural_form(locale.value, n) for n in (1, 2, 5, 21)
                    },
                }
                if any(f.startswith("title.") for f in CATALOGS[locale][key])
                else {}
            )
            for locale in LOCALES
        }
        for key in COVERED_KEYS
    }
    path = tmp_path / "finding-copy-fixture.json"
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    back = json.loads(path.read_text(encoding="utf-8"))
    assert set(back) == set(COVERED_KEYS)
    assert back["tech.form_protection.get_method"]["uk"]["title_plural"]["21"] == (
        "21 форма надсилає дані методом GET"
    )
