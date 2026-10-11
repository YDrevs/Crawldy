"""Загальний звіт Actual AI Presence — той самий прогін словами власника.

Документів про присутність тепер два, як і про аудит: технічний
(`presence_docx`) показує знаменники, режими, промпти й фрагменти
відповідей; цей показує те саме без жодного з цих слів.

Що тут свідомо НЕ зʼявляється:

* **Бала присутності немає і не буде.** Одне число на обкладинці
  обіцяло б зведену «видимість», якої ми не міряли. Замість нього дві
  великі дроби: скільки перевірених відповідей назвали бренд і скільки
  послалися на сайт.
* **Відсотка немає, поки спостережень мало.** Правило не наше особисте:
  його вже тримає двигун метрик (`MIN_OBSERVATIONS_FOR_RATE`), і
  документ просто показує `rate` тоді, коли двигун його порахував. На
  пʼятьох спостереженнях «20%» було б фальшивою точністю.
* **Смужок і діаграм немає.** Смужка — це той самий відсоток, лише
  намальований, і вона обійшла б попереднє правило мовчки.
* **Порад щодо сайту немає.** Ця перевірка міряє відповіді помічників,
  а не сайт; що саме змінити — предмет звіту аудиту, і документ прямо
  на нього посилається замість вигаданих рекомендацій.

Мов шість, як у решти клієнтської звітності. Мова, якою СТАВИЛИСЯ
запитання, — окремий факт, і він у документі названий: набір промптів
живе в двох мовах, тож німецький документ цілком може описувати
англомовний прогін, і мовчати про це не можна.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from app.audit.i18n import DEFAULT_LOCALE, Locale, parse
from app.report.docx_brand import (
    BRAND_BROWN,
    LOGO,
    MUTED,
    add_footer_for,
    add_rule,
    style_document,
)
from app.report.i18n import t
from app.report.presence_docx import PROVIDER_NAMES, strings_for

# Самоназва мови: у документі стоїть мова ЗАПИТАНЬ, а не мова
# документа, і перекладати її нема потреби — «English» упізнає читач
# будь-якою з шести. Ті самі коди, що приймає набір промптів.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "uk": "українська",
    "de": "Deutsch",
    "es": "español",
    "fr": "français",
    "ru": "русский",
}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Actual AI Presence",
        "site": "Website",
        "brand": "Brand",
        "generated": "Generated",
        "asked_title": "What we asked",
        "asked_lead": (
            "We asked AI assistants the kind of questions a customer asks "
            "when looking for what you offer. None of the questions named "
            "your brand. Below is what the assistants answered."
        ),
        "q_questions": "Questions asked",
        "q_providers": "Assistants asked",
        "q_language": "Questions were asked in",
        "q_answers": "Answers we could use",
        "result_title": "What the answers showed",
        "mentioned_caption": "answers named your brand",
        "cited_caption": "answers pointed to your website",
        "rate_note": "That is {rate}% of the answers we could use.",
        "too_few": (
            "There are too few observations to state a percentage, so the "
            "counts stand on their own."
        ),
        "state_none": (
            "Not a single observation finished with a usable answer. That "
            "is missing measurement, not zero presence."
        ),
        "state_no_mention": (
            "In none of the answers we could use did an assistant name "
            "your brand."
        ),
        "state_mention_no_citation": (
            "Assistants named your brand, but in none of the answers we "
            "could use did they point to your website as a source."
        ),
        "state_both": (
            "Assistants named your brand, and in some answers they pointed "
            "to your website as a source."
        ),
        "natural_title": "When the assistant decided for itself whether to search",
        "explicit_title": "When the assistant was asked to search the web",
        "competitors_title": "Which websites the same answers pointed to",
        "count_note": (
            "The number is how many of the answers we could use pointed "
            "to that site."
        ),
        "provider_count_note": (
            "The number is how many answers we could use came back from "
            "each one."
        ),
        "unbranded_note": (
            "These counts use only the questions that did not name your "
            "brand: those are the ones that show whether you are found "
            "without being named."
        ),
        "providers_title": "Who we asked",
        "provider_unavailable": "no answers came back",
        "limits_title": "What these numbers do not mean",
        "limit_ranking": (
            "They are not a ranking or a position: assistants do not "
            "publish one, and we do not calculate one."
        ),
        "limit_apps": (
            "They describe answers from the providers' interfaces for "
            "developers. The consumer apps can answer differently."
        ),
        "limit_repeat": (
            "The same question can get a different answer next time. These "
            "counts describe this run, not a fixed state."
        ),
        "limit_traffic": (
            "They say nothing about visits or sales: we observed answers, "
            "not people."
        ),
        "next_title": "What this does not cover",
        "next_body": (
            "This check measures what assistants answered, not your "
            "website. What to change on the site is the subject of the "
            "audit report."
        ),
        "deliverable_no": (
            "This run did not reach the coverage we require, so no AI "
            "Presence check was charged for it."
        ),
    },
    "uk": {
        "title": "Actual AI Presence",
        "site": "Сайт",
        "brand": "Бренд",
        "generated": "Сформовано",
        "asked_title": "Що ми питали",
        "asked_lead": (
            "Ми поставили AI-помічникам такі запитання, які ставить "
            "клієнт, коли шукає те, що ви пропонуєте. Жодне запитання не "
            "називало ваш бренд. Нижче — те, що помічники відповіли."
        ),
        "q_questions": "Поставлено запитань",
        "q_providers": "Опитано помічників",
        "q_language": "Мова запитань",
        "q_answers": "Відповідей, придатних до підрахунку",
        "result_title": "Що показали відповіді",
        "mentioned_caption": "відповідей назвали ваш бренд",
        "cited_caption": "відповідей послалися на ваш сайт",
        "rate_note": "Це {rate}% від відповідей, придатних до підрахунку.",
        "too_few": (
            "Спостережень замало, щоб називати відсоток, тож наводимо самі "
            "числа."
        ),
        "state_none": (
            "Жодне спостереження не завершилося придатною відповіддю. Це "
            "відсутність вимірювання, а не нульова присутність."
        ),
        "state_no_mention": (
            "У жодній із придатних відповідей помічник не назвав ваш бренд."
        ),
        "state_mention_no_citation": (
            "Помічники називали ваш бренд, але в жодній із придатних "
            "відповідей не послалися на ваш сайт як на джерело."
        ),
        "state_both": (
            "Помічники називали ваш бренд, а в частині відповідей "
            "посилалися на ваш сайт як на джерело."
        ),
        "natural_title": "Коли помічник сам вирішував, шукати чи ні",
        "explicit_title": "Коли помічника прямо просили пошукати в інтернеті",
        "competitors_title": "На які сайти посилалися ті самі відповіді",
        "count_note": (
            "Число — скільки придатних відповідей послалися на цей сайт."
        ),
        "provider_count_note": (
            "Число — скільки придатних відповідей надійшло від кожного."
        ),
        "unbranded_note": (
            "Ці числа рахують лише ті запитання, які не називали ваш "
            "бренд: саме вони показують, чи знаходять вас без назви."
        ),
        "providers_title": "Кого ми питали",
        "provider_unavailable": "відповідей не надійшло",
        "limits_title": "Чого ці числа не означають",
        "limit_ranking": (
            "Це не місце й не позиція: помічники їх не публікують, а ми не "
            "рахуємо."
        ),
        "limit_apps": (
            "Це відповіді з інтерфейсів провайдерів для розробників. "
            "Застосунки для людей можуть відповідати інакше."
        ),
        "limit_repeat": (
            "Те саме запитання наступного разу може дати іншу відповідь. "
            "Ці числа описують цей прогін, а не сталий стан."
        ),
        "limit_traffic": (
            "Вони нічого не кажуть про відвідування чи продажі: ми "
            "спостерігали відповіді, а не людей."
        ),
        "next_title": "Чого ця перевірка не охоплює",
        "next_body": (
            "Вона міряє те, що відповіли помічники, а не ваш сайт. Що саме "
            "змінити на сайті — предмет звіту аудиту."
        ),
        "deliverable_no": (
            "Прогін не досяг покриття, якого ми вимагаємо, тож перевірку "
            "AI-присутності за нього не списано."
        ),
    },
    "de": {
        "title": "Actual AI Presence",
        "site": "Website",
        "brand": "Marke",
        "generated": "Erstellt",
        "asked_title": "Was wir gefragt haben",
        "asked_lead": (
            "Wir haben KI-Assistenten die Fragen gestellt, die Kundinnen "
            "und Kunden stellen, wenn sie Ihr Angebot suchen. Keine Frage "
            "nannte Ihre Marke. Unten steht, was die Assistenten "
            "geantwortet haben."
        ),
        "q_questions": "Gestellte Fragen",
        "q_providers": "Befragte Assistenten",
        "q_language": "Sprache der Fragen",
        "q_answers": "Auswertbare Antworten",
        "result_title": "Was die Antworten zeigten",
        "mentioned_caption": "Antworten nannten Ihre Marke",
        "cited_caption": "Antworten verwiesen auf Ihre Website",
        "rate_note": "Das sind {rate}% der auswertbaren Antworten.",
        "too_few": (
            "Für eine Prozentangabe sind es zu wenige Beobachtungen; die "
            "Zahlen stehen daher für sich."
        ),
        "state_none": (
            "Keine einzige Beobachtung ergab eine auswertbare Antwort. Das "
            "ist fehlende Messung, keine Präsenz von null."
        ),
        "state_no_mention": (
            "In keiner auswertbaren Antwort nannte ein Assistent Ihre "
            "Marke."
        ),
        "state_mention_no_citation": (
            "Assistenten nannten Ihre Marke, verwiesen aber in keiner "
            "auswertbaren Antwort auf Ihre Website als Quelle."
        ),
        "state_both": (
            "Assistenten nannten Ihre Marke und verwiesen in einem Teil "
            "der Antworten auf Ihre Website als Quelle."
        ),
        "natural_title": "Wenn der Assistent selbst entschied, ob er sucht",
        "explicit_title": "Wenn der Assistent ausdrücklich suchen sollte",
        "competitors_title": "Auf welche Websites dieselben Antworten verwiesen",
        "count_note": (
            "Die Zahl gibt an, wie viele auswertbare Antworten auf diese "
            "Website verwiesen."
        ),
        "provider_count_note": (
            "Die Zahl gibt an, wie viele auswertbare Antworten von jedem "
            "einzelnen kamen."
        ),
        "unbranded_note": (
            "Diese Zahlen beruhen nur auf Fragen, die Ihre Marke nicht "
            "nannten: Sie zeigen, ob man Sie ohne Namen findet."
        ),
        "providers_title": "Wen wir gefragt haben",
        "provider_unavailable": "keine Antworten erhalten",
        "limits_title": "Was diese Zahlen nicht bedeuten",
        "limit_ranking": (
            "Sie sind kein Ranking und keine Position: Assistenten "
            "veröffentlichen keine, und wir berechnen keine."
        ),
        "limit_apps": (
            "Sie beschreiben Antworten aus den Entwickler-Schnittstellen "
            "der Anbieter. Die Apps für Endnutzer können anders antworten."
        ),
        "limit_repeat": (
            "Dieselbe Frage kann beim nächsten Mal anders beantwortet "
            "werden. Die Zahlen beschreiben diesen Lauf, keinen Dauerzustand."
        ),
        "limit_traffic": (
            "Sie sagen nichts über Besuche oder Umsätze: Wir haben "
            "Antworten beobachtet, nicht Menschen."
        ),
        "next_title": "Was diese Prüfung nicht abdeckt",
        "next_body": (
            "Sie misst die Antworten der Assistenten, nicht Ihre Website. "
            "Was auf der Website zu ändern ist, steht im Audit-Bericht."
        ),
        "deliverable_no": (
            "Dieser Lauf erreichte die geforderte Abdeckung nicht; dafür "
            "wurde keine AI-Presence-Prüfung berechnet."
        ),
    },
    "es": {
        "title": "Actual AI Presence",
        "site": "Sitio web",
        "brand": "Marca",
        "generated": "Generado",
        "asked_title": "Qué preguntamos",
        "asked_lead": (
            "Hicimos a los asistentes de IA el tipo de preguntas que hace "
            "un cliente cuando busca lo que usted ofrece. Ninguna pregunta "
            "nombraba su marca. Abajo está lo que respondieron."
        ),
        "q_questions": "Preguntas formuladas",
        "q_providers": "Asistentes consultados",
        "q_language": "Idioma de las preguntas",
        "q_answers": "Respuestas utilizables",
        "result_title": "Qué mostraron las respuestas",
        "mentioned_caption": "respuestas nombraron su marca",
        "cited_caption": "respuestas remitieron a su sitio",
        "rate_note": "Es el {rate}% de las respuestas utilizables.",
        "too_few": (
            "Hay muy pocas observaciones para dar un porcentaje, así que "
            "las cifras se presentan solas."
        ),
        "state_none": (
            "Ninguna observación terminó con una respuesta utilizable. Eso "
            "es falta de medición, no presencia nula."
        ),
        "state_no_mention": (
            "En ninguna de las respuestas utilizables un asistente nombró "
            "su marca."
        ),
        "state_mention_no_citation": (
            "Los asistentes nombraron su marca, pero en ninguna respuesta "
            "utilizable remitieron a su sitio como fuente."
        ),
        "state_both": (
            "Los asistentes nombraron su marca y en parte de las "
            "respuestas remitieron a su sitio como fuente."
        ),
        "natural_title": "Cuando el asistente decidía por sí mismo si buscar",
        "explicit_title": "Cuando se le pidió expresamente buscar en la web",
        "competitors_title": "A qué sitios remitieron esas mismas respuestas",
        "count_note": (
            "La cifra indica cuántas respuestas utilizables remitieron a "
            "ese sitio."
        ),
        "provider_count_note": (
            "La cifra indica cuántas respuestas utilizables llegaron de "
            "cada uno."
        ),
        "unbranded_note": (
            "Estas cifras usan solo las preguntas que no nombraban su "
            "marca: son las que muestran si le encuentran sin nombrarle."
        ),
        "providers_title": "A quién preguntamos",
        "provider_unavailable": "no llegaron respuestas",
        "limits_title": "Qué no significan estas cifras",
        "limit_ranking": (
            "No son una clasificación ni una posición: los asistentes no "
            "las publican y nosotros no las calculamos."
        ),
        "limit_apps": (
            "Describen respuestas de las interfaces para desarrolladores "
            "de los proveedores. Las aplicaciones de consumo pueden "
            "responder de otro modo."
        ),
        "limit_repeat": (
            "La misma pregunta puede recibir otra respuesta la próxima "
            "vez. Estas cifras describen esta ejecución, no un estado fijo."
        ),
        "limit_traffic": (
            "No dicen nada sobre visitas ni ventas: observamos respuestas, "
            "no personas."
        ),
        "next_title": "Qué no cubre esta comprobación",
        "next_body": (
            "Mide lo que respondieron los asistentes, no su sitio. Qué "
            "cambiar en el sitio es el asunto del informe de auditoría."
        ),
        "deliverable_no": (
            "Esta ejecución no alcanzó la cobertura exigida, así que no se "
            "cobró ninguna comprobación de AI Presence."
        ),
    },
    "fr": {
        "title": "Actual AI Presence",
        "site": "Site web",
        "brand": "Marque",
        "generated": "Généré",
        "asked_title": "Ce que nous avons demandé",
        "asked_lead": (
            "Nous avons posé aux assistants IA les questions que pose un "
            "client qui cherche ce que vous proposez. Aucune question ne "
            "nommait votre marque. Voici ce qu'ils ont répondu."
        ),
        "q_questions": "Questions posées",
        "q_providers": "Assistants interrogés",
        "q_language": "Langue des questions",
        "q_answers": "Réponses exploitables",
        "result_title": "Ce que les réponses ont montré",
        "mentioned_caption": "réponses ont nommé votre marque",
        "cited_caption": "réponses ont renvoyé vers votre site",
        "rate_note": "Soit {rate}% des réponses exploitables.",
        "too_few": (
            "Les observations sont trop peu nombreuses pour donner un "
            "pourcentage ; les nombres sont donnés tels quels."
        ),
        "state_none": (
            "Aucune observation n'a abouti à une réponse exploitable. "
            "C'est une mesure absente, pas une présence nulle."
        ),
        "state_no_mention": (
            "Dans aucune réponse exploitable un assistant n'a nommé votre "
            "marque."
        ),
        "state_mention_no_citation": (
            "Les assistants ont nommé votre marque, mais dans aucune "
            "réponse exploitable ils n'ont renvoyé vers votre site comme "
            "source."
        ),
        "state_both": (
            "Les assistants ont nommé votre marque et, dans une partie des "
            "réponses, ont renvoyé vers votre site comme source."
        ),
        "natural_title": "Quand l'assistant décidait lui-même de chercher ou non",
        "explicit_title": "Quand on lui demandait explicitement de chercher sur le web",
        "competitors_title": "Vers quels sites ces mêmes réponses ont renvoyé",
        "count_note": (
            "Le nombre indique combien de réponses exploitables ont "
            "renvoyé vers ce site."
        ),
        "provider_count_note": (
            "Le nombre indique combien de réponses exploitables sont "
            "venues de chacun."
        ),
        "unbranded_note": (
            "Ces nombres ne portent que sur les questions qui ne "
            "nommaient pas votre marque : ce sont elles qui montrent si "
            "l'on vous trouve sans vous nommer."
        ),
        "providers_title": "Qui nous avons interrogé",
        "provider_unavailable": "aucune réponse reçue",
        "limits_title": "Ce que ces nombres ne signifient pas",
        "limit_ranking": (
            "Ce n'est ni un classement ni une position : les assistants "
            "n'en publient pas et nous n'en calculons pas."
        ),
        "limit_apps": (
            "Ils décrivent les réponses des interfaces pour développeurs "
            "des fournisseurs. Les applications grand public peuvent "
            "répondre autrement."
        ),
        "limit_repeat": (
            "La même question peut recevoir une autre réponse la fois "
            "suivante. Ces nombres décrivent cette exécution, pas un état "
            "durable."
        ),
        "limit_traffic": (
            "Ils ne disent rien des visites ni des ventes : nous avons "
            "observé des réponses, pas des personnes."
        ),
        "next_title": "Ce que cette vérification ne couvre pas",
        "next_body": (
            "Elle mesure ce qu'ont répondu les assistants, pas votre site. "
            "Ce qu'il faut changer sur le site relève du rapport d'audit."
        ),
        "deliverable_no": (
            "Cette exécution n'a pas atteint la couverture exigée ; aucune "
            "vérification AI Presence n'a donc été facturée."
        ),
    },
    "ru": {
        "title": "Actual AI Presence",
        "site": "Сайт",
        "brand": "Бренд",
        "generated": "Сформировано",
        "asked_title": "Что мы спрашивали",
        "asked_lead": (
            "Мы задали AI-помощникам те вопросы, которые задаёт клиент, "
            "когда ищет то, что вы предлагаете. Ни один вопрос не называл "
            "ваш бренд. Ниже — то, что помощники ответили."
        ),
        "q_questions": "Задано вопросов",
        "q_providers": "Опрошено помощников",
        "q_language": "Язык вопросов",
        "q_answers": "Ответов, пригодных к подсчёту",
        "result_title": "Что показали ответы",
        "mentioned_caption": "ответов назвали ваш бренд",
        "cited_caption": "ответов сослались на ваш сайт",
        "rate_note": "Это {rate}% ответов, пригодных к подсчёту.",
        "too_few": (
            "Наблюдений слишком мало, чтобы называть процент, поэтому "
            "приводим сами числа."
        ),
        "state_none": (
            "Ни одно наблюдение не завершилось пригодным ответом. Это "
            "отсутствие измерения, а не нулевое присутствие."
        ),
        "state_no_mention": (
            "Ни в одном пригодном ответе помощник не назвал ваш бренд."
        ),
        "state_mention_no_citation": (
            "Помощники называли ваш бренд, но ни в одном пригодном ответе "
            "не сослались на ваш сайт как на источник."
        ),
        "state_both": (
            "Помощники называли ваш бренд, а в части ответов ссылались на "
            "ваш сайт как на источник."
        ),
        "natural_title": "Когда помощник сам решал, искать ли",
        "explicit_title": "Когда помощника прямо просили поискать в интернете",
        "competitors_title": "На какие сайты сослались те же ответы",
        "count_note": (
            "Число — сколько пригодных ответов сослались на этот сайт."
        ),
        "provider_count_note": (
            "Число — сколько пригодных ответов поступило от каждого."
        ),
        "unbranded_note": (
            "Эти числа учитывают только вопросы, которые не называли ваш "
            "бренд: именно они показывают, находят ли вас без названия."
        ),
        "providers_title": "Кого мы спрашивали",
        "provider_unavailable": "ответов не поступило",
        "limits_title": "Чего эти числа не означают",
        "limit_ranking": (
            "Это не место и не позиция: помощники их не публикуют, а мы не "
            "считаем."
        ),
        "limit_apps": (
            "Это ответы из интерфейсов провайдеров для разработчиков. "
            "Приложения для людей могут отвечать иначе."
        ),
        "limit_repeat": (
            "Тот же вопрос в следующий раз может дать другой ответ. Эти "
            "числа описывают этот прогон, а не устойчивое состояние."
        ),
        "limit_traffic": (
            "Они ничего не говорят о посещениях или продажах: мы "
            "наблюдали ответы, а не людей."
        ),
        "next_title": "Чего эта проверка не охватывает",
        "next_body": (
            "Она измеряет ответы помощников, а не ваш сайт. Что именно "
            "менять на сайте — предмет отчёта аудита."
        ),
        "deliverable_no": (
            "Прогон не достиг требуемого покрытия, поэтому проверка "
            "AI-присутствия за него не списана."
        ),
    },
}


def render_presence_owner_docx(
    *,
    run: dict[str, Any],
    metrics: dict[str, Any],
    coverage: dict[str, Any],
    observations: list[dict[str, Any]],
    lang: str = "en",
) -> bytes:
    """Той самий прогін, що й у технічному документі, мовою власника.

    Підпис приймає ті самі аргументи, що `render_presence_docx`, — вид
    документа обирається на місці виклику, і збирач даних один на два
    види. `observations` тут не читаються: фрагменти відповідей —
    предмет технічного документа.
    """
    s = _STRINGS.get(lang, _STRINGS["en"])
    locale = parse(lang) or DEFAULT_LOCALE
    document = Document()
    style_document(document)

    host = str(run.get("url") or "").replace("https://", "").replace("http://", "").strip("/")
    add_footer_for(document, host)

    natural = _combined(metrics, "natural")
    explicit = _combined(metrics, "explicit")
    # Основа документа — режим, у якому помічник вирішує сам: саме так
    # він відповідає людині. Явно заземлений режим — додаткове
    # спостереження, і воно стоїть окремим блоком нижче.
    main = natural or explicit

    _cover(document, run, s, locale, main)
    _asked(document, run, coverage, metrics, s)
    _result(document, s, natural, explicit)
    _competitors(document, metrics, s)
    _providers(document, metrics, s)
    _limits(document, s)
    _closing(document, s, lang)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ── блоки ──────────────────────────────────────────────────────────────


def _combined(metrics: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """Зведення по всіх провайдерах у режимі; None, коли режиму не було."""
    block = (metrics.get("modes") or {}).get(mode)
    if not block:
        return None
    combined = block.get("combined")
    return combined if isinstance(combined, dict) else None


def _pair(combined: dict[str, Any] | None, key: str) -> tuple[int, int, float | None]:
    """Чисельник, знаменник і частка — рівно те, що порахував двигун."""
    value = (combined or {}).get(key) or {}
    return (
        int(value.get("numerator") or 0),
        int(value.get("denominator") or 0),
        value.get("rate"),
    )


def _cover(
    document: Any,
    run: dict[str, Any],
    s: dict[str, str],
    locale: Locale,
    main: dict[str, Any] | None,
) -> None:
    if LOGO.exists():
        logo = document.add_paragraph()
        logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo.add_run().add_picture(str(LOGO), width=Cm(4.2))
        logo.paragraph_format.space_after = Pt(18)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = title.add_run(s["title"])
    run_title.bold = True
    run_title.font.size = Pt(24)
    run_title.font.color.rgb = BRAND_BROWN
    title.paragraph_format.space_after = Pt(2)

    kind = document.add_paragraph()
    kind.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kind_run = kind.add_run(t("kind_general", locale))
    kind_run.font.size = Pt(11)
    kind_run.font.color.rgb = MUTED
    kind.paragraph_format.space_after = Pt(10)

    for label, value in ((s["site"], run.get("url")), (s["brand"], run.get("brand"))):
        line = document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        line_run = line.add_run(f"{label}: {value or '—'}")
        line_run.font.size = Pt(12)
        line.paragraph_format.space_after = Pt(0)

    finished = run.get("finished_at") or run.get("created_at")
    if isinstance(finished, datetime):
        date = document.add_paragraph()
        date.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_run = date.add_run(f"{s['generated']}: {finished:%Y-%m-%d}")
        date_run.font.size = Pt(9.5)
        date_run.font.color.rgb = MUTED

    add_rule(document)

    # Дві дроби замість бала. Знаменник видно завжди: «2 із 6» і «2 із
    # 60» — різні твердження, і зведення їх в одне число приховало б
    # саме те, чим вони різні.
    mentioned = _pair(main, "mention_presence")
    cited = _pair(main, "citation_presence")
    if mentioned[1] == 0 and cited[1] == 0:
        # «0 / 0» читається як «вас не називають», хоча означає інше:
        # придатних відповідей не було зовсім. Замість дробу — речення,
        # яке каже саме це.
        empty = document.add_paragraph()
        empty.alignment = WD_ALIGN_PARAGRAPH.CENTER
        empty.paragraph_format.space_before = Pt(20)
        empty_run = empty.add_run(s["state_none"])
        empty_run.font.size = Pt(11)
    else:
        _figure(document, mentioned[0], mentioned[1], s["mentioned_caption"])
        _figure(document, cited[0], cited[1], s["cited_caption"])

    if run.get("deliverable") is False:
        settled = document.add_paragraph()
        settled.alignment = WD_ALIGN_PARAGRAPH.CENTER
        settled.paragraph_format.space_before = Pt(14)
        settled_run = settled.add_run(s["deliverable_no"])
        settled_run.font.size = Pt(9)
        settled_run.font.color.rgb = MUTED


def _figure(document: Any, numerator: int, denominator: int, caption: str) -> None:
    value = document.add_paragraph()
    value.alignment = WD_ALIGN_PARAGRAPH.CENTER
    value.paragraph_format.space_before = Pt(16)
    value.paragraph_format.space_after = Pt(0)
    figure = value.add_run(f"{numerator} / {denominator}")
    figure.bold = True
    figure.font.size = Pt(40)
    figure.font.color.rgb = BRAND_BROWN

    line = document.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    line_run = line.add_run(caption)
    line_run.font.size = Pt(11)
    line_run.font.color.rgb = MUTED


def _asked(
    document: Any,
    run: dict[str, Any],
    coverage: dict[str, Any],
    metrics: dict[str, Any],
    s: dict[str, str],
) -> None:
    document.add_heading(s["asked_title"], level=1)
    document.add_paragraph(s["asked_lead"])

    languages = [
        LANGUAGE_NAMES.get(code, code)
        for code in sorted({str(code) for code in run.get("languages") or [] if code})
    ]
    facts: list[tuple[str, str]] = [
        (s["q_questions"], str(coverage.get("prompts_declared") or len(run.get("prompts") or []))),
        (s["q_providers"], str(len(metrics.get("providers") or []))),
    ]
    if languages:
        facts.append((s["q_language"], ", ".join(languages)))
    facts.append(
        (
            s["q_answers"],
            f"{coverage.get('observations_ok', 0)} / {coverage.get('observations_total', 0)}",
        )
    )
    for label, value in facts:
        line = document.add_paragraph(style="List Bullet")
        line.add_run(f"{label}: ").bold = True
        line.add_run(value)


def _result(
    document: Any,
    s: dict[str, str],
    natural: dict[str, Any] | None,
    explicit: dict[str, Any] | None,
) -> None:
    document.add_heading(s["result_title"], level=1)

    if natural is not None:
        document.add_heading(s["natural_title"], level=2)
        _mode_body(document, s, natural)
    if explicit is not None:
        document.add_heading(s["explicit_title"], level=2)
        _mode_body(document, s, explicit)
    if natural is None and explicit is None:
        document.add_paragraph(s["state_none"])
        return

    # Знаменник менший за число придатних відповідей, і читач це
    # побачить: рахуються лише запитання без назви бренду. Пояснення
    # одне на розділ — воно однакове для обох режимів.
    note = document.add_paragraph()
    note_run = note.add_run(s["unbranded_note"])
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _mode_body(document: Any, s: dict[str, str], combined: dict[str, Any]) -> None:
    mentioned, mention_total, mention_rate = _pair(combined, "mention_presence")
    cited, cite_total, cite_rate = _pair(combined, "citation_presence")

    if mention_total == 0:
        document.add_paragraph(s["state_none"])
        return

    if mentioned == 0:
        document.add_paragraph(s["state_no_mention"])
    elif cited == 0:
        document.add_paragraph(s["state_mention_no_citation"])
    else:
        document.add_paragraph(s["state_both"])

    for numerator, denominator, rate, caption in (
        (mentioned, mention_total, mention_rate, s["mentioned_caption"]),
        (cited, cite_total, cite_rate, s["cited_caption"]),
    ):
        line = document.add_paragraph(style="List Bullet")
        line.add_run(f"{numerator} / {denominator} ").bold = True
        line.add_run(caption + ".")
        # Відсоток — лише коли його порахував двигун метрик (порогом
        # розпоряджається він) і коли є що показувати: «0%» поруч із
        # «0 / 96» не додає нічого, крім третього повторення нуля.
        if rate is not None and numerator > 0:
            line.add_run(" " + s["rate_note"].format(rate=round(float(rate) * 100)))

    if mention_rate is None:
        note = document.add_paragraph()
        note_run = note.add_run(s["too_few"])
        note_run.font.size = Pt(9)
        note_run.font.color.rgb = MUTED


def _competitors(document: Any, metrics: dict[str, Any], s: dict[str, str]) -> None:
    observed = [row for row in (metrics.get("observed_domains") or [])][:10]
    if not observed:
        return
    document.add_heading(s["competitors_title"], level=1)
    for row in observed:
        line = document.add_paragraph(style="List Bullet")
        line.add_run(str(row.get("domain") or "")).bold = True
        # Число без іменника навмисно: «42 відповіді» проти «58
        # відповідей» — чотири форми множини на шість мов, і жодна з них
        # не додає читачеві нічого понад саме число. Що воно означає,
        # каже підпис під списком.
        line.add_run(f" — {row.get('citations', 0)}")
    note = document.add_paragraph()
    note_run = note.add_run(s["count_note"])
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _providers(document: Any, metrics: dict[str, Any], s: dict[str, str]) -> None:
    document.add_heading(s["providers_title"], level=1)
    # Провайдера перелічуємо за всіма режимами разом: власнику важливо,
    # чи помічник відповідав узагалі, а не в якому з режимів.
    totals: dict[str, int] = {}
    for block in (metrics.get("modes") or {}).values():
        for provider, values in (block.get("per_provider") or {}).items():
            mention = values.get("mention_presence") or {}
            totals[provider] = totals.get(provider, 0) + int(mention.get("denominator") or 0)
    for provider in metrics.get("providers") or sorted(totals):
        line = document.add_paragraph(style="List Bullet")
        line.add_run(PROVIDER_NAMES.get(provider, provider)).bold = True
        answers = totals.get(provider, 0)
        if answers == 0:
            line.add_run(f" — {s['provider_unavailable']}")
        else:
            line.add_run(f" — {answers}")
    note = document.add_paragraph()
    note_run = note.add_run(s["provider_count_note"])
    note_run.font.size = Pt(9)
    note_run.font.color.rgb = MUTED


def _limits(document: Any, s: dict[str, str]) -> None:
    document.add_heading(s["limits_title"], level=1)
    for key in ("limit_ranking", "limit_apps", "limit_repeat", "limit_traffic"):
        document.add_paragraph(s[key], style="List Bullet")


def _closing(document: Any, s: dict[str, str], lang: str) -> None:
    document.add_heading(s["next_title"], level=1)
    document.add_paragraph(s["next_body"])

    marks = document.add_paragraph()
    marks_run = marks.add_run(strings_for(lang)["marks"])
    marks_run.font.size = Pt(8)
    marks_run.font.color.rgb = MUTED


def filename_for(url: str, lang: str) -> str:
    from app.report.presence_docx import filename_for as presence_filename

    return presence_filename(url, lang, kind="general")


__all__ = ["LANGUAGE_NAMES", "filename_for", "render_presence_owner_docx"]
