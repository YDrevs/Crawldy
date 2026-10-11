# Перші два звіти AuditLens: перевірка придатності

Два PDF від 2026-08-23: `auditlensapp.com` (7 сторінок, 13 знахідок) і
`dronehub.ai` (8 сторінок, 15 знахідок). Перенесено в `runs.json`
дослівно; 28 знахідок звелися до понять без залишку.

Це перевірка методики, а не оцінка конкурента. Висновків про якість
AuditLens за двома сайтами не робимо.

## Критерії з SUFFICIENCY.md

| # | критерій | результат |
|---|---|---|
| 1 | знахідки перелічені окремо | **так** — заголовок, серйозність, опис, рекомендація |
| 2 | знахідку можна звести до поняття | **так** — 28 з 28, після додавання трьох понять |
| 3 | видно, чи є бал | **так** — загальний плюс сім розділових |
| 4 | видно межу спостереження | **ні** — жоден звіт не називає, скільки сторінок прочитано |
| 5 | доказ під знахідкою | частково — імена файлів і параметри є в одній знахідці, решта без |
| 6 | порядок або пріоритет | **так** — HIGH / MEDIUM / LOW при кожній |

Три з чотирьох обовʼязкових виконано. Четвертий не виконано **прямо**,
але виводиться з формулювань: «Based solely on the text content»,
«Based purely on text», «the provided content», «within the 'Website
Content' section». Це визнання того, що аналізувався текст однієї
сторінки, — але як побічна фраза в описі знахідки, а не як заявлена
межа. Різниця істотна: клієнт, який читає бал 82, ніде не бачить, що
його поставлено за один документ.

**Висновок про методику:** порівняння на рівні знахідок можливе. Розділ
про покриття доведеться будувати на висновку з формулювань, і це буде
позначено як висновок, а не як заявлене число.

## Що збережено дослівно, бо саме воно й цінне

### Не виміряно — але бал поставлено

- `auditlensapp` / Performance Metrics = **80/100**, і єдина знахідка
  розділу: *«No specific performance metrics provided»*, «there's no
  visible indication of the page's own loading speed or optimization
  details from the provided content».
- `auditlensapp` / Responsiveness = **70/100**, і єдина знахідка:
  *«Based solely on the text content, it's impossible to evaluate how
  the layout, images, and text scale across different devices»*.
- `dronehub` / Broken Links = **95/100, «Excellent»**, і єдина знахідка
  розділу має серйозність **HIGH**: *«This makes it impossible to
  verify link health from the input»*.

Третій випадок вартий окремої уваги: розділ названо відмінним, а
всередині стоїть знахідка найвищої серйозності, яка каже, що перевірити
нічого не вдалося. Бал і зміст розділу суперечать одне одному в одному
документі.

### Припущення замість спостереження

- `dronehub`: *«While not explicitly stated in the provided content...
  Without a full page load analysis, this is an assumption»* — і це
  надруковано як знахідка з рекомендацією.
- `dronehub`: *«Next.js usually handles `srcset` for different devices.
  Assuming this is correctly implemented, images should scale well»*.
- `auditlensapp`: рекомендація *«Implement lazy loading for images (if
  any were present)»* — умовний спосіб щодо самого існування предмета.

### Вхідні дані, у яких звіт сумнівається сам

Обидва звіти отримали «Number of Links Found: 0» і пояснили це
**по-різному**:

- `dronehub`: *«likely an error in the input data as numerous links are
  clearly present»* — HIGH.
- `auditlensapp`: *«The system detected '0' links, likely due to this
  not being a navigable link»* — LOW.

Той самий симптом, два різні пояснення, різні серйозності. Жодне з них
не веде до відмови від бала розділу.

### Знахідка в сумнівному розділі

`auditlensapp` / «Input field URL is not a functional link» лежить у
розділі **Broken Links**, і рекомендація в тій самій знахідці каже:
*«This is a UI/UX issue, not a broken link»*. Продукт сам зазначає, що
поклав знахідку не туди. Тому `source_category` зберігається окремо від
`topic`.

### Похвала, порахована як проблема

З 28 знахідок **12 — це похвала**, ще 4 — «добре, але».

`dronehub` подано як *«We found 15 issues»*, і серед них: «Clear Value
Proposition», «Strong Use of Social Proof and Authority», «CTA Variety
and Clarity», «Logical Content Flow», «Effective Use of Visual
Elements», «CTA Placement and Visibility», «Strong Trust Signals»,
«Clear Call-to-Actions», «Addressing Objections», «Keywords in Meta
Description», «Heading Structure for Content Flow». Рекомендації до них
починаються з «The value proposition is strong», «The trust signals are
excellent», «The CTAs are generally excellent».

Тобто одинадцять із пʼятнадцяти «проблем» — компліменти. Ми це не
виправляємо: `polarity` позначає, звіт лишається таким, як є.

## Розриви, які ці два звіти виявили в нашому представленні

Дописано в `normalize.py` — усе адитивно:

1. **`Polarity`** — `defect` / `praise` / `mixed`. Без нього похвала
   рахувалася б знахідкою, і перетин знахідок двох продуктів був би
   арифметично неправильним.
2. **`Basis`** — `observed` / `assumed` / `unverifiable` /
   `input_suspect`. Прапорця `measurable` було замало: він не розрізняє
   «продукт визнав, що припускає» і «продукт визнав, що дані битi».
3. **`source_category`** — розділ, у який знахідку поклав сам продукт,
   окремо від поняття, до якого вона зводиться.
4. **`Coverage.category_scores`** — бали за розділами. До наших модулів
   не зводяться: «Copy & Offer» і «Conversion Potential» відповідників
   не мають, і вигадувати їх означало б стверджувати схожість, якої
   немає.
5. **`Coverage.pages_stated`** — розводить «не сказано» і «не зчитали».
   `pages_read=None` було двозначним, а саме на цьому тримається
   половина порівняння.
6. **Три нові поняття** — `cro.social_proof`, `cro.urgency`,
   `content.keyword_coverage`. У Crawldy відповідників немає й не
   планується, але без них знахідки конкурента лягли б в `unmapped`,
   тобто ми втратили б саме те, чим він займається.

Жодне з полів не зачіпає `app/`.

## Числа, які поки що нічого не доводять

| сайт | AuditLens | Crawldy | покриття Crawldy |
|---|---|---|---|
| auditlensapp.com | 72 | **None** | 8 з 8 сторінок, 16 слів статичного тексту |
| dronehub.ai | 82 | 93 | 18 зі 124 |

Порівнювати ці числа між собою не можна: методики різні, і саме тому
абсолютне зіставлення балів не є метрикою цього benchmark'у.

Що варте уваги — не різниця чисел, а розбіжність у **підставі**. На
`auditlensapp.com` Crawldy відмовився дати бал, бо на восьми
прочитаних сторінках знайшов 16 слів статичного тексту; AuditLens
поставив 72 і в розділі про швидкість написав, що метрик не має.
Обидва продукти дивилися на той самий SPA.

Одного сайту для твердження про систематичну поведінку замало.
