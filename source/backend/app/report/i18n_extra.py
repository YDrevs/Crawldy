"""Каркас звіту чотирма мовами запуску, яких бракувало.

Окремий файл лише через розмір: шість повних мов в одному i18n.py
перетворили б його на два з половиною екрани прокрутки до першої
функції. Реєструється в `STRINGS` поруч із UK та EN; правила ті самі.
"""

from __future__ import annotations

DE: dict[str, str] = {
    "doc_title": "Website-Audit",
    "generated": "Erstellt",
    "status": "Status",
    "pages_crawled": "Gecrawlte Seiten",
    "overall": "Gesamtnote",
    "of_100": "von 100",
    "kind_general": "Allgemeiner Bericht",
    "kind_technical": "Technischer Bericht",
    "part1_title": "Teil 1. Das Wichtigste in Kürze",
    "part1_subtitle": (
        "Für Entscheider: wo die Website steht und was zuerst zu tun ist. Ohne technische Details."
    ),
    "part2_title": "Teil 2. Technische Analyse",
    "part2_subtitle": (
        "Für Entwickler oder SEO-Fachleute: jeder Befund mit Belegen und Seitenadressen."
    ),
    "verdict_critical": (
        "Die Website hat systemische Probleme: Suchmaschinen und KI-Dienste sehen sie deutlich "
        "schlechter, als sie es verdient. Mehrere Bereiche brauchen zugleich Arbeit."
    ),
    "verdict_poor": (
        "Die Grundlage funktioniert, aber die Lücken reichen, um einen Teil der Besucher zu "
        "verlieren. Das meiste davon ist schnell behoben und braucht keinen Neubau."
    ),
    "verdict_medium": (
        "Die Website ist in Ordnung. Was bleibt, sind gezielte Verbesserungen, die Sichtbarkeit "
        "in der Suche und in KI-Diensten bringen."
    ),
    "verdict_good": (
        "Die Website ist in gutem Zustand. Die Befunde sind eher Feinschliff als Probleme "
        "und können ohne Eile angegangen werden."
    ),
    "verdict_unknown": (
        "Diesmal konnten wir die Website nicht bewerten: die meisten Prüfungen blieben "
        "ohne Daten. Die Gründe stehen unten im Abschnitt zu Datenlücken."
    ),
    "area_performance": "Wie schnell sich Seiten beim Besucher öffnen.",
    "area_seo": "Wie gut Suchmaschinen die Website verstehen.",
    "area_ai_ready": (
        "Ob die Website sich Maschinen beschreibt — die Quelle, aus der KI-Dienste Fakten nehmen."
    ),
    "area_llm_visibility": (
        "Ob ein Assistent die Website lesen, erkennen, wer Sie sind, und etwas Zitierbares "
        "finden kann. Ob er tatsächlich zitiert, prüfen wir nicht."
    ),
    "area_tech": (
        "Ob die Website vor Bots geschützt ist und ob Sie sehen, was Besucher tun."
    ),
    "area_accessibility": (
        "Ob die Website auch für Menschen mit eingeschränktem Sehvermögen oder "
        "eingeschränkter Motorik funktioniert, auf jedem Gerät."
    ),
    "col_area_meaning": "Was das bedeutet",
    "col_completeness": "Datenvollständigkeit",
    "completeness_full": "vollständig",
    "completeness_partial": "unvollständig",
    "section_priorities": "Was zuerst zu tun ist",
    "section_scores": "Noten nach Bereichen",
    "section_scores_technical": "Noten, Gewichte und Datenvollständigkeit",
    "section_missing_technical": "Lücken in den Daten",
    "section_missing": "Was wir nicht messen konnten",
    "section_details": "Vollständige Analyse",
    "section_evidence": "Anhang: was wir auf der Website sahen",
    "col_module": "Bereich",
    "col_score": "Note",
    "col_band": "Stufe",
    "col_issues": "Befunde",
    "col_weight": "Gewicht in der Gesamtnote",
    "col_parameter": "Parameter",
    "col_value": "Wert",
    "not_measured": "nicht gemessen",
    "missing_note_excluded": (
        "das Modul ist von der Gesamtnote ausgenommen; sein Gewicht verteilt sich auf die übrigen"
    ),
    "missing_note_partial": (
        "die Note beruht auf einem unvollständigen Satz von Signalen — als Anhaltspunkt lesen"
    ),
    "missing_note_incomplete": "die Modulnote beruht auf unvollständigen Daten",
    "impact_note": (
        "Der Effekt jedes Punkts ist einzeln gemessen — um wie viel die Gesamtnote steigt, wenn "
        "genau er behoben wird. Diese Zahlen dürfen nicht addiert werden."
    ),
    "effect": "Effekt",
    "effort": "Aufwand",
    "pages_affected": "Seiten",
    "site_wide": "gesamte Website",
    "problem": "Was falsch ist",
    "what_to_do": "Was zu tun ist",
    "gives": "Was es bringt",
    "no_priorities": "Keine dringenden Schritte — keine kritischen Probleme gefunden.",
    "part1_missing_intro": (
        "Ein Teil der Signale ließ sich diesmal nicht erheben, daher ist die Note unvollständig:"
    ),
    "evidence": "Beleg",
    "examples": "Beispielseiten",
    "and_more": "…und {count} weitere",
    "no_issues": "Keine Probleme gefunden.",
    "module_not_scored": "Dieser Bereich wurde nicht bewertet — keine Daten erhoben.",
    "severity": "Schweregrad",
    "impact_floored": "der Bereich ist bereits am Minimum, die Note steigt daher nicht",
    "affects": "Betrifft",
    "reason": "Grund",
    "band_critical": "kritisch",
    "band_poor": "schwach",
    "band_medium": "mittel",
    "band_good": "gut",
    "band_unknown": "unbekannt",
    "effort_low": "gering",
    "effort_medium": "mittel",
    "effort_high": "hoch",
    "severity_critical": "kritisch",
    "severity_high": "hoch",
    "severity_medium": "mittel",
    "severity_low": "niedrig",
    "severity_info": "Hinweis",
    "module_accessibility": "Barrierefreiheit",
    "section_passed": "Bestandene Prüfungen: {count}",
    "passed_intro": (
        "Ausdrücklich bestätigte Prüfungen. Sie geben keine Punkte und gleichen keine "
        "Befunde aus — eine Übersicht dessen, was bereits gut gelöst ist."
    ),
    "passed.seo.https": "HTTPS-Verbindung ohne beobachteten TLS-Fehler hergestellt",
    "passed.seo.robots_txt": "robots.txt gefunden und lesbar",
    "passed.seo.sitemap": "Sitemap gefunden; deklarierte Adressen: {declared}",
    "passed.tech.security_headers": (
        "Alle überwachten Schutz-Header auf der geprüften Antwort erkannt"
    ),
    "passed.tech.analytics": "Analytik erkannt: {found}",
    "passed.tech.form_protection": (
        "Sichtbare Anzeichen für Spam-Schutz der Formulare erkannt "
        "({providers}); geprüfte Formulare: {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD auf {pages} von {total} analysierten Seiten erkannt",
    "passed.ai.llms_txt": "llms.txt vorhanden (optionale Konvention)",
    "scores_weight_gap": (
        "Die Gewichte in dieser Tabelle ergeben {shown}. Die restlichen {hidden} stammen weiterhin "
        "aus der Barrierefreiheit: Sie erhält keine Bewertung mehr, behält ihren bisherigen "
        "Beitrag zur Gesamtnote aber vorerst. Die Momentaufnahme steht weiter unten."
    ),
    "a11y_still_weighted": (
        "Barrierefreiheit macht weiterhin {percent} der Gesamtnote aus — der Beitrag ist derselbe "
        "wie vor dem Wechsel zur Momentaufnahme. Das ist vorübergehend: Die Gewichte werden "
        "gesondert überprüft."
    ),
    "a11y_not_weighted": (
        "Barrierefreiheit fließt bei dieser Prüfung nicht in die Gesamtnote ein."
    ),
    "section_a11y_snapshot": "Barrierefreiheit: Momentaufnahme der geprüften Seite",
    "a11y_scope": "Geprüft wurde eine Seite: {url} (mobile Ansicht).",
    "a11y_counts": (
        "Automatische Prüfungen der Barrierefreiheit, die auf diese Seite zutrafen: {applicable}. "
        "Bestanden: {passed}. Nicht bestanden: {failed}."
    ),
    "a11y_clean": (
        "Unter den {applicable} Prüfungen, die auf diese Seite zutrafen, wurden keine maschinell "
        "erkennbaren Probleme gefunden."
    ),
    "a11y_unavailable": (
        "Die Barrierefreiheit wurde nicht gemessen: Das externe Werkzeug lieferte keine Daten für "
        "diese Seite. Das bedeutet nicht, dass es keine Probleme gibt."
    ),
    "a11y_caveat": (
        "Dies ist eine automatische Prüfung einer einzelnen Seite. Sie ist keine Aussage über die "
        "Erfüllung der WCAG und umfasst nicht die gesamte Website. Manche Hürden lassen sich "
        "maschinell nicht erkennen."
    ),
    "a11y_also_reported": "Ebenfalls gemeldet unter „{module}“",
    "a11y_lighthouse_ref": (
        "Lighthouse-Wert für Barrierefreiheit der geprüften Seite (externer Anhaltspunkt, nicht "
        "unsere Bewertung): {score}"
    ),
    "col_a11y_check": "Prüfung",
    "col_a11y_impact": "Auswirkung",
    "col_a11y_also": "Ebenfalls gemeldet",
    "module_performance": "Geschwindigkeit / UX",
    "module_seo": "Basis-SEO",
    "module_ai_ready": "KI-Bereitschaft / LLMO",
    "module_llm_visibility": "Zitierfähigkeit",
    "module_tech": "Schutz und Analytik",
    "ev_pages_ok": "Seiten erfolgreich",
    "ev_pages_failed": "Seiten mit Fehler",
    "ev_max_depth": "Maximale Tiefe",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Seiten mit JSON-LD",
    "ev_schema_types": "schema.org-Typen",
    "ev_url_count": "URLs in der Sitemap",
    "ev_blocked_agents": "Gesperrte KI-Crawler",
    "yes": "ja",
    "no": "nein",
    "present": "vorhanden",
    "absent": "fehlt",
    "none": "keine",
    # ── Bericht für den Inhaber ────────────────────────────────────────────
    "owner_title": "Was gerade mit Ihrer Website passiert",
    "owner_score_caption": "Gesamtnote der Website von 100",
    "owner_meaning_title": "In einfachen Worten",
    "owner_meaning_critical": (
        "Ihre Website arbeitet derzeit kaum für Sie. Menschen, die suchen, was Sie verkaufen, "
        "finden Sie meist nicht — sie landen bei Wettbewerbern. Mit dem Aussehen hat das nichts "
        "zu tun: Es geht um Dinge, die Besucher nie sehen, Google aber schon. Die gute "
        "Nachricht: Genau solche Websites wachsen am schnellsten, denn fast jede Korrektur "
        "zeigt sich im Ergebnis."
    ),
    "owner_meaning_poor": (
        "Die Website funktioniert, aber ein großer Teil Ihrer Kunden geht Ihnen verloren. Wie "
        "ein Laden in guter Lage, dessen Schild nur von einer Straßenseite zu sehen ist: Wer "
        "vorbeigeht, kommt herein — alle anderen erfahren nie, dass es Sie gibt."
    ),
    "owner_meaning_medium": (
        "Die Grundlage stimmt, und die Website trägt sich. Was Sie jetzt von Wettbewerbern "
        "trennt, sind Kleinigkeiten — und genau die entscheiden, wessen Link zuerst gesehen "
        "wird. Ein paar gezielte Korrekturen bringen hier mehr als ein Relaunch."
    ),
    "owner_meaning_good": (
        "Die Website ist gut gebaut — besser als die meisten. Sie brauchen keinen Umbau, "
        "sondern müssen die Position halten: Die Konkurrenz arbeitet auch, und ein Vorsprung "
        "geht leise verloren."
    ),
    "owner_meaning_unknown": (
        "Ihre Website hat unser Programm nicht hineingelassen, daher fehlt uns das ganze Bild. "
        "Meist ist das Schutz vor unerwünschten Besuchern — der aber zugleich Suchmaschinen "
        "aussperrt. Das sollte zuerst geprüft werden."
    ),
    "owner_meaning_empty": (
        "Unter Ihrer Adresse fanden wir eine Seite fast ohne Text. So sieht eine Website aus, "
        "deren Hosting oder Domain abgelaufen ist oder die nie befüllt wurde. Zu bewerten gibt "
        "es hier noch nichts — erst muss die Website öffnen."
    ),
    "owner_meaning_failures": (
        "Die meisten Seiten Ihrer Website haben nicht geantwortet. Wir lasen nur einen kleinen "
        "Teil, und eine Note darauf wäre erfunden. Meist ist der Server überlastet oder ein "
        "Teil der Website defekt."
    ),
    "owner_areas_title": "Sechs Dinge, an denen Sie gemessen werden",
    "owner_area_accessibility": "Ob alle sie nutzen können",
    "owner_area_performance": "Wie schnell die Website öffnet",
    "owner_area_seo": "Ob man Sie in der Suche findet",
    "owner_area_ai_ready": "Ob Software Ihre Website versteht",
    "owner_area_llm_visibility": "Ob ein Assistent etwas über Sie zu sagen hat",
    "owner_area_tech": "Ob Sie sehen, woher Kunden kommen",
    "owner_areas_note": (
        "Ein Strich bedeutet: Dieser Bereich ließ sich nicht prüfen — nicht, dass dort alles "
        "schlecht ist."
    ),
    "owner_problems_title": "Was wir gefunden haben",
    "owner_problem_gravity": "Wie dringend",
    "owner_problem_what": "Was es für Sie bedeutet",
    "owner_gravity_critical": "DRINGEND",
    "owner_gravity_high": "WICHTIG",
    "owner_gravity_poor": "LOHNT SICH",
    "owner_gravity_medium": "KANN WARTEN",
    "owner_gravity_unknown": "ZUR KENNTNIS",
    "owner_problems_note": (
        "Das sind die Hauptpunkte aus {total} Befunden. Die vollständige Liste mit technischen "
        "Details steht in einem separaten Dokument für Ihren Entwickler."
    ),
    "owner_gain_title": "Wie viel besser es sein könnte",
    "owner_gain_now": "Jetzt",
    "owner_gain_after": "Nach Behebung der Befunde",
    "owner_gain_note": (
        "Ein Unterschied von {points} Punkten. Das ist keine Umsatzprognose, sondern der "
        "Zustand der Website: wie leicht Suchmaschinen und Menschen Sie finden und verstehen, "
        "wofür Sie gut sind."
    ),
    "owner_next_title": "Wie es weitergeht",
    "owner_next_body": (
        "Diese Prüfung haben wir selbst durchgeführt, allein anhand Ihrer Webadresse, und sie "
        "hat Sie nichts gekostet. Jeder Befund oben hat eine konkrete technische Ursache und "
        "eine konkrete Lösung — wir wissen, woran es liegt und wie lange die Behebung dauert. "
        "In einem kurzen Gespräch zeigen wir, womit wir beginnen würden, in welcher "
        "Reihenfolge und was sich nach jedem Schritt ändert. Ein Wiederholungsaudit in einem "
        "Monat zeigt das Ergebnis in denselben Zahlen wie dieses."
    ),
    "owner_ai_view_title": "Wie künstliche Intelligenz Ihre Website heute beschreibt",
    "owner_ai_view_note": (
        "Das ist nicht unsere Nacherzählung. So hat die Software Ihre Website verstanden, die "
        "Ihr Kunde fragt, wenn er jemanden zum Beauftragen sucht."
    ),
    "owner_enrich_failed": (
        "Erweiterte Erläuterungen zu diesen Punkten fehlen im Dokument: {reason}"
    ),
}

ES: dict[str, str] = {
    "doc_title": "Auditoría del sitio",
    "generated": "Generado",
    "status": "Estado",
    "pages_crawled": "Páginas rastreadas",
    "overall": "Puntuación global",
    "of_100": "de 100",
    "kind_general": "Informe general",
    "kind_technical": "Informe técnico",
    "part1_title": "Parte 1. Lo esencial",
    "part1_subtitle": (
        "Para quien decide: cómo está el sitio y qué arreglar primero. Sin detalle técnico."
    ),
    "part2_title": "Parte 2. Desglose técnico",
    "part2_subtitle": (
        "Para el desarrollador o especialista SEO: cada hallazgo con pruebas y direcciones."
    ),
    "verdict_critical": (
        "El sitio tiene problemas sistémicos: los buscadores y los servicios de IA lo ven "
        "bastante peor de lo que merece. Varias áreas necesitan trabajo a la vez."
    ),
    "verdict_poor": (
        "La base funciona, pero hay huecos suficientes para perder parte de los visitantes. "
        "La mayoría se arregla rápido y sin rehacer el sitio."
    ),
    "verdict_medium": (
        "El sitio está en orden. Quedan mejoras puntuales que añaden visibilidad en la "
        "búsqueda y en los servicios de IA."
    ),
    "verdict_good": (
        "El sitio está en buen estado. Lo hallado es más pulido que problema, y puede "
        "hacerse sin prisa."
    ),
    "verdict_unknown": (
        "Esta vez no pudimos puntuar el sitio: la mayoría de las comprobaciones quedaron "
        "sin datos. Los motivos están más abajo, en la sección de lagunas de datos."
    ),
    "area_performance": "Con qué rapidez se abren las páginas para el visitante.",
    "area_seo": "Qué tan bien entienden el sitio los buscadores.",
    "area_ai_ready": (
        "Si el sitio se describe a las máquinas — de ahí toman los datos los servicios de IA."
    ),
    "area_llm_visibility": (
        "Si un asistente puede leer el sitio, saber quién eres y encontrar algo que citar. "
        "Si de verdad te cita, no lo comprobamos."
    ),
    "area_tech": (
        "Si el sitio está protegido de bots y si puedes ver qué hacen los visitantes."
    ),
    "area_accessibility": (
        "Si el sitio funciona para personas con visión o movilidad reducida, "
        "en cualquier dispositivo."
    ),
    "col_area_meaning": "Qué significa",
    "col_completeness": "Completitud de datos",
    "completeness_full": "completos",
    "completeness_partial": "incompletos",
    "section_priorities": "Qué arreglar primero",
    "section_scores": "Puntuaciones por área",
    "section_scores_technical": "Puntuaciones, pesos y completitud de datos",
    "section_missing_technical": "Huecos en los datos",
    "section_missing": "Lo que no pudimos medir",
    "section_details": "Desglose completo",
    "section_evidence": "Apéndice: lo que vimos en el sitio",
    "col_module": "Área",
    "col_score": "Puntuación",
    "col_band": "Nivel",
    "col_issues": "Hallazgos",
    "col_weight": "Peso en la global",
    "col_parameter": "Parámetro",
    "col_value": "Valor",
    "not_measured": "no medido",
    "missing_note_excluded": (
        "el módulo queda fuera de la puntuación global; su peso se reparte entre el resto"
    ),
    "missing_note_partial": (
        "la puntuación se basa en un conjunto incompleto de señales — léela como orientación"
    ),
    "missing_note_incomplete": "la puntuación del módulo se basa en datos incompletos",
    "impact_note": (
        "El efecto de cada punto se mide por separado — cuánto sube la puntuación global si "
        "se arregla justo ese. Estos números no se pueden sumar."
    ),
    "effect": "Efecto",
    "effort": "Esfuerzo",
    "pages_affected": "Páginas",
    "site_wide": "todo el sitio",
    "problem": "Qué está mal",
    "what_to_do": "Qué hacer",
    "gives": "Qué ganas",
    "no_priorities": "No hay acciones urgentes — no se encontraron problemas críticos.",
    "part1_missing_intro": (
        "Parte de las señales no se pudo recoger esta vez, así que la puntuación es incompleta:"
    ),
    "evidence": "Prueba",
    "examples": "Páginas de ejemplo",
    "and_more": "…y {count} más",
    "no_issues": "No se encontraron problemas.",
    "module_not_scored": "Esta área no se puntuó — no se recogieron datos.",
    "severity": "Gravedad",
    "impact_floored": "el área ya está en su mínimo, así que la puntuación no subirá",
    "affects": "Afecta a",
    "reason": "Motivo",
    "band_critical": "crítico",
    "band_poor": "flojo",
    "band_medium": "medio",
    "band_good": "bueno",
    "band_unknown": "desconocido",
    "effort_low": "bajo",
    "effort_medium": "medio",
    "effort_high": "alto",
    "severity_critical": "crítica",
    "severity_high": "alta",
    "severity_medium": "media",
    "severity_low": "baja",
    "severity_info": "informativa",
    "module_accessibility": "Accesibilidad",
    "section_passed": "Comprobaciones superadas: {count}",
    "passed_intro": (
        "Comprobaciones confirmadas explícitamente. No suman puntos ni compensan "
        "hallazgos: constancia de lo que ya está bien hecho."
    ),
    "passed.seo.https": "Conexión HTTPS completada sin errores TLS observados",
    "passed.seo.robots_txt": "robots.txt encontrado y legible",
    "passed.seo.sitemap": "Mapa del sitio encontrado; URL declaradas: {declared}",
    "passed.tech.security_headers": (
        "Todas las cabeceras de protección monitorizadas detectadas en la "
        "respuesta analizada"
    ),
    "passed.tech.analytics": "Analítica detectada: {found}",
    "passed.tech.form_protection": (
        "Señales visibles de protección antispam en los formularios "
        "({providers}); formularios comprobados: {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD detectado en {pages} de {total} páginas analizadas",
    "passed.ai.llms_txt": "llms.txt presente (convención opcional)",
    "scores_weight_gap": (
        "Los pesos de esta tabla suman {shown}. El {hidden} restante sigue viniendo de la "
        "accesibilidad: ya no recibe una puntuación, pero por ahora conserva su aportación "
        "anterior a la nota global. La instantánea está más abajo."
    ),
    "a11y_still_weighted": (
        "La accesibilidad aporta todavía el {percent} de la nota global: la aportación es la misma "
        "que antes de pasar a la instantánea. Es temporal: los pesos se revisan por separado."
    ),
    "a11y_not_weighted": (
        "La accesibilidad no entra en la nota global de esta auditoría."
    ),
    "section_a11y_snapshot": "Accesibilidad: instantánea de la página analizada",
    "a11y_scope": "Se analizó una página: {url} (vista móvil).",
    "a11y_counts": (
        "Comprobaciones automáticas de accesibilidad aplicables a esta página: {applicable}. "
        "Superadas: {passed}. No superadas: {failed}."
    ),
    "a11y_clean": (
        "No se encontraron problemas de accesibilidad detectables automáticamente entre las "
        "{applicable} comprobaciones aplicables a esta página."
    ),
    "a11y_unavailable": (
        "La accesibilidad no se midió: la herramienta externa no devolvió datos para esta página. "
        "Eso no significa que no haya problemas."
    ),
    "a11y_caveat": (
        "Esta es una comprobación automática de una sola página. No es un dictamen de conformidad "
        "con las WCAG ni abarca todo el sitio. Algunas barreras no pueden detectarse de forma "
        "automática."
    ),
    "a11y_also_reported": "También se indica en «{module}»",
    "a11y_lighthouse_ref": (
        "Puntuación de accesibilidad de Lighthouse para la página analizada (referencia externa, "
        "no es nuestra puntuación): {score}"
    ),
    "col_a11y_check": "Comprobación",
    "col_a11y_impact": "Impacto",
    "col_a11y_also": "También indicado",
    "module_performance": "Velocidad / UX",
    "module_seo": "SEO básico",
    "module_ai_ready": "Preparación para la IA / LLMO",
    "module_llm_visibility": "Aptitud para ser citado",
    "module_tech": "Protección y analítica",
    "ev_pages_ok": "Páginas correctas",
    "ev_pages_failed": "Páginas con error",
    "ev_max_depth": "Profundidad máxima",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Páginas con JSON-LD",
    "ev_schema_types": "Tipos de schema.org",
    "ev_url_count": "URL en el sitemap",
    "ev_blocked_agents": "Rastreadores de IA bloqueados",
    "yes": "sí",
    "no": "no",
    "present": "presente",
    "absent": "ausente",
    "none": "ninguno",
    # ── Informe para el propietario ────────────────────────────────────────
    "owner_title": "Qué está pasando ahora con tu sitio web",
    "owner_score_caption": "puntuación global del sitio sobre 100",
    "owner_meaning_title": "En palabras simples",
    "owner_meaning_critical": (
        "Tu sitio apenas trabaja para ti ahora mismo. La gente que busca lo que vendes en "
        "general no te encuentra — acaba con la competencia. El aspecto del sitio no tiene "
        "nada que ver: el problema está en cosas que el visitante nunca ve pero Google sí. "
        "La buena noticia es que los sitios así son los que más rápido crecen: aquí casi "
        "cada arreglo se nota en los resultados."
    ),
    "owner_meaning_poor": (
        "El sitio funciona, pero una parte importante de los clientes no te llega. Es como "
        "una tienda en buena zona cuyo cartel solo se ve desde un lado de la calle: quien "
        "pasa por delante entra, y el resto nunca sabe que existes."
    ),
    "owner_meaning_medium": (
        "La base está bien puesta y el sitio te da de comer. Pero entre tú y la competencia "
        "ahora la diferencia está en detalles, y justo esos detalles deciden qué enlace ve "
        "primero la gente. Unos pocos arreglos puntuales aquí dan más que rehacer el sitio."
    ),
    "owner_meaning_good": (
        "El sitio está bien hecho — mejor que la mayoría. No necesitas rehacer nada, "
        "necesitas mantener la posición: la competencia también trabaja, y la ventaja se "
        "pierde sin ruido."
    ),
    "owner_meaning_unknown": (
        "Tu sitio no dejó entrar a nuestro programa, así que no obtuvimos la imagen "
        "completa. Suele ser protección contra visitantes indeseados — pero junto con ellos "
        "corta también a los buscadores. Conviene comprobarlo primero."
    ),
    "owner_meaning_empty": (
        "En tu dirección encontramos una página casi sin texto. Así se ve un sitio al que "
        "se le acabó el hosting o el dominio, o que nunca se llenó. Aquí aún no hay nada "
        "que evaluar — primero el sitio tiene que abrir."
    ),
    "owner_meaning_failures": (
        "La mayoría de las páginas de tu sitio no respondió. Leímos solo una pequeña parte, "
        "y una puntuación basada en eso sería un invento. Normalmente significa que el "
        "servidor está sobrecargado o parte del sitio está rota."
    ),
    "owner_areas_title": "Seis cosas por las que te evalúan",
    "owner_area_accessibility": "Si todos pueden usarlo",
    "owner_area_performance": "Si el sitio abre rápido",
    "owner_area_seo": "Si te encuentran en la búsqueda",
    "owner_area_ai_ready": "Si los programas entienden tu sitio",
    "owner_area_llm_visibility": "Si un asistente tiene algo que decir de ti",
    "owner_area_tech": "Si ves de dónde vienen los clientes",
    "owner_areas_note": (
        "Un guion significa que esa área no se pudo comprobar, no que todo esté mal ahí."
    ),
    "owner_problems_title": "Qué encontramos",
    "owner_problem_gravity": "Cuánta urgencia",
    "owner_problem_what": "Qué significa para ti",
    "owner_gravity_critical": "URGENTE",
    "owner_gravity_high": "IMPORTANTE",
    "owner_gravity_poor": "MERECE LA PENA",
    "owner_gravity_medium": "PUEDE ESPERAR",
    "owner_gravity_unknown": "A TENER EN CUENTA",
    "owner_problems_note": (
        "Esto es lo principal de {total} hallazgos. La lista completa con detalle técnico "
        "va en un documento aparte para tu desarrollador."
    ),
    "owner_gain_title": "Cuánto mejor podría estar",
    "owner_gain_now": "Ahora",
    "owner_gain_after": "Tras arreglar lo encontrado",
    "owner_gain_note": (
        "Una diferencia de {points} puntos. No es una previsión de ventas sino el estado "
        "del sitio: qué tan fácil les resulta a buscadores y personas encontrarte y "
        "entender para qué eres útil."
    ),
    "owner_next_title": "Qué sigue",
    "owner_next_body": (
        "Esta revisión la hicimos nosotros, solo con la dirección de tu sitio, y no te "
        "costó nada. Cada observación de arriba tiene una causa técnica concreta y una "
        "solución concreta — sabemos qué pasa y cuánto lleva arreglarlo. Te lo contamos en "
        "una reunión corta: por dónde empezaríamos, en qué orden y qué cambia tras cada "
        "paso. Una auditoría repetida en un mes muestra el resultado con las mismas cifras "
        "que esta."
    ),
    "owner_ai_view_title": "Cómo describe hoy tu sitio la inteligencia artificial",
    "owner_ai_view_note": (
        "No es nuestro resumen. Así entendió tu sitio el programa al que pregunta tu "
        "comprador cuando busca a quién encargarle el trabajo."
    ),
    "owner_enrich_failed": (
        "El documento no incluye explicaciones ampliadas de estos puntos: {reason}"
    ),
}

FR: dict[str, str] = {
    "doc_title": "Audit du site",
    "generated": "Généré",
    "status": "Statut",
    "pages_crawled": "Pages explorées",
    "overall": "Note globale",
    "of_100": "sur 100",
    "kind_general": "Rapport général",
    "kind_technical": "Rapport technique",
    "part1_title": "Partie 1. L'essentiel",
    "part1_subtitle": (
        "Pour le décideur : où en est le site et quoi corriger d'abord. Sans détail technique."
    ),
    "part2_title": "Partie 2. Analyse technique",
    "part2_subtitle": (
        "Pour le développeur ou le spécialiste SEO : chaque constat avec preuves et adresses."
    ),
    "verdict_critical": (
        "Le site a des problèmes systémiques : les moteurs de recherche et les services d'IA "
        "le voient bien moins bien qu'il ne le mérite. Plusieurs domaines demandent du travail "
        "à la fois."
    ),
    "verdict_poor": (
        "La base fonctionne, mais les lacunes suffisent à perdre une partie des visiteurs. La "
        "plupart se corrigent vite et sans refonte."
    ),
    "verdict_medium": (
        "Le site est en état de marche. Restent des améliorations ciblées qui ajoutent de la "
        "visibilité dans la recherche et les services d'IA."
    ),
    "verdict_good": (
        "Le site est en bon état. Les constats relèvent du polissage plus que du problème, et "
        "peuvent se traiter sans urgence."
    ),
    "verdict_unknown": (
        "Cette fois, nous n'avons pas pu noter le site : la plupart des vérifications sont "
        "restées sans données. Les raisons figurent plus bas, dans la section sur les "
        "données manquantes."
    ),
    "area_performance": "À quelle vitesse les pages s'ouvrent chez le visiteur.",
    "area_seo": "À quel point les moteurs de recherche comprennent le site.",
    "area_ai_ready": (
        "Si le site se décrit aux machines — là où les services d'IA prennent leurs faits."
    ),
    "area_llm_visibility": (
        "Si un assistant peut lire le site, savoir qui vous êtes et trouver quelque chose à "
        "citer. Qu'il vous cite réellement, nous ne le vérifions pas."
    ),
    "area_tech": (
        "Si le site est protégé des bots et si vous voyez ce que font les visiteurs."
    ),
    "area_accessibility": (
        "Si le site reste utilisable pour les personnes à vision ou motricité "
        "réduite, sur n'importe quel appareil."
    ),
    "col_area_meaning": "Ce que cela signifie",
    "col_completeness": "Complétude des données",
    "completeness_full": "complètes",
    "completeness_partial": "incomplètes",
    "section_priorities": "Quoi corriger d'abord",
    "section_scores": "Notes par domaine",
    "section_scores_technical": "Notes, poids et complétude des données",
    "section_missing_technical": "Lacunes dans les données",
    "section_missing": "Ce que nous n'avons pas pu mesurer",
    "section_details": "Analyse complète",
    "section_evidence": "Annexe : ce que nous avons vu sur le site",
    "col_module": "Domaine",
    "col_score": "Note",
    "col_band": "Niveau",
    "col_issues": "Constats",
    "col_weight": "Poids dans la globale",
    "col_parameter": "Paramètre",
    "col_value": "Valeur",
    "not_measured": "non mesuré",
    "missing_note_excluded": (
        "le module est exclu de la note globale ; son poids se répartit sur les autres"
    ),
    "missing_note_partial": (
        "la note repose sur un jeu incomplet de signaux — à lire comme une indication"
    ),
    "missing_note_incomplete": "la note du module repose sur des données incomplètes",
    "impact_note": (
        "L'effet de chaque point est mesuré séparément — de combien la note globale monte si "
        "l'on corrige précisément celui-là. Ces nombres ne s'additionnent pas."
    ),
    "effect": "Effet",
    "effort": "Effort",
    "pages_affected": "Pages",
    "site_wide": "tout le site",
    "problem": "Ce qui ne va pas",
    "what_to_do": "Quoi faire",
    "gives": "Ce que cela apporte",
    "no_priorities": "Aucune action urgente — aucun problème critique trouvé.",
    "part1_missing_intro": (
        "Une partie des signaux n'a pas pu être collectée cette fois, la note est donc "
        "incomplète :"
    ),
    "evidence": "Preuve",
    "examples": "Pages d'exemple",
    "and_more": "…et {count} de plus",
    "no_issues": "Aucun problème trouvé.",
    "module_not_scored": "Ce domaine n'a pas été noté — aucune donnée collectée.",
    "severity": "Criticité",
    "impact_floored": "le domaine est déjà au minimum, la note ne montera donc pas",
    "affects": "Affecte",
    "reason": "Raison",
    "band_critical": "critique",
    "band_poor": "faible",
    "band_medium": "moyen",
    "band_good": "bon",
    "band_unknown": "inconnu",
    "effort_low": "faible",
    "effort_medium": "moyen",
    "effort_high": "élevé",
    "severity_critical": "critique",
    "severity_high": "élevée",
    "severity_medium": "moyenne",
    "severity_low": "basse",
    "severity_info": "information",
    "module_accessibility": "Accessibilité",
    "section_passed": "Vérifications réussies : {count}",
    "passed_intro": (
        "Vérifications confirmées explicitement. Elles n'ajoutent aucun point et ne "
        "compensent aucun constat — trace de ce qui est déjà bien fait."
    ),
    "passed.seo.https": "Connexion HTTPS établie sans erreur TLS observée",
    "passed.seo.robots_txt": "robots.txt trouvé et lisible",
    "passed.seo.sitemap": "Plan du site trouvé ; URL déclarées : {declared}",
    "passed.tech.security_headers": (
        "Tous les en-têtes de protection surveillés détectés sur la réponse testée"
    ),
    "passed.tech.analytics": "Outil d'analyse détecté : {found}",
    "passed.tech.form_protection": (
        "Signes visibles de protection antispam des formulaires détectés "
        "({providers}) ; formulaires vérifiés : {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD détecté sur {pages} des {total} pages analysées",
    "passed.ai.llms_txt": "llms.txt présent (convention facultative)",
    "scores_weight_gap": (
        "Les poids de ce tableau totalisent {shown}. Les {hidden} restants proviennent toujours de "
        "l'accessibilité : elle ne reçoit plus de note, mais conserve pour l'instant sa "
        "contribution antérieure au score global. L'instantané figure plus bas."
    ),
    "a11y_still_weighted": (
        "L'accessibilité représente encore {percent} du score global — la contribution est "
        "inchangée par rapport à avant le passage à l'instantané. C'est temporaire : les poids "
        "sont réexaminés séparément."
    ),
    "a11y_not_weighted": (
        "L'accessibilité n'entre pas dans le score global de cet audit."
    ),
    "section_a11y_snapshot": "Accessibilité : instantané de la page testée",
    "a11y_scope": "Une page a été testée : {url} (affichage mobile).",
    "a11y_counts": (
        "Vérifications automatiques d'accessibilité applicables à cette page : {applicable}. "
        "Réussies : {passed}. Échouées : {failed}."
    ),
    "a11y_clean": (
        "Aucun problème d'accessibilité détectable automatiquement n'a été trouvé parmi les "
        "{applicable} vérifications applicables à cette page."
    ),
    "a11y_unavailable": (
        "L'accessibilité n'a pas été mesurée : l'outil externe n'a renvoyé aucune donnée pour "
        "cette page. Cela ne signifie pas qu'il n'y a pas de problèmes."
    ),
    "a11y_caveat": (
        "Il s'agit d'une vérification automatique d'une seule page. Ce n'est pas un avis de "
        "conformité aux WCAG et cela ne couvre pas l'ensemble du site. Certains obstacles ne "
        "peuvent pas être détectés automatiquement."
    ),
    "a11y_also_reported": "Également signalé sous « {module} »",
    "a11y_lighthouse_ref": (
        "Score d'accessibilité Lighthouse pour la page testée (référence externe, pas notre score) "
        ": {score}"
    ),
    "col_a11y_check": "Vérification",
    "col_a11y_impact": "Impact",
    "col_a11y_also": "Également signalé",
    "module_performance": "Vitesse / UX",
    "module_seo": "SEO de base",
    "module_ai_ready": "Préparation à l'IA / LLMO",
    "module_llm_visibility": "Aptitude à la citation",
    "module_tech": "Protection et mesure",
    "ev_pages_ok": "Pages réussies",
    "ev_pages_failed": "Pages en erreur",
    "ev_max_depth": "Profondeur maximale",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Pages avec JSON-LD",
    "ev_schema_types": "Types schema.org",
    "ev_url_count": "URL dans la sitemap",
    "ev_blocked_agents": "Robots d'IA bloqués",
    "yes": "oui",
    "no": "non",
    "present": "présent",
    "absent": "absent",
    "none": "aucun",
    # ── Rapport pour le propriétaire ───────────────────────────────────────
    "owner_title": "Ce qui se passe en ce moment avec votre site",
    "owner_score_caption": "note globale du site sur 100",
    "owner_meaning_title": "En termes simples",
    "owner_meaning_critical": (
        "Votre site ne travaille presque pas pour vous en ce moment. Les gens qui cherchent "
        "ce que vous vendez ne vous trouvent généralement pas — ils atterrissent chez vos "
        "concurrents. L'apparence du site n'y est pour rien : il s'agit de choses que le "
        "visiteur ne voit jamais mais que Google voit. La bonne nouvelle : ce sont "
        "précisément ces sites qui progressent le plus vite, car presque chaque correction "
        "se voit dans les résultats."
    ),
    "owner_meaning_poor": (
        "Le site fonctionne, mais une part importante de vos clients vous échappe. C'est "
        "comme une boutique bien placée dont l'enseigne ne se voit que d'un côté de la rue : "
        "qui passe devant entre, les autres ignorent que vous existez."
    ),
    "owner_meaning_medium": (
        "La base est saine et le site vous nourrit. Ce qui vous sépare des concurrents tient "
        "désormais à des détails — et ce sont eux qui décident quel lien une personne voit "
        "en premier. Quelques corrections ciblées valent ici mieux qu'une refonte."
    ),
    "owner_meaning_good": (
        "Le site est bien fait — mieux que la plupart. Vous n'avez pas besoin de refonte, "
        "mais de tenir la position : vos concurrents travaillent aussi, et un avantage se "
        "perd sans bruit."
    ),
    "owner_meaning_unknown": (
        "Votre site n'a pas laissé entrer notre programme, nous n'avons donc pas la vue "
        "complète. C'est le plus souvent une protection contre les visiteurs indésirables — "
        "qui coupe en même temps les moteurs de recherche. À vérifier en premier."
    ),
    "owner_meaning_empty": (
        "À votre adresse, nous avons trouvé une page presque sans texte. C'est l'aspect d'un "
        "site dont l'hébergement ou le domaine a expiré, ou qui n'a jamais été rempli. Rien "
        "à évaluer pour l'instant — il faut d'abord que le site s'ouvre."
    ),
    "owner_meaning_failures": (
        "La plupart des pages de votre site n'ont pas répondu. Nous n'en avons lu qu'une "
        "petite partie, et une note fondée dessus serait une invention. Le plus souvent, le "
        "serveur est surchargé ou une partie du site est cassée."
    ),
    "owner_areas_title": "Six choses sur lesquelles on vous juge",
    "owner_area_accessibility": "Si tout le monde peut l'utiliser",
    "owner_area_performance": "Si le site s'ouvre vite",
    "owner_area_seo": "Si l'on vous trouve dans la recherche",
    "owner_area_ai_ready": "Si les programmes comprennent votre site",
    "owner_area_llm_visibility": "Si un assistant a quelque chose à dire de vous",
    "owner_area_tech": "Si vous voyez d'où viennent les clients",
    "owner_areas_note": (
        "Un tiret signifie que ce domaine n'a pas pu être vérifié — pas que tout y va mal."
    ),
    "owner_problems_title": "Ce que nous avons trouvé",
    "owner_problem_gravity": "Quelle urgence",
    "owner_problem_what": "Ce que cela signifie pour vous",
    "owner_gravity_critical": "URGENT",
    "owner_gravity_high": "IMPORTANT",
    "owner_gravity_poor": "À FAIRE",
    "owner_gravity_medium": "PEUT ATTENDRE",
    "owner_gravity_unknown": "À NOTER",
    "owner_problems_note": (
        "Voici l'essentiel des {total} constats. La liste complète avec le détail technique "
        "figure dans un document séparé pour votre développeur."
    ),
    "owner_gain_title": "À quel point cela pourrait être mieux",
    "owner_gain_now": "Maintenant",
    "owner_gain_after": "Après correction des constats",
    "owner_gain_note": (
        "Une différence de {points} points. Ce n'est pas une prévision de ventes mais "
        "l'état du site : la facilité avec laquelle moteurs et personnes vous trouvent et "
        "comprennent à quoi vous êtes utile."
    ),
    "owner_next_title": "Et ensuite",
    "owner_next_body": (
        "Nous avons mené cette vérification nous-mêmes, à partir de votre seule adresse web, "
        "et elle ne vous a rien coûté. Chaque constat ci-dessus a une cause technique "
        "précise et une solution précise — nous savons de quoi il s'agit et combien de temps "
        "prend la correction. Nous vous l'expliquons lors d'un court échange : par où nous "
        "commencerions, dans quel ordre, et ce qui change après chaque étape. Un audit "
        "répété dans un mois montre le résultat avec les mêmes chiffres que celui-ci."
    ),
    "owner_ai_view_title": "Comment l'intelligence artificielle décrit votre site aujourd'hui",
    "owner_ai_view_note": (
        "Ce n'est pas notre résumé. C'est ainsi que votre site a été compris par le "
        "programme que votre client interroge quand il cherche à qui confier le travail."
    ),
    "owner_enrich_failed": (
        "Le document ne contient pas d'explications développées pour ces points : "
        "{reason}"
    ),
}

RU: dict[str, str] = {
    "doc_title": "Аудит сайта",
    "generated": "Сформировано",
    "status": "Статус",
    "pages_crawled": "Обойдено страниц",
    "overall": "Общая оценка",
    "of_100": "из 100",
    "kind_general": "Общий отчёт",
    "kind_technical": "Технический отчёт",
    "part1_title": "Часть 1. Коротко о главном",
    "part1_subtitle": (
        "Для руководителя: что с сайтом и что делать первым. Без технических деталей."
    ),
    "part2_title": "Часть 2. Технический разбор",
    "part2_subtitle": (
        "Для разработчика или SEO-специалиста: все находки с доказательствами и адресами."
    ),
    "verdict_critical": (
        "У сайта системные проблемы: поисковые системы и ИИ-сервисы видят его значительно "
        "хуже, чем он того заслуживает. Нужны изменения сразу в нескольких направлениях."
    ),
    "verdict_poor": (
        "Основа работает, но пробелов достаточно, чтобы терять часть посетителей. "
        "Большинство из них исправляется быстро и без переделки сайта."
    ),
    "verdict_medium": (
        "Сайт в рабочем состоянии. Остались точечные улучшения, которые добавят видимости "
        "в поиске и в ИИ-сервисах."
    ),
    "verdict_good": (
        "Сайт в хорошем состоянии. Найденное — скорее шлифовка, чем проблемы, и делать её "
        "можно без спешки."
    ),
    "verdict_unknown": (
        "В этот раз оценить сайт не удалось: большинство проверок остались без данных. "
        "Причины — ниже, в разделе о пробелах в данных."
    ),
    "area_performance": "Насколько быстро страницы открываются у посетителя.",
    "area_seo": "Насколько хорошо сайт понимают поисковые системы.",
    "area_ai_ready": (
        "Есть ли у сайта машинное описание себя — то, откуда ИИ-сервисы берут факты."
    ),
    "area_llm_visibility": (
        "Может ли ассистент прочитать сайт, понять, кто вы, и найти что процитировать. "
        "Цитирует ли на самом деле — мы не проверяем."
    ),
    "area_tech": (
        "Защищён ли сайт от ботов и видно ли вам, что делают посетители."
    ),
    "area_accessibility": (
        "Удобен ли сайт людям со слабым зрением или моторикой и на любом устройстве."
    ),
    "col_area_meaning": "Что это значит",
    "col_completeness": "Полнота данных",
    "completeness_full": "полные",
    "completeness_partial": "неполные",
    "section_priorities": "Что делать первым",
    "section_scores": "Оценки по направлениям",
    "section_scores_technical": "Оценки, веса и полнота данных",
    "section_missing_technical": "Пробелы в данных",
    "section_missing": "Чего мы не измерили",
    "section_details": "Полный разбор",
    "section_evidence": "Приложение: что мы увидели на сайте",
    "col_module": "Направление",
    "col_score": "Оценка",
    "col_band": "Уровень",
    "col_issues": "Находок",
    "col_weight": "Вес в общей",
    "col_parameter": "Параметр",
    "col_value": "Значение",
    "not_measured": "не измерялось",
    "missing_note_excluded": (
        "модуль исключён из общей оценки; его вес распределён между остальными"
    ),
    "missing_note_partial": (
        "оценка посчитана на неполном наборе сигналов — трактуйте как ориентир"
    ),
    "missing_note_incomplete": "оценка модуля посчитана на неполных данных",
    "impact_note": (
        "Эффект каждого пункта посчитан отдельно — насколько вырастет общая оценка, если "
        "исправить именно его. Эти числа нельзя складывать."
    ),
    "effect": "Эффект",
    "effort": "Сложность",
    "pages_affected": "Страниц",
    "site_wide": "весь сайт",
    "problem": "В чём проблема",
    "what_to_do": "Что сделать",
    "gives": "Что это даст",
    "no_priorities": "Срочных действий нет — критических проблем не найдено.",
    "part1_missing_intro": "Часть сигналов в этот раз собрать не удалось, поэтому оценка неполная:",
    "evidence": "Доказательство",
    "examples": "Примеры страниц",
    "and_more": "…ещё {count}",
    "no_issues": "Проблем не найдено.",
    "module_not_scored": "Направление не оценивалось — данных не получено.",
    "severity": "Критичность",
    "impact_floored": "оценка направления уже на минимуме, поэтому балл не вырастет",
    "affects": "Влияет на",
    "reason": "Причина",
    "band_critical": "критично",
    "band_poor": "слабо",
    "band_medium": "средне",
    "band_good": "хорошо",
    "band_unknown": "неизвестно",
    "effort_low": "низкая",
    "effort_medium": "средняя",
    "effort_high": "высокая",
    "severity_critical": "критическая",
    "severity_high": "высокая",
    "severity_medium": "средняя",
    "severity_low": "низкая",
    "severity_info": "информация",
    "module_accessibility": "Доступность",
    "section_passed": "Проверки пройдены: {count}",
    "passed_intro": (
        "Явно подтверждённые проверки. Они не добавляют баллов и не компенсируют находок "
        "— справка о том, что уже сделано хорошо."
    ),
    "passed.seo.https": "HTTPS-соединение прошло без обнаруженных ошибок TLS",
    "passed.seo.robots_txt": "robots.txt найден и читается",
    "passed.seo.sitemap": "Карта сайта найдена; объявленных адресов: {declared}",
    "passed.tech.security_headers": (
        "Все отслеживаемые защитные заголовки обнаружены на проверенном ответе"
    ),
    "passed.tech.analytics": "Система аналитики обнаружена: {found}",
    "passed.tech.form_protection": (
        "Видимые признаки защиты форм от автоматического спама обнаружены "
        "({providers}); форм проверено: {forms}"
    ),
    "passed.ai.jsonld": "JSON-LD обнаружен на {pages} из {total} проанализированных страниц",
    "passed.ai.llms_txt": "llms.txt присутствует (необязательная конвенция)",
    "scores_weight_gap": (
        "Веса в таблице дают {shown}. Остальные {hidden} по-прежнему даёт доступность: она больше "
        "не оценивается баллом, но свой прежний вклад в общую оценку пока сохраняет. Снимок "
        "доступности — ниже."
    ),
    "a11y_still_weighted": (
        "Доступность пока даёт {percent} общей оценки — вклад остался таким же, каким был до "
        "перехода на снимок. Это временно: веса направлений пересматриваются отдельно."
    ),
    "a11y_not_weighted": (
        "Доступность не входит в общую оценку этого аудита."
    ),
    "section_a11y_snapshot": "Доступность: снимок проверенной страницы",
    "a11y_scope": "Проверена одна страница: {url} (мобильный просмотр).",
    "a11y_counts": (
        "Автоматических проверок доступности, применимых к этой странице: {applicable}. Пройдено: "
        "{passed}. Не пройдено: {failed}."
    ),
    "a11y_clean": (
        "Автоматически обнаруживаемых проблем доступности не найдено среди {applicable} проверок, "
        "применимых к этой странице."
    ),
    "a11y_unavailable": (
        "Доступность не измерена: внешний инструмент не вернул данных для этой страницы. Это не "
        "значит, что проблем нет."
    ),
    "a11y_caveat": (
        "Это автоматическая проверка одной страницы. Она не является заключением о соответствии "
        "WCAG и не охватывает сайт целиком. Часть препятствий обнаружить автоматически невозможно."
    ),
    "a11y_also_reported": "Об этом сказано также в направлении «{module}»",
    "a11y_lighthouse_ref": (
        "Балл доступности Lighthouse для проверенной страницы (внешний ориентир, не наша оценка): "
        "{score}"
    ),
    "col_a11y_check": "Проверка",
    "col_a11y_impact": "Влияние",
    "col_a11y_also": "Где ещё сказано",
    "module_performance": "Скорость / UX",
    "module_seo": "Базовое SEO",
    "module_ai_ready": "Готовность к ИИ / LLMO",
    "module_llm_visibility": "Пригодность как источника",
    "module_tech": "Защита и аналитика",
    "ev_pages_ok": "Страниц успешно",
    "ev_pages_failed": "Страниц с ошибкой",
    "ev_max_depth": "Максимальная глубина",
    "ev_https": "HTTPS",
    "ev_hsts": "HSTS",
    "ev_robots": "robots.txt",
    "ev_sitemap": "sitemap.xml",
    "ev_llms": "llms.txt",
    "ev_jsonld": "Страниц с JSON-LD",
    "ev_schema_types": "Типы schema.org",
    "ev_url_count": "URL в карте",
    "ev_blocked_agents": "Заблокированные ИИ-роботы",
    "yes": "да",
    "no": "нет",
    "present": "есть",
    "absent": "нет",
    "none": "нет",
    # ── Отчёт для владельца ────────────────────────────────────────────────
    "owner_title": "Что сейчас происходит с вашим сайтом",
    "owner_score_caption": "общая оценка сайта из 100",
    "owner_meaning_title": "Простыми словами",
    "owner_meaning_critical": (
        "Ваш сайт сейчас почти не работает на вас. Люди, которые ищут то, что вы продаёте, "
        "в основном вас не находят — они попадают к конкурентам. Внешний вид сайта тут ни "
        "при чём: дело в вещах, которых посетитель не видит, а Google видит. Хорошая "
        "новость в том, что именно такие сайты растут быстрее всего: здесь почти каждое "
        "исправление даёт заметный результат."
    ),
    "owner_meaning_poor": (
        "Сайт у вас работает, но значительную часть клиентов вы не получаете. Это похоже "
        "на магазин в хорошем месте, вывеску которого видно только с одной стороны улицы: "
        "кто проходит мимо, тот зайдёт, а остальные даже не узнают, что вы есть."
    ),
    "owner_meaning_medium": (
        "Основа заложена нормально, и сайт вас кормит. Но между вами и конкурентами сейчас "
        "разница в мелочах, и именно эти мелочи решают, чью ссылку человек увидит первой. "
        "Несколько точечных исправлений дают здесь больше, чем полная переделка."
    ),
    "owner_meaning_good": (
        "Сайт сделан хорошо — лучше, чем у большинства. Вам не нужны переделки, нужно "
        "удержание позиций: конкуренты тоже работают, и преимущество теряется незаметно."
    ),
    "owner_meaning_unknown": (
        "Ваш сайт не пустил нашу программу внутрь, поэтому полной картины мы не получили. "
        "Чаще всего так настраивают защиту от нежелательных посетителей — но вместе с ними "
        "она отрезает и поисковые системы. Это стоит проверить первым."
    ),
    "owner_meaning_empty": (
        "По вашему адресу мы нашли страницу почти без текста. Так выглядит сайт, у "
        "которого закончился хостинг или домен, или который ещё не наполнили. Оценивать "
        "пока нечего — сначала сайт должен открываться."
    ),
    "owner_meaning_failures": (
        "Большинство страниц вашего сайта не ответили на запрос. Мы прочитали лишь малую "
        "часть, и оценка по ней была бы выдумкой. Чаще всего так бывает, когда сервер "
        "перегружен или часть сайта сломана."
    ),
    "owner_areas_title": "Шесть вещей, по которым вас оценивают",
    "owner_area_accessibility": "Могут ли пользоваться все",
    "owner_area_performance": "Быстро ли открывается сайт",
    "owner_area_seo": "Находят ли вас в поиске",
    "owner_area_ai_ready": "Понимают ли ваш сайт программы",
    "owner_area_llm_visibility": "Есть ли ассистенту что о вас сказать",
    "owner_area_tech": "Видно ли вам, откуда клиенты",
    "owner_areas_note": (
        "Прочерк означает, что это направление проверить не удалось, а не что там всё плохо."
    ),
    "owner_problems_title": "Что мы нашли",
    "owner_problem_gravity": "Насколько срочно",
    "owner_problem_what": "Что это значит для вас",
    "owner_gravity_critical": "СРОЧНО",
    "owner_gravity_high": "ВАЖНО",
    "owner_gravity_poor": "СТОИТ СДЕЛАТЬ",
    "owner_gravity_medium": "МОЖНО ПОЗЖЕ",
    "owner_gravity_unknown": "К СВЕДЕНИЮ",
    "owner_problems_note": (
        "Это главное из {total} найденных замечаний. Полный перечень с техническими "
        "подробностями — в отдельном документе для вашего разработчика."
    ),
    "owner_gain_title": "Насколько может быть лучше",
    "owner_gain_now": "Сейчас",
    "owner_gain_after": "После исправления найденного",
    "owner_gain_note": (
        "Разница в {points} баллов. Это не прогноз продаж, а состояние сайта: насколько "
        "легко поисковым системам и людям найти вас и понять, чем вы полезны."
    ),
    "owner_next_title": "Что дальше",
    "owner_next_body": (
        "Эту проверку мы сделали сами, по одному лишь адресу сайта, и она ничего вам не "
        "стоила. Каждое замечание выше имеет конкретную техническую причину и конкретное "
        "решение — мы знаем, в чём дело и сколько времени займёт исправление. Расскажем на "
        "короткой встрече: покажем, с чего начали бы, в каком порядке и что изменится "
        "после каждого шага. Повторный аудит через месяц покажет результат теми же "
        "цифрами, что и этот."
    ),
    "owner_ai_view_title": "Как искусственный интеллект описывает ваш сайт сегодня",
    "owner_ai_view_note": (
        "Это не наш пересказ. Так ваш сайт поняла программа, к которой обращается ваш "
        "покупатель, когда ищет, у кого заказать."
    ),
    "owner_enrich_failed": "Развёрнутых пояснений к этим пунктам в документе нет: {reason}",
}
