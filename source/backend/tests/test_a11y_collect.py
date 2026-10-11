"""Правило вибірки для повторного виміру доступності.

Підкорпус на 150 сайтів існує, щоб виміряти РОЗКИД між двома проходами.
Якщо його склад залежить від порядку читання файлу, версії Python чи
машини, два проходи візьмуть різні сайти — і різниця між ними
описуватиме вибірку, а не мінливість вимірювання.
"""

from scripts.benchmark.a11y_collect import REPEAT_SIZE, repeat_sample
from scripts.benchmark.manifest import Site


def _corpus(count: int = 400) -> list[Site]:
    return [Site(site_id=f"site-{i:04d}", url=f"https://s{i}.example/") for i in range(count)]


def test_the_sample_does_not_depend_on_input_order() -> None:
    sites = _corpus()
    forward = [s.site_id for s in repeat_sample(sites)]
    backward = [s.site_id for s in repeat_sample(list(reversed(sites)))]
    assert forward == backward


def test_the_sample_is_stable_across_calls() -> None:
    sites = _corpus()
    assert [s.site_id for s in repeat_sample(sites)] == [
        s.site_id for s in repeat_sample(sites)
    ]


def test_the_sample_has_the_declared_size() -> None:
    assert len(repeat_sample(_corpus())) == REPEAT_SIZE


def test_a_smaller_corpus_yields_everything_rather_than_failing() -> None:
    """Корпус менший за вибірку — не помилка, а просто менша вибірка."""
    assert len(repeat_sample(_corpus(20))) == 20


def test_adding_sites_does_not_reshuffle_those_already_chosen() -> None:
    """Вибірка тримається на хеші кожного сайту, а не на його позиції.

    Це важливо: якби додавання сайту в корпус перетасовувало вибірку,
    повторний прохід після будь-якої зміни корпусу порівнював би різні
    множини. Склад корпусу все одно заморожений, але правило не має
    спиратися на цю заморозку.
    """
    small = _corpus(200)
    chosen = {s.site_id for s in repeat_sample(small, size=50)}
    grown = small + [
        Site(site_id=f"extra-{i}", url=f"https://e{i}.example/") for i in range(50)
    ]
    after = {s.site_id for s in repeat_sample(grown, size=50)}
    # Нові сайти можуть увійти у вибірку — але ті, що вибули, вибули
    # через них, а не через перетасування: порядок решти незмінний.
    survivors = [s for s in repeat_sample(grown, size=50) if s.site_id in chosen]
    assert [s.site_id for s in survivors] == [
        s.site_id for s in repeat_sample(small, size=50) if s.site_id in after
    ]
