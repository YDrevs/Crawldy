"""Deutsche Formulierung der Befunde. Für den Kunden geschrieben, nicht Wort für Wort übersetzt.

Glossar der Sprache (konsistent mit der öffentlichen DE-Seite):
Befund — finding; Beleg — evidence; Abdeckung — coverage; Empfehlung —
recommendation; KI — nie «AI» als Primärbegriff; Suchmaschinen — search
engines. Anrede: Sie.
"""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    # ── SEO ─────────────────────────────────────────────────────────────────
    "seo.title.missing": {
        "title": "Fehlender <title>",
        "description": "Die Seite hat kein Title-Tag — kritisch für Suche und Sprachmodelle.",
        "recommendation": "Einen eindeutigen Titel mit 30–60 Zeichen und der Hauptsuchanfrage "
        "ergänzen.",
        "consequence": (
            "Die Seite hat keinen eigenen Titel. Suchmaschinen können die Überschrift für das "
            "Ergebnis selbst aus dem Seitentext bilden."
        ),
    },
    "seo.title.too_short": {
        "title": "Der Titel erklärt nichts ({length} Zeichen)",
        "description": (
            "Ein Titel unter {min} Zeichen kann nicht sagen, worum es auf der Seite geht."
        ),
        "recommendation": (
            "Ergänzen, wonach Menschen tatsächlich suchen: die Leistung, den Ort, den Nutzen."
        ),
        "consequence": (
            "Neben den Wettbewerbern in den Ergebnissen gibt so eine Überschrift keinen Grund, "
            "gerade Sie anzuklicken."
        ),
    },
    "seo.title.too_long": {
        "title": "Nur die ersten {visible} von {length} Zeichen werden angezeigt",
        "description": "Die Suche schneidet das Ende des Titels ab.",
        "recommendation": (
            "Das Wichtige nach vorn stellen — alles jenseits von {visible} Zeichen wird nicht "
            "angezeigt."
        ),
        "consequence": (
            "Das Ende der Überschrift sieht niemand — stand die Pointe dort, kommt sie nicht an."
        ),
    },
    "seo.title.duplicate": {
        "title": "Derselbe Titel auf {count} Seiten",
        "description": "Identische Titel machen Seiten im Index ununterscheidbar.",
        "recommendation": "Jeder Seite einen eigenen Titel geben.",
        "consequence": (
            "Für Suchmaschinen wie für Menschen sehen die Seiten identisch aus: schwer zu "
            "erkennen, welche man braucht."
        ),
    },
    "seo.meta_description.missing": {
        "title": "Fehlende Meta-Description",
        "description": "Ohne sie baut die Suche das Snippet aus einem zufälligen Textstück.",
        "recommendation": "Eine Beschreibung ergänzen, die in die sichtbaren ~{visible} Zeichen "
        "passt.",
        "consequence": (
            "Für diese Seite wurde keine Meta-Beschreibung erkannt. Suchmaschinen können "
            "das Snippet deshalb aus dem Seitentext erstellen."
        ),
    },
    "seo.h1.missing": {
        "title": "Kein h1 in der analysierten Ansicht",
        "description": (
            "Die analysierte Ansicht der Seite enthält keine HTML-Überschrift h1. Sind "
            "Überschriften niedrigerer Ebenen vorhanden, wird die erste davon in den Belegen "
            "gezeigt. Ein klares h1 ist eine empfohlene Praxis der Dokumentstruktur; für das "
            "Verstehen und Beschriften einer Seite ist es ein möglicher Hinweis unter mehreren "
            "Signalen, neben dem title und anderen."
        ),
        "recommendation": (
            "Erwägen Sie ein klares h1 mit dem Seitenthema — oft genügt es, die vorhandene erste "
            "Überschrift hochzustufen."
        ),
        "consequence": (
            "Die Hauptüberschrift der Seite ist im Code nicht als oberste markiert. Programme, "
            "die Struktur lesen, stützen sich auf andere Hinweise — den Tab-Titel und die "
            "Zwischenüberschriften."
        ),
    },
    "seo.h1.no_headings": {
        "title": "Keine HTML-Überschriften (h1–h6) gefunden",
        "description": (
            "Die analysierte Ansicht der Seite enthält keine nicht-leeren HTML-Überschriften "
            "h1–h6. Überschriften gliedern Inhalte für Leser und assistive Technologien; die "
            "Aussage betrifft ausdrücklich HTML-Überschriften — andere Auszeichnungswege wurden "
            "nicht bewertet."
        ),
        "recommendation": (
            "Ergänzen Sie eine klare, zur Seite passende Überschriftenstruktur: eine "
            "Hauptüberschrift und Zwischenüberschriften."
        ),
        "consequence": (
            "Die Seite hat keine markierte Abschnittsstruktur. Leser und Vorleseprogramme haben "
            "außer Fließtext nichts, woran sie sich halten können."
        ),
    },
    "seo.h1.multiple": {
        "title": "Mehrere h1-Elemente ({count}); Sichtbarkeit nicht bewertet",
        "description": (
            "Die analysierte Ansicht enthält {count} nicht-leere h1-Elemente. Ihre CSS- "
            "Sichtbarkeit wurde nicht bewertet: Ein Teil kann Vorlagen-Duplikate für verschiedene "
            "Layouts sein. Ein einzelnes klares h1 ist verbreitete gute Praxis, mehrere h1 sind "
            "jedoch zulässiges HTML, und diese Beobachtung allein belegt kein Suchproblem."
        ),
        "recommendation": (
            "Sind die Duplikate unbeabsichtigt, behalten Sie ein Haupt-h1 und stufen Sie die "
            "übrigen zu Zwischenüberschriften herab."
        ),
        "consequence": (
            "Die Hauptüberschrift ist mehrfach markiert. Das ist eine Beobachtung am Code der "
            "Seite, kein festgestellter Schaden."
        ),
    },
    "seo.heading_hierarchy": {
        "title": "Überschriftensprung H{previous} → H{level}",
        "description": "Eine übersprungene Ebene macht die Struktur maschinell schwerer lesbar.",
        "recommendation": "Keine Überschriftenebenen überspringen.",
        "consequence": (
            "Die Seitenstruktur wirkt auf die lesende Software unlogisch, und der Text lässt "
            "sich schlechter in sinnvolle Blöcke teilen."
        ),
    },
    "seo.canonical.missing": {
        "title": "Kein rel=canonical",
        "description": "",
        "recommendation": "Jeder indexierbaren Seite eine selbstreferenzierende Canonical geben.",
        "consequence": (
            "Ist dieselbe Seite unter mehreren Adressen erreichbar, kann die Suche sie als "
            "verschiedene Seiten behandeln und das Ranking-Gewicht aufteilen."
        ),
    },
    "seo.canonical.mismatch": {
        "title": "Canonical zeigt auf eine andere Seite",
        "description": "Das nimmt die Seite aus dem Index — prüfen Sie, ob das beabsichtigt ist.",
        "recommendation": "Prüfen, ob die Canonical nicht versehentlich auf die Startseite zeigt.",
        "consequence": (
            "Die Seite erklärt den Suchmaschinen, nicht die Hauptversion zu sein, und kann "
            "damit ganz aus den Ergebnissen verschwinden."
        ),
    },
    "seo.noindex": {
        "title": "Die Seite ist für die Suche gesperrt",
        "description": (
            "Das Markup weist Suchmaschinen an, diese Seite nicht zu zeigen. Oft ist das "
            "Absicht — bezahlte Landingpages, Veranstaltungsarchive, Seiten für internen "
            "Traffic. Wir sehen die Anweisung, aber nicht die Absicht — prüfen Sie, ob sie "
            "hierher gehört."
        ),
        "recommendation": (
            "Soll die Seite Menschen aus der Suche bringen, entfernen Sie die Anweisung. "
            "Ist sie mit Absicht gesperrt, lassen Sie alles wie es ist."
        ),
        "consequence": (
            "Solange die Anweisung steht, bringt diese Seite keine Besucher aus der Suche. "
            "Ist das gewollt, ist alles in Ordnung; wenn nicht, verpufft die Arbeit, die in "
            "ihr steckt."
        ),
    },
    "seo.render_delta.indexing": {
        "title": "Indexierungssignale unterscheiden sich nach JavaScript: {fields}",
        "description": (
            "Serverantwort und Seite nach Skriptausführung sind sich uneinig darüber, welche URL "
            "indexiert werden soll. Beide Werte stehen im Nachweis. Google rendert JavaScript, "
            "doch die Dokumentation nennt eine Warteschlange, die \"can take longer\" als "
            "Sekunden dauert, und hält fest: \"not all bots can run JavaScript\" — ein Crawler "
            "kann also der Antwortversion folgen."
        ),
        "recommendation": (
            "Prüfen Sie, welcher der beiden Werte gemeint ist, und liefern Sie diesen bereits im "
            "HTML der Antwort aus, statt ihn per Skript zu setzen."
        ),
        "consequence": (
            "Für dieselbe Seite existieren zwei Anweisungen, und welche gilt, hängt davon ab, ob "
            "das besuchende System Skripte ausführt."
        ),
    },
    "seo.render_delta.identity": {
        "title": "Die Selbstbeschreibung der Seite ändert sich nach JavaScript: {fields}",
        "description": (
            "Überschrift oder der in Suchergebnissen gezeigte Text sind vor und nach der "
            "Skriptausführung verschieden. Beide Werte stehen im Nachweis. Ein System ohne "
            "JavaScript sieht nur die Antwortversion."
        ),
        "recommendation": (
            "Legen Sie endgültige Überschrift und Beschreibung in das vom Server gelieferte HTML; "
            "Skripte sollen die Seite ergänzen, nicht definieren."
        ),
        "consequence": (
            "Manche Systeme beschreiben Ihre Seite so, andere anders — der Name, den Menschen "
            "sehen, ist nicht immer der von Ihnen geschriebene."
        ),
    },
    "seo.render_delta.markup": {
        "title": "Strukturierte Daten unterscheiden sich nach JavaScript",
        "description": (
            "Die maschinenlesbare Auszeichnung der Seite ist vor und nach der Skriptausführung "
            "nicht gleich: Typen oder Bezeichner erscheinen, verschwinden oder ändern sich. Beide "
            "Mengen stehen im Nachweis."
        ),
        "recommendation": (
            "Geben Sie die Auszeichnung in der Serverantwort aus. Was erst nach Skripten "
            "erscheint, lesen nur Systeme, die Skripte ausführen."
        ),
        "consequence": (
            "Die Fakten, die Sie über Ihr Unternehmen veröffentlichen, sind für manche Systeme "
            "sichtbar und für andere nicht."
        ),
    },
    "seo.render_delta.links": {
        "title": "{count} interne Links existieren erst nach JavaScript",
        "description": (
            "Diese Links fehlen in der Serverantwort und erscheinen nur in der gerenderten Seite. "
            "Der Nachweis listet sie auf. Google folgt Links, die es nach dem Rendern findet, "
            "hält aber selbst fest, dass nicht alle Bots JavaScript ausführen."
        ),
        "recommendation": (
            "Liefern Sie diese Links als gewöhnliche Anker im HTML aus. Skripte dürfen die "
            "Navigation darüber hinaus verbessern."
        ),
        "consequence": (
            "Teile der Website sind nur für Systeme erreichbar, die Skripte ausführen; für alle "
            "anderen sind diese Seiten von hier nicht verlinkt."
        ),
    },
    "seo.robots_txt.missing": {
        "title": "robots.txt fehlt",
        "description": "Crawler bekommen keine Anweisungen und keinen Verweis auf Ihre Sitemap.",
        "recommendation": "/robots.txt mit einer Sitemap-Direktive anlegen.",
        "consequence": (
            "Suchmaschinen kommen ohne Anweisungen an und wissen nicht, wo Ihre Sitemap liegt."
        ),
    },
    "seo.robots_txt.disallow_all": {
        "title": "robots.txt sperrt die gesamte Website",
        "description": "`Disallow: /` für `User-agent: *` blockiert jedes Crawling.",
        "recommendation": "Disallow: / entfernen, wenn die Website in der Suche stehen soll.",
        "consequence": (
            "robots.txt verbietet das Crawlen der gesamten Website. Suchmaschinen lesen die "
            "Seiten nicht; eine Adresse kann dennoch in den Ergebnissen auftauchen, aber ohne "
            "Beschreibung und ohne Inhalt."
        ),
    },
    "seo.robots_txt.no_sitemap": {
        "title": "robots.txt ohne Sitemap-Direktive",
        "description": "",
        "recommendation": "Eine Zeile `Sitemap: https://.../sitemap.xml` ergänzen.",
        "consequence": (
            "Suchmaschinen bekommen keinen Hinweis, wo Ihre Seitenliste liegt, und entdecken "
            "Seiten langsamer."
        ),
    },
    "seo.sitemap.missing": {
        "title": "sitemap.xml nicht gefunden",
        "description": "",
        "recommendation": "Eine XML-Sitemap erzeugen und aus robots.txt darauf verweisen.",
        "consequence": (
            "Keine Sitemap gefunden: An den Standardadressen ist keine vorhanden, und die Website "
            "hat keine andere Adresse angegeben."
        ),
    },
    "seo.sitemap.invalid": {
        "title": "sitemap.xml lässt sich nicht parsen",
        "description": "",
        "recommendation": "Das XML reparieren — eine ungültige Sitemap ignorieren Crawler.",
        "consequence": (
            "Die Sitemap existiert, lässt sich aber nicht lesen: Die Datei ist kein gültiges "
            "XML. Sie nützt nichts, solange das Format nicht korrigiert ist."
        ),
    },
    "seo.sitemap.empty": {
        "title": "sitemap.xml ist leer",
        "description": "",
        "recommendation": "Die URLs Ihrer Seiten in die Sitemap eintragen.",
        "consequence": "Die Sitemap enthält keine Adressen und erfüllt ihre Aufgabe nicht.",
    },
    "seo.sitemap.coverage": {
        "title": "{count} gecrawlte Seiten fehlen in der Sitemap",
        "description": "",
        "recommendation": "Die Sitemap-Erzeugung mit der realen Seitenstruktur synchron halten.",
        "consequence": (
            "Ein Teil der Seiten fehlt in der Sitemap, sodass die Suche später oder gar nicht "
            "von ihnen erfährt."
        ),
    },
    "seo.broken_links": {
        "title": "{count} interne URLs liefern einen Fehler",
        "description": (
            "Wir sind diesen Links selbst gefolgt, und der Server antwortete mit einem Fehler. "
            "Der Nachweis führt jedes defekte Ziel auf, dazu die Seiten, die darauf verlinken, "
            "den Linktext und ob der Link in der Serverantwort stand oder erst nach den "
            "Skripten erschien. Ein Ziel ohne Quellseiten war auf keiner gelesenen Seite "
            "verlinkt — es stammt aus der Sitemap."
        ),
        "recommendation": (
            "Arbeiten Sie mit dem Nachweis: Er nennt zu jedem Ziel die Seiten, die darauf "
            "zeigen. Ändern Sie diese Links auf eine funktionierende Adresse oder entfernen Sie "
            "sie. Verweisen mehrere Seiten auf dieselbe tote Adresse, steht der Link meist in "
            "einer gemeinsamen Vorlage."
        ),
        "consequence": "Besucher landen auf kaputten Seiten — verlorene Besuche und ein "
        "schlechter Eindruck.",
    },
    "seo.https.missing": {
        "title": "Website läuft nicht über HTTPS",
        "description": "HTTP-Websites werden als unsicher markiert und ranken schlechter.",
        "recommendation": "TLS aktivieren und HTTP per 301 auf HTTPS umleiten.",
        "consequence": (
            "Browser markieren die Website als unsicher und zeigen eine Warnung noch vor dem "
            "Inhalt. Was ein Besucher mit dieser Warnung macht, messen wir nicht."
        ),
    },
    "seo.https.invalid_cert": {
        "title": "Das HTTPS-Zertifikat ist ungültig",
        "description": (
            "Die Website lädt nur mit abgeschalteter Zertifikatsprüfung. Übliche Ursachen sind "
            "eine unvollständige Zwischenkette, ein selbstsigniertes oder ein abgelaufenes "
            "Zertifikat. Such-Crawler überspringen Websites in diesem Zustand."
        ),
        "recommendation": (
            "Das Zertifikat neu ausstellen und mit vollständiger Zwischenkette ausliefern. Das "
            "Ergebnis auf ssllabs.com/ssltest prüfen — die Note sollte A sein."
        ),
        "consequence": (
            "Statt Ihrer Website sehen Besucher eine rote Warnseite mit einem Knopf «Zurück zur "
            "Sicherheit». Fast alle drücken ihn."
        ),
    },
    "seo.https.no_hsts": {
        "title": "Kein HSTS-Header",
        "description": "",
        "recommendation": "`Strict-Transport-Security: max-age=31536000` ergänzen.",
        "consequence": (
            "Der erste Besuch kann über eine ungeschützte Verbindung laufen — eine kleine, aber "
            "reale Sicherheitslücke."
        ),
    },
    "seo.image_alt": {
        "title": "{without_alt} von {total} Bildern ohne Alt-Text",
        "description": "Alt-Text ist Barrierefreiheit und zugleich ein Textsignal für Modelle.",
        "recommendation": "Den Bildinhalt beschreiben; alt=\"\" nur für Dekoratives lassen.",
        "consequence": (
            "Blinde Besucher erfahren nichts über das Bild: Ein Screenreader nimmt die "
            "Beschreibung genau aus diesem Attribut. Text, der nur im Bild steht, gehört nicht "
            "zum Seiteninhalt."
        ),
    },
    "seo.thin_content": {
        "title": "Nur {word_count} Wörter auf der Seite",
        "description": (
            "Wenig Text ist ein schwaches Signal für Suche wie für Zitate durch Sprachmodelle. "
            "Es kann auch bedeuten, dass der Inhalt clientseitig gerendert wird."
        ),
        "recommendation": "Den Haupttext auf {threshold}+ Wörter ausbauen oder SSR prüfen.",
        "consequence": (
            "Zu wenig Text, als dass die Seite als nützlich gälte: sie rankt schwach, und zu "
            "zitieren gibt es fast nichts."
        ),
    },
    "seo.click_depth": {
        "title": "Wenige Links von dieser Seite weiter: {internal_links}",
        "description": (
            "Diese Seite verlinkt auf {internal_links} andere Seiten der Website. Gezählt "
            "werden die Links auf dieser Seite; über die Zahl der Seiten, die AUF sie "
            "verweisen, sagt das nichts — eine Seite, auf die das ganze Menü zeigt, kann "
            "selbst ins Leere führen."
        ),
        "recommendation": (
            "Verlinken Sie von hier auf das, was Lesende als Nächstes suchen: verwandte "
            "Leistungen, die passende Kategorie, das Projektbeispiel dazu."
        ),
        "consequence": (
            "Wer hier landet, kann kaum weitergehen und verlässt die Website, statt sich "
            "Ihr Angebot weiter anzusehen."
        ),
    },
    "cro.no_action": {
        "title": "Auf dieser Seite gibt es nichts zu tun",
        "description": (
            "Eine Seite, die etwas anbietet, hat kein Formular, keine klickbare Telefonnummer "
            "oder E-Mail und keinen Link zu Bestellung, Warenkorb oder Kontakt. Wen die Seite "
            "überzeugt hat, der kann damit nichts anfangen."
        ),
        "recommendation": (
            "Der Seite einen offensichtlichen nächsten Schritt geben und ihn nach dem "
            "Haupttext wiederholen: einen Bestellknopf, ein Anfrageformular oder die "
            "Telefonnummer als Link. Ein klarer Schritt wirkt besser als drei."
        ),
        "consequence": (
            "Diese Seite bietet außerhalb von Menü und Fußzeile keine Aktion: kein Formular, "
            "keine Schaltfläche, keinen Kontakt im Text selbst. Wer zu Ende gelesen hat und "
            "Kontakt aufnehmen möchte, muss selbst suchen."
        ),
    },
    "cro.phone_not_tappable": {
        "title": "Die Telefonnummer steht da, lässt sich aber nicht wählen",
        "description": (
            "Die Nummer erscheint auf der Website, ist aber nirgends als Wähl-Link "
            "ausgezeichnet. Am Telefon muss der Besucher sie sich merken, die Website "
            "verlassen und von Hand eintippen. Seiten, auf denen wir das sahen: {count}."
        ),
        "recommendation": (
            "Die Nummer überall als tel:+…-Link auszeichnen — Kopfzeile, Fußzeile und "
            "Kontaktseite. Eine halbe Stunde Arbeit."
        ),
        "consequence": (
            "Die meisten Besucher kommen mit dem Telefon. Statt zum Anruf zu tippen, müssen "
            "sie die Nummer abschreiben — und ein Teil tut es schlicht nicht."
        ),
    },
    "seo.topic_islands": {
        "title": "{count} Seiten zu einem Thema verlinken einander nie",
        "description": (
            "Wir haben {count} Seiten zum selben Gebiet gelesen, und keine erwähnt eine "
            "andere. Der einzige Weg von einer zur nächsten ist das Menü oder eine "
            "Übersichtsseite — die inhaltlichen Verbindungen, die zeigen, dass das Thema "
            "durchgearbeitet wurde, fehlen."
        ),
        "recommendation": (
            "Fügen Sie kontextuelle Links ZWISCHEN WIRKLICH VERWANDTEN Seiten ein, wo sie dem "
            "Leser tatsächlich helfen: von einer Fallstudie zu einer benachbarten, von einem "
            "Artikel zum Folgebeitrag. Es ist nicht nötig, jede Seite des Bereichs mit jeder "
            "anderen zu verlinken — ein Link, der nur eine Regel erfüllt, hilft weder Mensch noch "
            "Suchmaschine."
        ),
        "consequence": (
            "Die Seiten stärken einander nicht. Wer eine von ihnen liest, bekommt die "
            "nächste, die er braucht, nie gezeigt, und die Website liest sich als Stapel "
            "loser Blätter statt als Beleg, dass die Firma ihr Fach kennt."
        ),
    },
    "seo.orphan_pages": {
        "title": "Auf {count} Seiten aus der Sitemap zeigt kein einziger Link",
        "description": (
            "Die Sitemap nennt diese Seiten, aber nichts auf der Website führt zu ihnen. "
            "Suchmaschinen können sie finden; ein Besucher nie, und ihr Stand ruht allein "
            "auf der Sitemap — dem schwächsten Signal, das eine Website senden kann."
        ),
        "recommendation": (
            "Diese Seiten von dort verlinken, wo sie hingehören: aus dem Menü, ihrer "
            "Kategorie oder dem Fließtext verwandter Seiten. Ist eine Seite nicht für "
            "Besucher gedacht, nehmen Sie sie stattdessen aus der Sitemap."
        ),
        "consequence": (
            "Diese Seiten existieren, aber von der Website selbst führt kein Weg zu ihnen. "
            "Besucher sehen sie nie, und die Arbeit, die in ihnen steckt, ist vergeben."
        ),
    },
    "seo.links_to_noindex": {
        "title": "{count} Seiten sind verlinkt, aber vor der Suche verborgen",
        "description": (
            "Die Website nimmt eine Seite in ihre Navigation auf und verbietet Suchmaschinen "
            "zugleich, sie zu zeigen. Eines von beidem ist falsch: Entweder ist die Seite "
            "für Menschen wichtig und sollte sichtbar sein, oder sie ist intern und gehört "
            "nicht ins Menü."
        ),
        "recommendation": (
            "Für jede Seite entscheiden, welches von beidem sie ist. Ist sie wichtig, das "
            "Indexierungsverbot entfernen; ist sie intern, den Link aus der Navigation nehmen."
        ),
        "consequence": (
            "Ein Besucher folgt einem Link auf eine Seite, die Suchmaschinen verbergen "
            "sollen. Die Website widerspricht sich selbst, und ein Teil des Wegs zum Kauf "
            "führt ins Leere."
        ),
    },
    "seo.viewport": {
        "title": "Kein Meta-Viewport",
        "description": "Ohne Viewport passt sich die Seite mobilen Bildschirmen nicht an.",
        "recommendation": (
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> ergänzen."
        ),
        "consequence": (
            "Am Telefon erscheint die Seite als geschrumpftes Desktop-Layout — unbequem zu "
            "lesen, und Google bezieht das ein."
        ),
    },
    "seo.sitemap.lastmod": {
        "title": "Sitemap ohne Änderungsdaten",
        "description": "",
        "recommendation": "Jeder URL ein lastmod geben und es bei Änderungen aktualisieren.",
        "consequence": (
            "Nach einer Aktualisierung trägt die Karte kein Zeichen davon, was sich geändert "
            "hat — es gibt darin nichts, woran man eine neue Seite von einer alten "
            "unterscheiden könnte."
        ),
    },
    "seo.clean_url.uppercase": {
        "title": "Großbuchstaben in der Seiten-URL",
        "description": (
            "URLs unterscheiden Groß- und Kleinschreibung: /Services und /services sind "
            "technisch verschiedene Seiten."
        ),
        "recommendation": "Den Pfad kleinschreiben und vom alten Wert per 301 umleiten.",
        "consequence": (
            "Die Suche kann Schreibvarianten als verschiedene Seiten behandeln und ihr Gewicht "
            "aufteilen."
        ),
    },
    "seo.clean_url.underscore": {
        "title": "Unterstriche in der Seiten-URL",
        "description": "",
        "recommendation": "Unterstriche durch Bindestriche ersetzen und per 301 umleiten.",
        "consequence": (
            "Die Wörter in der Adresse fließen zusammen, und die Suche versteht das "
            "Seitenthema schlechter."
        ),
    },
    "seo.clean_url.query": {
        "title": "Query-Parameter in der Seiten-URL",
        "description": (
            "Derselbe Inhalt, über verschiedene Parameter erreichbar, wirkt wie mehrere Seiten."
        ),
        "recommendation": "Auf saubere Pfade wechseln oder Parameter per Canonical bündeln.",
        "consequence": (
            "Derselbe Inhalt ist unter mehreren Adressen erreichbar. Suchmaschinen können sie "
            "als verschiedene Seiten behandeln und die Signale auf sie aufteilen."
        ),
    },
    # ── KI-Bereitschaft / LLMO ──────────────────────────────────────────────
    "ai.llms_txt.missing": {
        "title": "Kein llms.txt (optionale Möglichkeit)",
        "description": (
            "llms.txt ist eine Markdown-Datei im Stammverzeichnis, die die Website kurz für KI- "
            "Agenten beschreibt: worum es geht, wichtige Bereiche, Links zu den Hauptseiten. Es "
            "ist eine junge Konvention mit wachsender Verbreitung, aber weiterhin ein Vorschlag "
            "und kein Standard: Die Datei ist optional und experimentell, und ihr Fehlen ist "
            "weder ein bekanntes Ranking-Problem noch eine Voraussetzung für Sichtbarkeit in "
            "Sprachmodellen. Ihr Fehlen hindert KI-Systeme nicht daran, die Website zu erreichen "
            "oder zu zitieren."
        ),
        "recommendation": (
            "Vor allem dann eine Überlegung wert, wenn die Website Dokumentation, Referenzen oder "
            "anderen strukturierten Inhalt hat. Legen Sie /llms.txt an: eine H1 mit dem "
            "Produktnamen, eine kurze Beschreibung und `##`-Abschnitte mit Links zu den "
            "wichtigsten Seiten. Garantien gibt es keine — weder Crawling noch Zitate noch "
            "Platzierungen."
        ),
        "consequence": (
            "Dienste wie ChatGPT oder Perplexity bilden sich ihr Bild der Website aus dem, was "
            "sie selbst finden. Die Datei kann das erleichtern — ihr Fehlen nimmt der Website "
            "aber weder Zugang noch Zitate."
        ),
    },
    "ai.llms_txt.no_h1": {
        "title": "llms.txt ohne H1",
        "description": "",
        "recommendation": (
            "Die erste Zeile sollte `# Projektname` sein. Die Datei selbst bleibt eine "
            "experimentelle Option, keine Anforderung."
        ),
        "consequence": (
            "Die Datei llms.txt beginnt ohne Namen, obwohl die Spezifikation ihn in der ersten "
            "Zeile verlangt. Wer die Datei liest, sieht nicht, zu welchem Produkt sie gehört."
        ),
    },
    "ai.llms_txt.thin": {
        "title": "llms.txt ist zu dünn",
        "description": "Die Datei existiert, gibt dem Modell aber keine Karte der Website.",
        "recommendation": (
            "`##`-Abschnitte und 5+ Links auf Schlüsselseiten ergänzen. Die Datei selbst bleibt "
            "eine experimentelle Option, keine Anforderung."
        ),
        "consequence": (
            "Die Zusammenfassungsdatei existiert, zeigt dem Modell aber nicht, woraus die "
            "Website besteht — sie bringt wenig."
        ),
    },
    "ai.jsonld.missing": {
        "title": "Keine strukturierten Daten in den Serverantworten erkannt",
        "description": (
            "In den analysierten Serverantworten wurde weder JSON-LD noch Microdata erkannt; RDFa "
            "wurde nicht bewertet. Schema.org-Auszeichnung ist optional: Sie gibt Maschinen "
            "explizite Hinweise auf die Bedeutung der Seite und macht Rich-Ergebnisse möglich, "
            "garantiert sie aber nicht und ist keine Voraussetzung für Sichtbarkeit in KI- "
            "Diensten."
        ),
        "recommendation": (
            "Falls Sie Auszeichnung ergänzen möchten, beginnen Sie mit JSON-LD auf der "
            "Startseite: Google empfiehlt dieses Format als das wartungsfreundlichste."
        ),
        "consequence": (
            "Maschinen bilden ihr Bild der Seite allein aus dem Text. Explizite Hinweise könnten "
            "das erleichtern — ihr Fehlen kostet die Website aber weder Suchpräsenz noch "
            "Erwähnungen."
        ),
    },
    "ai.jsonld.invalid": {
        "title": "Ungültiges JSON-LD",
        "description": "Der ld+json-Block lässt sich nicht parsen — das Markup wird komplett "
        "ignoriert.",
        "recommendation": "Die JSON-Syntax im application/ld+json-Script reparieren.",
        "consequence": (
            "Die maschinenlesbare Beschreibung der Seite lässt sich nicht lesen — die Mühe, "
            "sie zu ergänzen, war umsonst."
        ),
    },
    "ai.jsonld.no_type": {
        "title": "JSON-LD ohne @type",
        "description": "",
        "recommendation": "Jede Entität braucht einen @type aus schema.org.",
        "consequence": (
            "Die Daten der Seite sind unbeschriftet — Software sieht Werte, weiß aber nicht, "
            "was sie bedeuten."
        ),
    },
    "ai.schema.organization": {
        "title": "Keine Organisations- oder Personen-Entität in der Auszeichnung",
        "description": (
            "Strukturierte Daten sind vorhanden, aber auf der Startseite und den Über-uns-Seiten "
            "der Stichprobe wurde keine Identitätsentität beobachtet: weder Organization noch "
            "einer seiner Untertypen, Person oder WebSite. Eine solche Entität ist optional und "
            "hat keine Pflichteigenschaften."
        ),
        "recommendation": (
            "Für ein Unternehmen, eine Einrichtung oder eine persönliche Marke lohnt sich der "
            "passende Organization-Untertyp oder Person/WebSite auf der Start- oder Über-uns- "
            "Seite. Ergänzen Sie nur die Eigenschaften, die auf Sie zutreffen."
        ),
        "consequence": (
            "Es gibt keine explizite maschinenlesbare Karte, wer hinter der Website steht — "
            "Maschinen leiten das aus dem Text ab. Das ist eine Verbesserungsmöglichkeit, kein "
            "Defekt."
        ),
    },
    "ai.entity.sameas": {
        "title": "Kein sameAs (Entitätssignale)",
        "description": (
            "sameAs verknüpft Ihre Marke mit externen Wissensbasen (Wikidata, LinkedIn, "
            "GitHub, Crunchbase) — das primäre Identitätssignal."
        ),
        "recommendation": "sameAs mit Links auf die offiziellen Profile der Marke ergänzen.",
        "consequence": (
            "Es gibt keine Bestätigung, dass dies dieselbe Marke wie auf Wikipedia oder "
            "LinkedIn ist, und Modelle sind bei Ihren Daten weniger sicher."
        ),
    },
    "ai.schema.breadcrumb": {
        "title": "Keine BreadcrumbList",
        "description": "Breadcrumbs zeigen dem Modell, wo eine Seite in der Hierarchie sitzt.",
        "recommendation": "BreadcrumbList auf Unterseiten ergänzen.",
        "consequence": (
            "Unklar, zu welchem Bereich der Website die Seite gehört — Kontext geht verloren."
        ),
    },
    "ai.schema.faq": {
        "title": "{count} Fragen auf der Seite ohne FAQPage-Markup",
        "description": (
            "Überschriften sind als Fragen formuliert, doch FAQPage- oder QAPage-Markup fehlt. "
            "Frage-Antwort-Paare sind das Format, das Sprachmodelle am besten verarbeiten: "
            "ausgezeichnet lassen sie sich am Stück übernehmen und zitieren."
        ),
        "recommendation": (
            "Die vorhandenen Frage-Antwort-Paare in FAQPage-Markup fassen. Nichts muss neu "
            "geschrieben werden — der Inhalt ist da, nur das Markup fehlt."
        ),
        "consequence": (
            "Die Antworten stehen bereits auf der Seite, aber in einer Form, die nichts "
            "erkennt — also zitieren Modelle den Wettbewerber, der dasselbe ausgezeichnet hat."
        ),
    },
    "ai.schema.content_type": {
        "title": "Inhaltsseite ohne Article-/Product-Markup",
        "description": "",
        "recommendation": (
            "Je nach Seitentyp Article (headline, author, datePublished, dateModified) oder "
            "Product ergänzen."
        ),
        "consequence": (
            "Eine gehaltvolle Seite ist weder als Artikel noch als Produkt ausgezeichnet und "
            "erscheint nicht in den erweiterten Suchergebnissen."
        ),
    },
    "ai.opengraph": {
        "title": "Fehlende OG-Tags: {missing}",
        "description": "",
        "recommendation": "OpenGraph ausfüllen — soziale Netzwerke wie KI-Crawler lesen es.",
        "consequence": (
            "In Messengern und sozialen Netzwerken geteilte Links auf Ihre Website haben kein "
            "richtiges Bild und keine Beschreibung."
        ),
    },
    "ai.lang": {
        "title": "Seitensprache nicht deklariert",
        "description": "Das lang-Attribut hilft, den Text korrekt zu deuten und zu indexieren.",
        "recommendation": "<html lang=\"de\"> ergänzen (oder den passenden Sprachcode).",
        "consequence": (
            "Die Seitensprache ist nicht deklariert, sodass die Seite dem falschen Publikum "
            "gezeigt oder zur Übersetzung angeboten werden kann."
        ),
    },
    "ai.opengraph.no_image": {
        "title": "Kein og:image",
        "description": "",
        "recommendation": "Ein Bild 1200×630 im Meta-Tag og:image ergänzen.",
        "consequence": (
            "Links auf Ihre Website erscheinen in Messengern und sozialen Netzwerken als "
            "leeres Rechteck, und weniger Menschen klicken sie."
        ),
    },
    "ai.schema.contact.missing": {
        "title": "Kein LocalBusiness-/ContactPoint-Markup",
        "description": (
            "Für ein lokales Geschäft ist das der wichtigste Weg, einer Maschine Adresse, "
            "Telefon und Öffnungszeiten zu übergeben."
        ),
        "recommendation": (
            "JSON-LD LocalBusiness mit address, telephone, openingHoursSpecification und geo "
            "ergänzen."
        ),
        "consequence": (
            "Kontaktdaten stehen auf der Website, sind aber nicht als strukturierte "
            "Unternehmensdaten ausgezeichnet."
        ),
    },
    "ai.schema.contact.incomplete": {
        "title": "LocalBusiness ohne die Felder: {missing}",
        "description": "",
        "recommendation": "Das Markup vervollständigen — diese Felder speisen Suchkarten und "
        "KI-Antworten.",
        "consequence": (
            "Ihre Visitenkarte in der Suche bleibt unvollständig: Ein Teil der Daten hat "
            "schlicht keine Quelle."
        ),
    },
    "ai.schema.graph": {
        "title": "JSON-LD-Blöcke sind nicht miteinander verknüpft",
        "description": "Mehrere getrennte Blöcke ohne @id lesen sich als beziehungslose Entitäten.",
        "recommendation": (
            "Jedem Block eine @id geben und sie blockübergreifend referenzieren, sodass ein "
            "Graph entsteht."
        ),
        "consequence": (
            "Eine Maschine sieht verstreute Datenfragmente statt eines zusammenhängenden Bilds "
            "der Firma."
        ),
    },
    "ai.twitter_card": {
        "title": "Keine Twitter/X-Card",
        "description": "",
        "recommendation": (
            "<meta name=\"twitter:card\" content=\"summary_large_image\"> plus "
            "twitter:title/description/image ergänzen."
        ),
        "consequence": (
            "Auf X und in mehreren Messengern erscheint Ihr Link ohne Bild und Beschreibung."
        ),
    },
    # ── Zitierfähigkeit ─────────────────────────────────────────────────────
    "llm.direct_answer": {
        "title": "Veraltete Prüfung: Struktur des Seitenanfangs",
        "description": (
            "Eine frühere Crawldy-Version markierte die Struktur des Textes am Seitenanfang. "
            "Diese Heuristik wurde inzwischen zurückgezogen, weil sie Navigation, Zeichensetzung "
            "und Seitenlayout mit Inhaltsqualität verwechseln konnte. In neuen Prüfungen und in "
            "der Bewertung wird sie nicht mehr verwendet."
        ),
        "recommendation": (
            "Allein auf Grundlage dieses veralteten Eintrags ist nichts zu tun. Beurteilen Sie "
            "die Verständlichkeit der Seite für Besucher anhand der aktuellen Befunde und Belege "
            "des Berichts."
        ),
        "consequence": (
            "Dieser Eintrag stammt aus einer früheren Prüfversion und beeinflusst neue Ergebnisse "
            "nicht."
        ),
    },
    "llm.structure": {
        "title": "Langer Text ({word_count} Wörter) ohne Zwischenüberschriften",
        "description": "Eine massive Textwand lässt sich schwerer in zitierbare Stücke teilen.",
        "recommendation": "Den Inhalt in H2-/H3-Abschnitte teilen; Listen und Tabellen ergänzen.",
        "consequence": (
            "Eine massive Textwand: für Menschen schwer zu lesen, und für ein Modell schwer, "
            "ein kurzes Fragment herauszulösen."
        ),
    },
    "llm.about_page": {
        "title": "Keine Über-uns-Seite",
        "description": (
            "Die Über-uns-Seite ist die Hauptquelle, aus der ein Modell sein Bild der "
            "Organisation und ihrer Autorität formt."
        ),
        "recommendation": "/about anlegen und Firma, Geschichte und Team beschreiben.",
        "consequence": (
            "Unter den gelesenen Seiten hat keine eine Adresse, einen Titel oder einen "
            "Linktext, der wie eine „Über uns“-Seite aussieht."
        ),
    },
    "llm.contact_page": {
        "title": "Keine Kontaktseite",
        "description": (
            "Kontaktdaten sind ein grundlegendes Vertrauenssignal (E-E-A-T) für Suche und "
            "Modelle."
        ),
        "recommendation": "/contact mit Adresse, E-Mail und ContactPoint-Markup ergänzen.",
        "consequence": (
            "Ohne sichtbare Kontaktdaten wirkt die Website auf Besucher wie auf Suchmaschinen "
            "weniger vertrauenswürdig."
        ),
    },
    "llm.brand_consistency": {
        "title": "Der Markenname ist uneinheitlich",
        "description": (
            "Der Name im JSON-LD taucht im Titel der Startseite nicht auf — ein Modell "
            "verbindet die Website womöglich nicht mit der Marke."
        ),
        "recommendation": "In title, H1 und schema.org identische Markenschreibweise verwenden.",
        "consequence": (
            "Der Markenname ist an verschiedenen Stellen verschieden geschrieben, was die "
            "Zuordnung zu Ihnen erschwert."
        ),
    },
    "llm.stale_content": {
        "title": "Seit {years} Jahren wurde nichts auf der Website aktualisiert",
        "description": (
            "Keine der datierten Seiten, die wir lasen, wurde in {years} Jahren angefasst. "
            "Es geht nicht um eine einzelne Seite — ein Leitfaden kann jahrelang stimmen —, "
            "sondern um die Website als Ganzes."
        ),
        "recommendation": (
            "Die Hauptseiten durchgehen und auffrischen, was gealtert ist: Preise, "
            "Leistungsumfang, jüngste Arbeiten. Das Aktualisierungsdatum ins Seiten-Markup "
            "schreiben, sonst erfährt niemand von der Änderung."
        ),
        "consequence": (
            "Das neueste Datum, das wir auf der Website gefunden haben, liegt Jahre zurück. Ein "
            "Leser kann nicht erkennen, ob die Informationen noch gelten."
        ),
    },
    "llm.stale_content.sparse": {
        "title": "Das neueste datierte Material stammt von vor {years} Jahren",
        "description": (
            "Daten stehen nur auf {dated} von {read} gelesenen Seiten. Dies ist also eine Aussage "
            "über die gefundenen Daten, nicht über die gesamte Website. Eine Seite ohne Datum ist "
            "keine alte Seite: Viele Websites geben keines an."
        ),
        "recommendation": (
            "Wenn die Inhalte tatsächlich aktualisiert wurden, tragen Sie das "
            "Aktualisierungsdatum in die Auszeichnung ein — ohne es gibt es kein Datum zu "
            "lesen. Wenn nicht, beginnen Sie mit den meistgelesenen Seiten."
        ),
        "consequence": (
            "Wenn die einzigen sichtbaren Daten Jahre zurückliegen, nimmt der Leser "
            "an, die Website werde nicht mehr gepflegt — auch wenn das nicht stimmt."
        ),
    },
    "llm.authorship": {
        "title": "Inhaltsseite ohne author/datePublished",
        "description": "Autorschaft und Daten sind Signale für Frische und Glaubwürdigkeit.",
        "recommendation": "author, datePublished und dateModified ins Article-Markup ergänzen.",
        "consequence": (
            "Es ist nicht zu sehen, wer das wann geschrieben hat, und das Material liest sich "
            "weniger verlässlich."
        ),
    },
    "llm.crawler_blocked.search": {
        "title": "{count} KI-Suchcrawler sind blockiert: {crawlers}",
        "description": (
            "Diese Crawler indexieren Seiten, damit ein Assistent sie finden und zitieren kann. "
            "robots.txt verwehrt ihnen derzeit die im Nachweis genannten Seiten. Es geht um "
            "Zugriff, nicht darum, ob ein Assistent Sie erwähnt — das messen wir nicht."
        ),
        "recommendation": (
            "War die Sperre nicht beabsichtigt, erlauben Sie diese User-Agents in robots.txt. "
            "Halten Sie sie getrennt von Trainings-Crawlern: Suchzugriff erlauben und Training "
            "weiterhin ablehnen ist möglich."
        ),
        "consequence": (
            "Die Assistenten, die Menschen fragen, können diese Seiten nicht öffnen — das kann "
            "Ihre Chancen verringern, als Quelle genannt zu werden."
        ),
    },
    "llm.crawler_blocked.grounding": {
        "title": "{count} KI-Grounding-Crawler sind blockiert: {crawlers}",
        "description": (
            "Diese Tokens steuern, ob Inhalte, die der Anbieter von Ihrer Website erfasst, für "
            "Grounding — also zur Übergabe an das Modell zum Zeitpunkt der Anfrage — in den "
            "eigenen KI-Produkten dieses Anbieters verwendet werden dürfen. Google-Extended "
            "betrifft Gemini Apps und Vertex AI. robots.txt verwehrt ihnen die im Nachweis "
            "genannten Seiten. Google betont, dass dieses Token weder Aufnahme noch Ranking in "
            "der Google-Suche beeinflusst — es ist also kein Suchproblem."
        ),
        "recommendation": (
            "War die Sperre nicht beabsichtigt, erlauben Sie diese User-Agents. Beachten Sie: "
            "dasselbe Token steuert auch das Modelltraining, eine Erlaubnis gilt also für beides; "
            "in robots.txt lassen sie sich derzeit nicht trennen."
        ),
        "consequence": (
            "Von diesen Seiten erfasste Inhalte werden möglicherweise nicht als Quelle "
            "herangezogen, wenn Gemini eine Frage beantwortet. Über andere Assistenten sagt das "
            "nichts aus, und Ihre Position in der normalen Google-Suche bleibt unberührt."
        ),
    },
    "llm.crawler_blocked.user": {
        "title": "{count} Assistenz-Abrufe sind blockiert: {crawlers}",
        "description": (
            "Diese Agenten rufen eine Seite ab, wenn eine Person einen Assistenten ausdrücklich "
            "danach fragt. robots.txt verwehrt ihnen die im Nachweis genannten Seiten."
        ),
        "recommendation": (
            "War das nicht beabsichtigt, erlauben Sie diese User-Agents. Sie handeln auf direkte "
            "Anfrage einer Person; die Sperre trifft vor allem jemanden, der Ihre Seite ohnehin "
            "lesen wollte."
        ),
        "consequence": (
            "Ihre Website verbietet diesen Agenten. Bittet ein Besucher den Assistenten, Ihre "
            "Seite anzusehen, darf dieser sie also nicht abrufen. Was der Assistent stattdessen "
            "antwortet, beobachten wir nicht."
        ),
    },
    "llm.crawler_blocked.training": {
        "title": "{count} KI-Trainingscrawler sind blockiert: {crawlers}",
        "description": (
            "Diese Crawler sammeln Material für das Modelltraining. Blockiert sind hier nur sie — "
            "Such- und Assistenzzugriff bleiben unberührt. Training abzulehnen ist eine legitime "
            "Entscheidung über eigene Inhalte; der Eintrag steht hier, damit es eine Entscheidung "
            "bleibt und kein Versehen wird."
        ),
        "recommendation": (
            "War es beabsichtigt, ist nichts zu tun. Andernfalls erlauben Sie diese User-Agents; "
            "sie steuern ausschließlich den Trainingszugriff."
        ),
        "consequence": (
            "Ihre Texte bleiben aus dem Modelltraining heraus. Das ist eine Entscheidung über "
            "Ihre Inhalte, kein Mangel der Website."
        ),
    },
    "llm.client_rendered": {
        "title": "Der Inhalt wird offenbar clientseitig gerendert",
        "description": (
            "Das statische HTML enthält trotz viel Markup fast keinen Text. Die meisten "
            "KI-Crawler führen kein JavaScript aus und sehen eine leere Seite."
        ),
        "recommendation": "SSR/SSG oder Prerendering für die Schlüsselseiten aktivieren.",
        "consequence": (
            "In der eigenen Antwort des Servers ist die Seite fast leer: Der Text erscheint "
            "erst, nachdem Skripte ausgeführt wurden. Ein Leser, der sie nicht ausführt, sieht "
            "die leere Fassung."
        ),
    },
    # ── Geschwindigkeit ─────────────────────────────────────────────────────
    "perf.core_web_vitals.lcp": {
        "title": "LCP = {value}{unit} ({strategy})",
        "description": (
            "Largest Contentful Paint — Zeit bis zum Rendern des Hauptelements. Die Schwelle "
            "für «gut» liegt bei {threshold}{unit}."
        ),
        "recommendation": (
            "Das Hero-Bild optimieren (preload, modernes Format) und render-blockierendes "
            "CSS/JS entfernen."
        ),
        "consequence": (
            "Der Hauptinhalt der Seite lädt zu langsam. Besucher müssen länger warten und "
            "verlassen die Website möglicherweise, bevor der Inhalt vollständig geladen ist."
        ),
    },
    "perf.core_web_vitals.inp": {
        "title": "INP = {value}{unit} ({strategy})",
        "description": (
            "Interaction to Next Paint — Reaktionsverzögerung auf eine Nutzeraktion. Die "
            "Schwelle für «gut» liegt bei {threshold}{unit}."
        ),
        "recommendation": "Lange JS-Aufgaben zerlegen und den Umfang der Hydration verringern.",
        "consequence": (
            "Die Seite stockt spürbar nach Klicks — sie fühlt sich träge an."
        ),
    },
    "perf.core_web_vitals.cls": {
        "title": "CLS = {value}{unit} ({strategy})",
        "description": (
            "Cumulative Layout Shift — visuelle Instabilität beim Laden. Die Schwelle für "
            "«gut» liegt bei {threshold}{unit}."
        ),
        "recommendation": "width/height an Bildern setzen und Platz für Banner und Schriften "
        "reservieren.",
        "consequence": (
            "Während Bilder und Schriften laden, verschiebt sich der Text vor den Augen, und "
            "die Seite lässt sich unangenehm lesen."
        ),
    },
    "perf.core_web_vitals.ttfb": {
        "title": "TTFB = {value}{unit} ({strategy})",
        "description": (
            "Time To First Byte — Antwortzeit des Servers. Die Schwelle für «gut» liegt bei "
            "{threshold}{unit}."
        ),
        "recommendation": "Caching/CDN aktivieren und Datenbankabfragen optimieren.",
        "consequence": (
            "Der Server antwortet zu langsam und verzögert dadurch das Laden der Seite."
        ),
    },
    "perf.core_web_vitals.tbt": {
        "title": "TBT = {value}{unit} ({strategy})",
        "description": (
            "Total Blocking Time — Blockade des Hauptthreads. Die Schwelle für «gut» liegt "
            "bei {threshold}{unit}."
        ),
        "recommendation": "Menge und Gewicht des JavaScripts verringern.",
        "consequence": (
            "Die Seite sieht geladen aus, reagiert aber noch nicht auf Eingaben — der "
            "ärgerlichste Zustand für einen Besucher."
        ),
    },
    "perf.mobile_gap": {
        "title": "Am Telefon ist die Website doppelt so langsam wie am Computer",
        "description": (
            "Wir haben die Website zweimal gemessen: wie ein Computer sie sieht und wie ein "
            "Telefon. Am Computer erreicht sie {desktop} von 100, am Telefon {mobile}. Google "
            "rankt nach der Mobilversion, und die meisten Menschen kommen auch mit dem Telefon."
        ),
        "recommendation": (
            "Die Belege unten vergleichen: Dort stehen die Metriken, die mobil mehr als "
            "doppelt so schlecht sind. Übliche Ursachen sind schwere Bilder und die Menge an "
            "JavaScript, an der ein Telefon weit länger arbeitet als ein Desktop."
        ),
        "consequence": (
            "Sie sehen Ihre Website am Computer an, und alles wirkt gut. Ihre Kunden sehen "
            "sie am Telefon und sehen etwas anderes — und ein Teil von ihnen wartet nicht."
        ),
    },
    "perf.server_response.slow": {
        "title": "Der Server antwortet langsam ({median} ms)",
        "description": (
            "Medianzeit bis zum ersten Byte über die gecrawlten Seiten. Die Schwelle für «gut» "
            "liegt bei {threshold} ms. Das ist Verzögerung, bevor der Browser irgendetwas "
            "zeichnen kann."
        ),
        "recommendation": (
            "Server- oder CDN-Caching aktivieren und nach langsamen Datenbankabfragen suchen."
        ),
        "consequence": "Jeder Besucher wartet vor einem leeren Bildschirm, bevor etwas erscheint.",
    },
    "perf.server_response.very_slow": {
        "title": "Der Server antwortet sehr langsam ({median} ms)",
        "description": (
            "Medianzeit bis zum ersten Byte über die gecrawlten Seiten, gegen eine "
            "«gut»-Schwelle von {threshold} ms. Bei dieser Latenz leidet jede andere Metrik: "
            "Der Browser wartet schlicht."
        ),
        "recommendation": (
            "Das ist der erste Engpass, den es zu beheben gilt. Die Seitengenerierung auf dem "
            "Server profilieren, dann Caching und ein CDN ergänzen."
        ),
        "consequence": (
            "Der Server antwortet zu langsam und verzögert dadurch das Laden der Seite."
        ),
    },
    "perf.lighthouse_score": {
        "title": "Lighthouse-Performance {score} ({strategy})",
        "description": "Ein Wert unter 90 bedeutet spürbare Geschwindigkeitsprobleme.",
        "recommendation": "Mit den obersten Punkten im Opportunities-Block beginnen.",
        "consequence": (
            "Die Gesamtnote für Geschwindigkeit ist niedrig — auf einer langsamen Verbindung "
            "wird die Website schwer benutzbar sein."
        ),
    },
    "perf.unavailable": {
        "title": "Geschwindigkeitsdaten nicht erhoben",
        "description": "Der Anbieter lieferte keine Metriken — das Geschwindigkeitsmodul wurde "
        "nicht bewertet.",
        "recommendation": "PSI_API_KEY oder die Verfügbarkeit des Lighthouse-Sidecars prüfen.",
        "consequence": (
            "Die Geschwindigkeit wurde diesmal nicht gemessen, die Bewertung ist also "
            "unvollständig. Das ist kein Problem der Website."
        ),
    },
    "perf.render_blocking": {
        "title": "{count} render-blockierende Ressourcen im <head>",
        "description": "Synchrone Skripte und CSS verzögern das erste Rendern.",
        "recommendation": "Skripten async/defer geben und das kritische CSS inline stellen.",
        "consequence": (
            "Ihr Besucher starrt mehrere Sekunden auf einen leeren Bildschirm, bevor etwas "
            "erscheint."
        ),
    },
    "perf.images.legacy_format": {
        "title": "{count} Bilder ließen sich in einem leichteren Format ausliefern",
        "description": (
            "JPG und PNG sind nicht veraltet und funktionieren überall — aber dieselben Bilder "
            "wiegen als WebP oder AVIF meist deutlich weniger. Der Gewinn hängt von der Datei ab."
        ),
        "recommendation": (
            "WebP/AVIF über <picture> ausliefern, mit Fallback auf das aktuelle Format."
        ),
        "consequence": (
            "Die Seite lädt langsamer als nötig — am deutlichsten am Telefon und auf langsamer "
            "Verbindung."
        ),
    },
    "perf.images.no_dimensions": {
        "title": "{count} Bilder ohne width/height",
        "description": (
            "Ohne Abmessungen reserviert der Browser keinen Platz — ein direkter CLS-Preis."
        ),
        "recommendation": "Jedem <img> width und height (oder aspect-ratio) geben.",
        "consequence": (
            "Während Bilder laden, springt der Text umher und wird unbequem zu lesen."
        ),
    },
    "perf.images.no_lazy": {
        "title": "Kein Lazy Loading trotz vieler Bilder",
        "description": "",
        "recommendation": "Bildern unterhalb des sichtbaren Bereichs loading=\"lazy\" geben.",
        "consequence": (
            "Der Browser lädt alle Bilder auf einmal, auch die, zu denen der Besucher womöglich "
            "nie scrollt."
        ),
    },
    "perf.external_fonts": {
        "title": "Schriften laden von fremden Hosts: {hosts}",
        "description": (
            "Ein externer Schrift-Host fügt dem kritischen Rendering-Pfad eine Verbindung hinzu."
        ),
        "recommendation": (
            "Die Schriften selbst hosten und per @font-face mit font-display: swap laden."
        ),
        "consequence": (
            "Der Browser wartet auf einen fremden Server, bevor er Text zeigt — die Seite "
            "bleibt länger leer."
        ),
    },
    "perf.third_party": {
        "title": "{count} Dritt-Hosts auf der Startseite",
        "description": (
            "Jeder externe Host bedeutet eine eigene Verbindung, einen DNS-Lookup und fremden "
            "Code."
        ),
        "recommendation": (
            "Entfernen, was der Conversion nicht dient: überzählige Widgets, Tracker, "
            "Chat-Tools."
        ),
        "consequence": (
            "Die Website hängt von Geschwindigkeit und Verfügbarkeit fremder Server ab, von "
            "denen jeder sie bremsen kann."
        ),
    },
    "perf.third_party.weight": {
        "title": "Fremdcode macht {share} der Seite aus ({kb} KB)",
        "description": (
            "Wir haben die Seite in einem echten Browser geöffnet und alles gewogen, was sie "
            "lädt. {share} des Gesamtgewichts kommen von fremden Domains — Widgets, Chats, "
            "Tracker, Werbung. Jedes davon muss ankommen, bevor die Seite voll benutzbar ist."
        ),
        "recommendation": (
            "Die schwersten Domains aus den Belegen durchgehen. Alles, was oberhalb der "
            "Falz nicht gebraucht wird, nachladen — und streichen, was niemand nutzt."
        ),
        "consequence": (
            "Die Geschwindigkeit Ihrer Website hängt von den Servern anderer Firmen ab. Haben "
            "die einen schlechten Tag, haben ihn Ihre Besucher auch — und Sie können nichts "
            "dagegen tun."
        ),
    },
    "perf.page_weight": {
        "title": "Die Seite wiegt {megabytes} MB noch vor allen Bildern",
        "description": (
            "Das ist allein das Markup, ohne Bilder und Skripte: {words} Wörter in einem "
            "einzigen Dokument. Eine gewöhnliche Seite hat Dutzende bis Hunderte Kilobyte. "
            "Übliche Ursachen sind Kommentar-Spam, ein in die Seite gekippter Katalog oder "
            "Spuren eines Einbruchs."
        ),
        "recommendation": (
            "Nachsehen, was den Platz belegt: die Seite öffnen und nach Text suchen, den Sie "
            "nie hinzugefügt haben. Sind es Kommentare, abschalten oder moderieren; sind es "
            "fremde Links und Kauderwelsch, die Website auf Kompromittierung prüfen und die "
            "Passwörter ändern."
        ),
        "consequence": (
            "Eine Seite dieses Gewichts lädt selbst bei guter Verbindung lange und öffnet sich "
            "auf dem Telefon möglicherweise gar nicht."
        ),
    },
    "perf.page_weight.truncated": {
        "title": "Die Seite ist zu groß, um sie ganz zu lesen: mindestens {megabytes} MB",
        "description": (
            "Das Markup überschritt die Grenze, bis zu der wir lesen, sodass {words} Wörter "
            "nicht einmal alles sind. Ein Dokument dieser Größe ist nie Zufall: meist "
            "Kommentar-Spam, ein gekippter Katalog oder die Folgen eines Einbruchs. Alles "
            "Weitere über diese Seite bezieht sich auf den gelesenen Teil."
        ),
        "recommendation": (
            "Die Seite von Hand prüfen: öffnen und sehen, woher die Masse kommt. Fremde Links "
            "oder Text, den Sie nicht geschrieben haben, bedeuten eine wahrscheinliche "
            "Kompromittierung — Passwörter ändern und die Website prüfen lassen. Spam-Kommentare "
            "aus der Datenbank entfernen, nicht nur ausblenden."
        ),
        "consequence": (
            "Wer mit dem Telefon kommt, gibt höchstwahrscheinlich auf, bevor sie lädt. Auch "
            "Suchmaschinen lesen sie nur teilweise — und das Gelesene kann sich als fremder "
            "Text statt Ihres eigenen erweisen."
        ),
    },
    "perf.responsive_images": {
        "title": "{count} Bilder ohne responsive Größen",
        "description": "",
        "recommendation": "srcset und sizes ergänzen, damit Telefone eine kleinere Version laden.",
        "consequence": (
            "Telefone laden Fotos in derselben Größe wie Desktops: Die Seite öffnet langsamer "
            "und verbraucht das Datenvolumen des Besuchers."
        ),
    },
    # ── Schutz und Analytik ─────────────────────────────────────────────────
    "tech.security_headers.none": {
        "title": "Keine Browser-Schutz-Header auf der geprüften Antwort erkannt",
        "description": (
            "Keiner der geprüften Schutz-Header ({headers}) ist auf der Antwort vorhanden. Es "
            "sind zusätzliche Schutzmechanismen; ihr Fehlen ist für sich genommen kein Hinweis "
            "auf einen Sicherheitsvorfall, bedeutet aber meist, dass die Konfiguration noch nicht "
            "angegangen wurde."
        ),
        "recommendation": (
            "Besprechen Sie mit dem Entwickler, welche dieser Mechanismen zur Anwendung passen. "
            "Üblicher Einstieg ist X-Content-Type-Options: nosniff — am verträglichsten für die "
            "Kompatibilität."
        ),
        "consequence": (
            "Browserseitige Schutzmechanismen für Besucher sind gar nicht konfiguriert. Die "
            "Website ist deshalb nicht defekt — ihr fehlt aber die Reserve, die diese Mechanismen "
            "kostenlos bieten."
        ),
    },
    "tech.security_headers.missing": {
        "title": "{count} optionale Browser-Schutzmechanismen nicht erkannt",
        "description": (
            "Auf der geprüften Antwort nicht erkannt: {headers}. Das sind zusätzliche "
            "browserseitige Schutzmechanismen für Besucher. Ihr Fehlen ist für sich genommen kein "
            "Hinweis auf einen Sicherheitsvorfall und keine direkte Voraussetzung für Such- oder "
            "KI-Sichtbarkeit."
        ),
        "recommendation": (
            "Prüfen Sie die Konfiguration mit dem Entwickler der Website: Welche Header sinnvoll "
            "sind, hängt von der Anwendung ab, und blindes Aktivieren kann funktionierende Seiten "
            "beschädigen."
        ),
        "consequence": (
            "Ein Teil der üblichen Browser-Schutzmechanismen für Besucher ist nicht aktiviert. "
            "Das ist fehlende Reserve, kein Einbruch: Die Website ist dadurch weder "
            "kompromittiert noch verliert sie Leser."
        ),
    },
    "tech.crawler_blocked": {
        "title": "Die Website antwortet Robots mit Status {status} statt einer Seite",
        "description": (
            "Unser Agent erhielt {status} und sah keine Seite mit Inhalt. Bot-Schutz behandelt "
            "GPTBot, ClaudeBot und PerplexityBot oft genauso: Auch ihre Anfragen kommen aus "
            "einem unbekannten Browser. Google wird dabei möglicherweise durchgelassen — es "
            "wird separat erkannt. Wir haben einen Agenten getestet, unseren eigenen; wie die "
            "Website den anderen antwortet, haben wir nicht geprüft."
        ),
        "recommendation": (
            "In den Schutzeinstellungen (Cloudflare, WAF, fail2ban) Such- und KI-Crawler über "
            "ihre User-Agents und IP-Bereiche zulassen. Das Ergebnis mit der URL-Prüfung in "
            "der Search Console verifizieren."
        ),
        "consequence": (
            "Die Website hat unser Programm nicht eingelassen: keine einzige Seite konnte "
            "gelesen werden. Dieselben Einstellungen stoppen oft auch die Bots von KI-Diensten; "
            "ob diese Website sie blockiert, haben wir jedoch nicht geprüft — der Rest des "
            "Berichts stützt sich nur auf das, was von außen zu sehen war."
        ),
    },
    "tech.analytics.missing": {
        "title": "Auf der Website wurde kein Analysesystem erkannt",
        "description": (
            "Wir haben die Seite in einem echten Browser geöffnet und ihr gesamtes JavaScript "
            "ausgeführt. Kein Zähler erschien — kein Google Analytics oder GTM, kein "
            "Plausible, Matomo, Segment oder PostHog, und auch kein eigenes Mess-Skript."
        ),
        "recommendation": (
            "Google Analytics 4 installieren und die Website in der Search Console "
            "verifizieren. Beides ist kostenlos und in etwa einer Stunde eingerichtet."
        ),
        "consequence": (
            "Auf den gelesenen Seiten wurde kein Analyse-Skript erkannt."
        ),
    },
    "tech.analytics.unconfirmed": {
        "title": "Kein Analytik-Tag im Quelltext gefunden",
        "description": (
            "Das HTML enthält kein Google Analytics oder GTM und keine Alternative. Wir haben "
            "allerdings ohne JavaScript geschaut, und manche Tags werden erst danach "
            "eingefügt — so eines hätten wir nicht gesehen."
        ),
        "recommendation": (
            "Prüfen, ob wirklich ein Tag installiert ist, etwa in den Berichten des "
            "Analytik-Tools selbst. Wenn nicht, Google Analytics 4 ergänzen."
        ),
        "consequence": (
            "Misst nichts die Besuche, wissen Sie weder, wie viele Menschen kommen, noch was "
            "sie tun — Verbesserungen haben keine Grundlage."
        ),
    },
    "tech.form_protection.unprotected": {
        "title": "Veralteter Check: kein sichtbarer Schutzmarker im Formular gefunden",
        "description": (
            "Eintrag eines früheren Audits: Im Formular wurde kein clientseitig sichtbarer "
            "Anti-Missbrauch-Marker erkannt. Serverseitige und unsichtbare Mechanismen "
            "bewertete jener Check nicht; dieser Eintrag allein ist kein Beleg, dass das "
            "Formular ungeschützt war."
        ),
        "recommendation": (
            "Allein auf Grundlage dieses Alteintrags ist nichts zu tun. Beurteilen Sie die "
            "Formulare nach den aktuellen Befunden des Berichts."
        ),
        "consequence": (
            "Dieser Eintrag stammt aus einer älteren Audit-Version und beeinflusst neue "
            "Ergebnisse nicht."
        ),
    },
    "tech.form_protection.no_visible_marker": {
        "title": (
            "Im Formular wurde kein sichtbarer Schutz vor Bots erkannt."
        ),
        "description": (
            "Weder im ursprünglichen HTML noch im gerenderten Formular wurde sichtbarer Schutz "
            "gefunden. Serverseitiger Schutz kann dennoch vorhanden sein und lässt sich mit "
            "dieser passiven Prüfung nicht bestätigen."
        ),
        "recommendation": (
            "Wenn unerwünschte automatische Übermittlungen tatsächlich ein Problem oder ein "
            "wesentliches Risiko sind, klären Sie mit dem Entwickler oder Anbieter, welche "
            "serverseitigen Schutzmechanismen aktiv sind. Wählen Sie Mittel, die zum Formular "
            "und zum Nutzerrisiko passen, und bedenken Sie Komfort und Barrierefreiheit; "
            "CAPTCHA ist nicht verpflichtend, und ein clientseitiges Widget braucht "
            "serverseitige Validierung."
        ),
        "consequence": (
            "Im Formular selbst ist kein sichtbares Zeichen einer Prüfung zu sehen, ob ein "
            "Mensch es absendet. Das ist eine Beobachtung über den Seitencode, kein "
            "nachgewiesener Mangel: Die Prüfung kann auf dem Server laufen, wo wir sie nicht "
            "sehen."
        ),
    },
    "tech.form_protection.get_method": {
        "title": (
            "{count} Formulare senden Daten per GET"
        ),
        "title.one": "{count} Formular sendet Daten per GET",
        "description": (
            "Ein GET-Formular schreibt die eingegebenen Werte in die Anfrage-URL. Solche URLs "
            "können im Browserverlauf bleiben und in Server- oder Proxy-Logs sowie in kopierten "
            "Links auftauchen. Verwenden Sie POST für Formulare mit persönlichen oder nicht "
            "öffentlichen Daten; POST allein ist keine Verschlüsselung und kein vollständiger "
            "Schutz — HTTPS ist separat erforderlich."
        ),
        "recommendation": (
            "Die Methode auf post ändern — Formulardaten gehören nicht in die Adresszeile."
        ),
        "consequence": (
            "Was jemand ins Formular tippt, landet in der Seitenadresse und kann im "
            "Browserverlauf und in Logs bleiben."
        ),
    },
    "tech.email_exposed": {
        "title": "{count} E-Mail-Adressen offen im Quelltext",
        "description": (
            "mailto:-Links mit Klartextadresse werden von automatischen Scrapern eingesammelt."
        ),
        "recommendation": "Durch ein Kontaktformular ersetzen oder die Adresse per Skript "
        "zusammensetzen.",
        "consequence": (
            "Spam-Bots sammeln die Adresse nach und nach ein, und Müll beginnt einzutreffen. "
            "Das ist lästig, keine Bedrohung: Das Postfach selbst ist nicht in Gefahr."
        ),
    },
    "tech.caching": {
        "title": "Seiten werden ohne Caching-Regeln ausgeliefert",
        "description": "Kein Cache-Control, ETag oder Last-Modified auf {count} geprüften Seiten.",
        "recommendation": "Cache-Control und ETag auf Server- oder CDN-Ebene konfigurieren.",
        "consequence": (
            "Der Browser lädt die Seite jedes Mal neu, auch wenn sich nichts geändert hat."
        ),
    },
    "tech.soft_404": {
        "title": "Eine nicht existierende Seite liefert Status {status}",
        "description": (
            "Der Server antwortet mit Erfolg auf eine Adresse, die es nicht gibt. Erwartet "
            "wird 404."
        ),
        "recommendation": "Den Server so konfigurieren, dass nicht existierende Adressen 404 "
        "liefern.",
        "consequence": (
            "Die Seite antwortet „alles in Ordnung“ und zeigt dabei einen Fehler. Alles, was "
            "sich nach dem Antwortcode richtet — Browser, Suchmaschine, unser eigenes Programm "
            "— hält sie für eine echte Seite."
        ),
    },
    "tech.host_canonical": {
        "title": "Die Website öffnet auch unter {host}",
        "description": (
            "Beide Host-Varianten liefern Inhalt und leiten nicht auf eine einzige um."
        ),
        "recommendation": (
            "Eine dauerhafte 301-Umleitung vom Neben-Host auf den Haupt-Host einrichten."
        ),
        "consequence": (
            "Dieselbe Website existiert unter zwei Adressen, und die Suche teilt ihr Gewicht "
            "zwischen ihnen auf, statt es voll zu zählen."
        ),
    },
    "tech.nap.phone_mismatch": {
        "title": "Die Website zeigt {count} verschiedene Telefonnummern",
        "description": "Verschiedene Seiten zeigen verschiedene Kontaktnummern.",
        "recommendation": "Bei einer Nummer bleiben oder klar sagen, welche Nummer wofür ist.",
        "consequence": (
            "Es wurden mehrere Telefonnummern gefunden, aber keine ist als "
            "Hauptkontaktnummer gekennzeichnet."
        ),
    },
    "tech.nap.phone_not_e164": {
        "title": "{count} Nummern sind nicht im internationalen Format",
        "description": (
            "Ein tel:-Link sollte Plus, Ländervorwahl und Nummer tragen — ohne Leerzeichen, "
            "Klammern oder Striche. Aktuell zum Beispiel: {example}."
        ),
        "recommendation": (
            "Jedes tel: auf internationale Form normalisieren: Plus, Ländervorwahl, dann die "
            "Ziffern ohne Trenner. Der sichtbare Text kann lesbar bleiben."
        ),
        "consequence": (
            "Am Telefon lässt sich so eine Nummer nicht immer mit einem Tipp wählen."
        ),
    },
    "tech.nap.schema_mismatch": {
        "title": "Das Telefon im Markup stimmt nicht mit dem auf den Seiten überein",
        "description": (
            "JSON-LD übergibt Maschinen eine Nummer, während die Website Menschen eine andere "
            "zeigt."
        ),
        "recommendation": "telephone in den strukturierten Daten mit der Nummer in den Kontakten "
        "abgleichen.",
        "consequence": (
            "Ihre Visitenkarte in der Suche kann die falsche Nummer zeigen — Anrufe laufen "
            "an die falsche Stelle."
        ),
    },
    "seo.meta_description.too_long": {
        "title": "Nur die ersten {visible} von {length} Zeichen werden angezeigt",
        "description": (
            "Die Suche schneidet den Rest ab. Eine längere Beschreibung ist kein Fehler — "
            "KI-Crawler lesen sie ganz —, aber in den Ergebnissen sehen Menschen nur den Anfang."
        ),
        "recommendation": (
            "Sicherstellen, dass Kernaussage und Handlungsaufforderung in die ersten {visible} "
            "Zeichen passen."
        ),
        "consequence": (
            "Steht die Hauptbotschaft am Ende der Beschreibung, liest sie in der Suche niemand."
        ),
    },
    "seo.meta_description.too_short": {
        "title": "Die Beschreibung ist zu dünn ({length} Zeichen)",
        "description": "Unter {min} Zeichen kann sie weder erklären noch überzeugen.",
        "recommendation": "Sagen, was die Leistung ist, für wen, und was als Nächstes zu tun ist.",
        "consequence": (
            "Unter Ihrem Suchergebnis steht fast nichts — Menschen wählen den Wettbewerber, "
            "der etwas geschrieben hat."
        ),
    },
    "llm.unstated_facts.offering": {
        "title": (
            "Die gelesenen Seiten sagen nicht, was die Firma verkauft"
        ),
        "description": (
            "Nach Lektüre der gesamten Website lässt sich kein konkretes Produkt und keine "
            "konkrete Leistung benennen. Phrasen wie «Lösungen für Ihr Geschäft» beantworten "
            "die Frage nicht, mit der ein Käufer kommt."
        ),
        "recommendation": (
            "Auf der Startseite in einem Satz sagen, was Sie verkaufen — nicht "
            "«Komplettlösungen», sondern «wir installieren Videoüberwachung»."
        ),
        "consequence": (
            "Die von uns gelesenen Seiten sagen nicht, was Sie verkaufen. Weder ein Mensch noch "
            "ein Such- oder KI-Dienst hat eine Quelle dafür."
        ),
    },
    "llm.unstated_facts.location": {
        "title": "Die Website sagt nie, wo Sie tätig sind",
        "description": (
            "Keine Stadt, keine Region, kein Land — nirgends auf der Website. Für ein "
            "Geschäft mit Einzugsgebiet ist das der erste Filter eines Käufers: Er sucht "
            "jemanden in seiner Nähe."
        ),
        "recommendation": (
            "Stadt und Anschrift in die Fußzeile jeder Seite und auf die Kontaktseite setzen. "
            "Decken Sie ein größeres Gebiet ab, die bedienten Orte auflisten."
        ),
        "consequence": (
            "Auf die Frage «wer macht das in meiner Stadt» hat die Website nichts zu "
            "antworten: Sie sagt nie, wo Sie sind. Damit werden Sie genau den Käufern "
            "seltener vorgeschlagen, für die der Weg zu Ihnen bequem wäre."
        ),
    },
    "llm.unstated_facts.pricing": {
        "title": "Die Website sagt nie, was es kostet",
        "description": (
            "Keine Preise, keine Preisliste, kein klares Angebot, ein Angebot zu erstellen. "
            "Der Preis ist das Erste, wonach ein Käufer fragt, und die Website antwortet nicht."
        ),
        "recommendation": (
            "Preise veröffentlichen, mindestens eine «von–bis»-Spanne. Wird jede Arbeit "
            "individuell kalkuliert, das offen sagen und ein Formular für die Anfrage geben."
        ),
        "consequence": (
            "Der Käufer vergleicht Sie mit Wettbewerbern und streicht Sie zuerst: Deren Preis "
            "ist sichtbar, Ihrer nicht. Schweigen über den Preis liest sich als «teuer»."
        ),
    },
    "ai.jsonld.partial": {
        "title": "Veraltete Beobachtung: Auszeichnung nicht auf jeder Seite",
        "description": (
            "Eine frühere Crawldy-Version wertete teilweise Abdeckung als Mangel. Diese "
            "Beobachtung wurde zurückgezogen: Auszeichnung muss nicht auf jeder Seite stehen, und "
            "neuere Prüfungen behandeln teilweise Abdeckung nicht als Problem."
        ),
        "recommendation": (
            "Allein auf Grundlage dieses veralteten Eintrags ist nichts zu tun."
        ),
        "consequence": (
            "Dieser Eintrag stammt aus einer früheren Prüfversion und beeinflusst neue Ergebnisse "
            "nicht."
        ),
    },
    "tech.demo_content": {
        "title": "Demo-Inhalte des Templates sind noch auf der Website",
        "description": (
            "{count} Anzeichen gefunden, dass ein Teil der Website Demodaten eines nie "
            "ersetzten Themes ist: erfundene Personen im Team-Bereich, eine "
            "Platzhalter-Telefonnummer, eine E-Mail auf der Domain des Theme-Anbieters oder "
            "öffentlich erreichbare Template-Teile des Page-Builders."
        ),
        "recommendation": (
            "Demo-Seiten und -Kontakte entfernen oder ersetzen. Template-Teile des "
            "Page-Builders aus dem Index halten."
        ),
        "consequence": (
            "Besucher sehen Menschen, die nicht für Sie arbeiten, und Kontakte, die Sie nicht "
            "haben. Das beschädigt Vertrauen härter als technische Mängel — und Suchmaschinen "
            "wie Assistenten lesen diese Seiten als die Wahrheit über Ihre Firma."
        ),
    },
    "a11y.blocking": {
        "title": "{count} Barrieren, die die Nutzung der Website verhindern",
        "description": (
            "Es geht nicht um Gestaltung. Gesperrter Zoom, ein Knopf oder Link ohne Namen, "
            "ein Feld ohne Beschriftung — jemand kann schlicht nicht tun, wofür er kam: am "
            "Telefon lesen, antippen, das Formular ausfüllen."
        ),
        "recommendation": (
            "user-scalable=no aus dem Viewport entfernen, Knöpfen und Links Text oder ein "
            "aria-label geben, Formularfelder beschriften."
        ),
        "consequence": (
            "Einige Besucher können Teile der Seite möglicherweise nicht bedienen. "
            "Barrierefreiheitsprobleme betreffen Schaltflächen, Links oder Formularfelder."
        ),
    },
    "a11y.failures": {
        "title": "{count} Anmerkungen zur Barrierefreiheit",
        "description": (
            "Ein automatischer Lighthouse-Durchlauf fand Stellen, an denen Inhalt schwerer zu "
            "lesen oder per Tastatur zu erreichen ist. Volle Normkonformität prüft niemand "
            "automatisch — das braucht manuelle Tests."
        ),
        "recommendation": (
            "Die Liste in den Belegen durchgehen. Das meiste davon lässt sich mit "
            "Markup-Attributen beheben, ohne irgendetwas neu zu gestalten."
        ),
        "consequence": (
            "Menschen mit schwacher Sehkraft, auf älteren Telefonen oder mit Tastatur statt "
            "Maus haben es auf der Website schwerer als nötig."
        ),
    },
    # ── Мовні версії ───────────────────────────────────────────────────────
    "seo.hreflang_invalid": {
        "title": (
            "{count} angegebene Fassungen verwenden einen Wert, den Google nicht annimmt: "
            "{values}"
        ),
        "description": (
            "Google akzeptiert hier eine engere Schreibweise als vermutet: eine Sprache nach "
            "ISO 639-1, wahlweise eine Schrift nach ISO 15924, wahlweise ein Land nach ISO "
            "3166-1 Alpha 2 — genau in dieser Reihenfolge — sowie das reservierte x-default. "
            "zh-Hant und zh-Hans-US sind also gültig, en_US, en-UK und en-US-Latn nicht. Der "
            "Nachweis benennt zu jedem Wert den Fehler; am häufigsten steht ein Länderkürzel "
            "dort, wo die Sprache hingehört."
        ),
        "recommendation": (
            "Korrigieren Sie jeden Wert aus dem Nachweis: Bindestrich statt Unterstrich, en-GB "
            "statt uk oder en-UK, die Sprache vor dem Land. Der Nachweis hält auch fest, an "
            "welcher der drei Stellen der Wert steht."
            "Ein Fall hat keine gültige Form: eine Sprache ohne ISO-639-1-Code "
            "(Asturisch, Kaschubisch und andere; im Nachweis als not_a_language "
            "markiert). Sie lässt sich durch keinen gültigen hreflang-Sprachcode "
            "darstellen, denn Googles Grammatik kennt keinen dafür. Setzen Sie nicht den "
            "Code einer anderen Sprache ein — eine als Spanisch deklarierte asturische "
            "Seite führt Suchmaschinen und Leser in die Irre. Entfernen Sie den Wert und "
            "lassen Sie diese Version ohne hreflang."
            "Steht derselbe Wert auch in den wechselseitigen Sätzen anderer Sprachversionen, "
            "entfernen Sie ihn dort ebenfalls — sonst verweist die halbe Website weiterhin auf "
            "einen ungültigen Code."
        ),
        "consequence": (
            "Die Kennzeichnungen der Sprachversionen sind in einer Form geschrieben, die "
            "Suchmaschinen nicht akzeptieren, also wirken sie nicht. Seiten für andere Länder "
            "bleiben unangemeldet."
        ),
    },
    "seo.hreflang_reciprocity.self": {
        "title": "Die Seite gibt {count} Fassungen an, nennt sich selbst aber nie",
        "description": (
            "Eine Gruppe angegebener Fassungen muss die Seite enthalten, auf der sie steht, mit "
            "Verweis auf deren eigene Adresse. Ohne diesen Selbstverweis gilt die Gruppe als "
            "unvollständig und kann übergangen werden. Ein x-default-Eintrag auf diese Seite "
            "zählt nicht: er bedeutet \"hierher, wenn nichts passt\"."
        ),
        "recommendation": (
            "Ergänzen Sie neben den übrigen einen Eintrag für die Sprache dieser Seite, der auf "
            "genau diese Adresse zeigt. Jede der drei Stellen genügt: die Seite selbst, der "
            "HTTP-Header oder die Sitemap."
        ),
        "consequence": (
            "Die Seite zählt auf, welche anderen Fassungen es gibt, sagt aber nie, welche davon "
            "sie selbst ist — die ganze Gruppe kann verworfen werden, und Besucher landen auf "
            "der falschen Seite."
        ),
    },
    "seo.hreflang_reciprocity.return": {
        "title": "{count} von {checked} geöffneten Fassungen verweisen nicht zurück",
        "description": (
            "Die Angabe wirkt nur, wenn beide Seiten sie machen: nennt diese Seite eine andere "
            "als ihre Fassung, muss jene diese im Gegenzug nennen. Wir haben {checked} der "
            "{declared} hier angegebenen Adressen geöffnet und bei den im Nachweis genannten "
            "keinen Rückverweis gefunden. Über nicht geöffnete Adressen sagen wir nichts."
        ),
        "recommendation": (
            "Ergänzen Sie auf jeder im Nachweis genannten Seite den Eintrag, der auf diese "
            "Adresse zurückverweist. Stammen sie aus derselben Vorlage, ist das meist eine "
            "einzige Änderung."
        ),
        "consequence": (
            "Die Verbindung zwischen beiden Seiten ist nur einseitig erklärt. Suchmaschinen "
            "können sie deshalb als getrennte Seiten behandeln, die einander Konkurrenz machen, "
            "statt als eine Seite für zwei Zielgruppen."
        ),
    },
    "seo.hreflang_conflict.duplicate": {
        "title": "{value} ist für {count} verschiedene Adressen angegeben",
        "description": (
            "Ein Wert darf auf genau eine Adresse zeigen. Zeigt er auf mehrere, ist nicht "
            "erkennbar, welche gemeint war, und Google kann alle Angaben der Seite verwerfen, "
            "nicht nur die widersprüchliche. Der Nachweis listet die konkurrierenden Adressen "
            "und ihre Herkunft auf."
        ),
        "recommendation": (
            "Behalten Sie eine Adresse je Wert. Sehen Sie zuerst die Herkunft im Nachweis an: "
            "widersprechen sich zwei der drei Stellen, stammt die ältere meist aus einer "
            "früheren Einrichtung und kann weg."
        ),
        "consequence": (
            "Die Seite gibt zwei verschiedene Antworten auf dieselbe Frage, und Suchmaschinen "
            "verwerfen die Einstellung eher ganz, als zu raten, was gemeint war."
        ),
    },
    "seo.hreflang_conflict.x_default": {
        "title": "{value} nennt {count} verschiedene Adressen",
        "description": (
            "x-default bezeichnet die Seite, die gezeigt wird, wenn keine der angegebenen "
            "Fassungen zum Besucher passt. Mehrere Angaben lassen genau diesen Fall offen — und "
            "es ist der einzige Fall, in dem für alle Unvorhergesehenen entschieden wird."
        ),
        "recommendation": (
            "Wählen Sie eine Adresse als Rückfallebene und entfernen Sie die übrigen. Üblich "
            "ist eine Seite, die selbst entscheidet: mit Länderauswahl oder Umschalter."
        ),
        "consequence": (
            "Besucher aus einem Land, an das Sie nicht gedacht haben, können auf einer von zwei "
            "Seiten landen — und welche es wird, entscheiden nicht mehr Sie."
        ),
    },
    "seo.hreflang_conflict.canonical": {
        "title": "Die Seite gibt Fassungen an und schickt die Suche zugleich auf {canonical}",
        "description": (
            "Eine Seite, die zu einer Gruppe angegebener Fassungen gehört, muss ihr eigenes "
            "Canonical sein. Hier nennt das Canonical eine andere Adresse — die Angaben "
            "beschreiben also eine Seite, die die Website selbst nicht zeigen lassen will. "
            "Beide Anweisungen widersprechen sich, und Google löst das nach eigenem Ermessen."
        ),
        "recommendation": (
            "Entscheiden Sie, welche Seite die maßgebliche ist: Lassen Sie das Canonical auf "
            "diese Adresse zeigen, oder verschieben Sie die Angaben auf die Seite, die das "
            "Canonical nennt."
        ),
        "consequence": (
            "Die Seite sagt zwei Gegenteile zugleich: dass es sie für andere Länder gibt und "
            "dass nicht sie gezeigt werden soll. Suchmaschinen klären das selbst — meist "
            "anders, als Sie es wollten."
        ),
    },
    "seo.hreflang_broken.unreachable": {
        "title": "{count} angegebene Fassungen lieferten keine funktionierende Seite",
        "description": (
            "Wir haben diese Adressen selbst geöffnet, und der Server antwortete nicht "
            "erfolgreich. Der Nachweis führt jede Adresse mit ihrem Statuscode auf — gemessen, "
            "nicht vermutet. Nicht geöffnete Adressen stehen hier nicht."
        ),
        "recommendation": (
            "Korrigieren Sie jede Adresse aus dem Nachweis auf die Seite, die es heute gibt, "
            "oder nehmen Sie sie aus der Gruppe. Häufigste Ursache ist eine Adresse aus einem "
            "früheren Aufbau der Website."
        ),
        "consequence": (
            "Ein Teil der Adressen, die Besuchern aus anderen Ländern angeboten werden, führt "
            "ins Leere. Wer dorthin geschickt wird, sieht eine Fehlerseite statt Ihrer."
        ),
    },
    "seo.hreflang_broken.noindex": {
        "title": "{count} angegebene Fassungen sind für die Suche gesperrt",
        "description": (
            "Die Adresse ist als zeigenswerte Fassung angegeben und trägt zugleich ein noindex "
            "— die Anweisung an Suchmaschinen, sie nicht zu zeigen. Beides hebt sich auf. Die "
            "Anweisung haben wir auf der Seite selbst gelesen; der Nachweis zitiert sie."
        ),
        "recommendation": (
            "Entscheiden Sie, was gewollt war: noindex von diesen Seiten entfernen oder die "
            "Seiten aus der Gruppe der angegebenen Fassungen nehmen."
        ),
        "consequence": (
            "Eine Seite wird als die für ein anderes Land angeboten und zugleich als eine "
            "gekennzeichnet, die in der Suche nicht erscheinen soll. Besucher von dort werden "
            "nicht hingeschickt."
        ),
    },
    "seo.hreflang_missing": {
        "title": "Seiten erscheinen in {count} Sprachen ({languages}), ohne angegebene Fassungen",
        "description": (
            "Die gelesenen Seiten geben selbst verschiedene Sprachen an, und nirgends steht, "
            "dass sie Fassungen voneinander sind — weder auf den Seiten noch im HTTP-Header "
            "noch in der Sitemap. Ob es Übersetzungen desselben Inhalts oder getrennte Bereiche "
            "sind, ist von außen nicht zu sehen; darum ist das ein Prüfanlass und kein Befund. "
            "Der Nachweis ordnet die Adressen nach Sprache."
        ),
        "recommendation": (
            "Sind es Fassungen desselben Inhalts, geben Sie das an. Eine der drei Stellen "
            "genügt — Google behandelt sie als gleichwertig — und bei generierten Seiten ist "
            "die Sitemap meist die günstigste."
        ),
        "consequence": (
            "Wer auf Deutsch sucht, bekommt womöglich die englisch geschriebene Seite "
            "angezeigt, weil nichts den Suchmaschinen sagt, dass diese Seiten zusammengehören."
        ),
    },
    # ── Перенаправлення ────────────────────────────────────────────────────
    "seo.redirect_chain": {
        "title": "Die Adresse durchläuft {count} Weiterleitungen, bevor die Seite erscheint",
        "description": (
            "Der Browser fragte eine Adresse an und wurde mehr als einmal weitergeschickt, "
            "bevor überhaupt etwas ausgeliefert wurde. Der Nachweis führt jeden Schritt mit "
            "Statuscode und Zieladresse auf. Eine Weiterleitung ist normal — http auf https "
            "oder eine alte Adresse auf ihre Nachfolgerin; eine Kette bedeutet meist zwei "
            "Regeln, die mit der Zeit übereinandergelegt wurden."
        ),
        "recommendation": (
            "Lassen Sie die erste Regel direkt auf die Zieladresse zeigen, damit die Kette auf "
            "einen Schritt zusammenfällt. Nennt der Nachweis Seiten, die auf die "
            "Ausgangsadresse verlinken, ändern Sie auch diese Links — dann verschwindet die "
            "Weiterleitung ganz aus dem Weg, statt nur kürzer zu werden."
        ),
        "consequence": (
            "Jeder zusätzliche Schritt ist ein weiterer Gang zum Server, bevor etwas sichtbar "
            "wird. Die Seite beginnt später zu laden als nötig — am deutlichsten am Handy."
        ),
    },
    "seo.redirect_loop.repeated": {
        "title": "Der Weiterleitungsweg kehrt zu einer bereits besuchten Adresse zurück",
        "description": (
            "Eine Adresse taucht auf dem Weg zur Seite mehrfach auf: der Weg lief in sich "
            "selbst zurück, bevor er endete. Der Nachweis führt die gesamte Abfolge und die "
            "wiederholten Adressen auf. Dieser Weg endete, die Seite war also erreichbar — aber "
            "die Regeln beschreiben einen Kreis, und eine kleine Änderung schließt ihn."
        ),
        "recommendation": (
            "Vergleichen Sie die Regeln, aus denen die wiederholte Adresse im Nachweis stammt. "
            "Meist schicken zwei davon den Verkehr zueinander, und nur die Reihenfolge der "
            "Auswertung hält den Kreis offen."
        ),
        "consequence": (
            "Die Adresse schickt Besucher dorthin zurück, wo sie schon waren. Heute "
            "funktioniert das, doch eine kleine Änderung an einer der Regeln genügt, damit die "
            "Seite gar nicht mehr aufgeht."
        ),
    },
    "seo.redirect_loop.limit": {
        "title": "{url} leitete immer weiter und lieferte nie eine Seite",
        "description": (
            "Wir sind {followed} Weiterleitungen ab dieser Adresse gefolgt und haben "
            "abgebrochen, ohne eine Seite erhalten zu haben. Mehr lässt sich nicht sagen: die "
            "Abfolge endete innerhalb dieser Schritte nicht. Wo sie kreiste — und ob überhaupt "
            "— wissen wir nicht, denn wir bekamen nie eine Seite zu sehen."
        ),
        "recommendation": (
            "Öffnen Sie diese Adresse im Browser und beobachten Sie die Adresszeile. Kommt sie "
            "zur Ruhe, ist die Kette nur lang und die erste Regel sollte direkt auf die "
            "Zieladresse zeigen; ändert sie sich weiter, schicken zwei Regeln den Verkehr "
            "zueinander."
        ),
        "consequence": (
            "Diese Adresse öffnet sich gar nicht. Wer einem Link dorthin folgt — ein Besucher "
            "oder eine Suchmaschine, die die Seite lesen will — bekommt nichts zurück."
        ),
    },
    "seo.redirect_target": {
        "title": "Die Weiterleitung endet auf einer Adresse, die mit {status} antwortete",
        "description": (
            "Die Regel greift und schickt den Browser weiter, doch das Ziel liefert keine "
            "Seite. Den Statuscode haben wir selbst gelesen; der Nachweis führt den ganzen Weg "
            "auf. Die Ursache liegt meist nicht bei der Weiterleitung, sondern beim Ziel: die "
            "Seite wurde später entfernt als die Regel, die auf sie zeigt."
        ),
        "recommendation": (
            "Lassen Sie die Regel auf eine heute existierende Adresse zeigen, oder entfernen "
            "Sie sie. Nennt der Nachweis Seiten, die auf die Ausgangsadresse verlinken, "
            "aktualisieren Sie auch diese Links."
        ),
        "consequence": (
            "Die Adresse führt Besucher auf eine Fehlerseite. Weil die Weiterleitung selbst "
            "funktioniert, wirkt die Website bis zum Moment des Fehlers so, als behandle sie "
            "die Adresse richtig."
        ),
    },
    # ── Узгодженість карти сайту ───────────────────────────────────────────
    "seo.sitemap_consistency.error": {
        "title": "{count} Adressen aus der Sitemap antworteten mit einem Fehler",
        "description": (
            "Die Sitemap bittet Suchmaschinen, diese Adressen zu finden, und der Server "
            "lieferte dort keine Seite. Wir haben jede selbst geöffnet; der Nachweis führt "
            "Adresse und Statuscode auf. Von {declared} angegebenen Adressen haben wir "
            "{checked} geprüft; den Rest haben wir nicht geöffnet, er zählt hier weder so "
            "noch so."
        ),
        "recommendation": (
            "Entfernen Sie diese Adressen aus der Sitemap, oder stellen Sie die Seiten dahinter "
            "wieder her. Eine aus der Datenbank erzeugte Sitemap führt meist weiter Seiten auf, "
            "die über die Oberfläche gelöscht wurden."
        ),
        "consequence": (
            "Sie weisen Suchmaschinen auf Seiten hin, die sich nicht öffnen. Der Aufwand ist "
            "vergebens, und wer eine solche Adresse anders findet, sieht einen Fehler."
        ),
    },
    "seo.sitemap_consistency.redirects": {
        "title": "{count} Adressen aus der Sitemap leiten anderswohin weiter",
        "description": (
            "In einer Sitemap sollte die Adresse stehen, unter der eine Seite endgültig liegt, "
            "nicht eine, die dorthin weiterleitet. Jede dieser Adressen schickt den Browser "
            "weiter; der Nachweis nennt Ziel und Anzahl der Schritte. Von {declared} "
            "angegebenen Adressen haben wir {checked} geprüft."
        ),
        "recommendation": (
            "Ersetzen Sie jeden Eintrag durch die Adresse, bei der er endet — der Nachweis "
            "führt beide. Wird die Sitemap erzeugt, liest der Generator vermutlich eine "
            "gespeicherte Adresse von vor dem letzten Umzug."
        ),
        "consequence": (
            "Die Liste der Adressen, die Sie veröffentlichen, ist nicht die, auf der Besucher "
            "tatsächlich landen. Jede kostet einen zusätzlichen Schritt bis zur Seite."
        ),
    },
    "seo.sitemap_consistency.noindex": {
        "title": "{count} Adressen aus der Sitemap sind für die Suche gesperrt",
        "description": (
            "Diese Seiten tragen eine noindex-Anweisung und stehen zugleich in der Sitemap. "
            "Beides sagt das Gegenteil: das eine bittet, die Seite zu finden, das andere, sie "
            "nicht zu zeigen. Die Anweisung haben wir auf der Seite selbst gelesen; der "
            "Nachweis hält fest, ob sie in der Serverantwort stand oder erst nach den Skripten "
            "erschien. Geprüft: {checked} von {declared} angegebenen Adressen."
        ),
        "recommendation": (
            "Entscheiden Sie, was gewollt war. Soll die Seite nicht in der Suche erscheinen, "
            "nehmen Sie sie aus der Sitemap; soll sie es, entfernen Sie das noindex."
        ),
        "consequence": (
            "Ihre Website bittet darum, diese Seiten zu finden, und auf denselben Seiten darum, "
            "sie nicht zu zeigen. Welche Anweisung auch gewinnt — eine der beiden tut nicht, "
            "was Sie meinten."
        ),
    },
    "seo.sitemap_consistency.canonical": {
        "title": "{count} Adressen der Sitemap nennen eine andere Adresse als die maßgebliche",
        "description": (
            "Jede dieser Seiten gibt ein Canonical an, das nicht der in der Sitemap gelisteten "
            "Adresse entspricht. In der Sitemap sollte die Adresse stehen, die die Seite selbst "
            "für die maßgebliche hält. Der Nachweis zeigt beide und ob die kanonische Adresse "
            "ebenfalls in der Sitemap steht. Welche Adresse eine Suchmaschine am Ende wählt, "
            "behaupten wir nicht zu wissen. Geprüft: {checked} von {declared}."
        ),
        "recommendation": (
            "Tragen Sie stattdessen die kanonische Adresse in die Sitemap ein. Fehlt sie dem "
            "Nachweis zufolge dort ganz, ist ihr Eintragen meist die Lösung."
        ),
        "consequence": (
            "Sitemap und Seiten sind sich uneinig, welche Adresse die echte ist. Sie bitten "
            "darum, die eine Fassung zu finden, während die Seite auf eine andere zeigt."
        ),
    },
    "seo.sitemap_consistency.not_for_search": {
        "title": "{count} Servicesseiten stehen in der Sitemap",
        "description": (
            "Anmeldeseiten, Warenkörbe und Archive sind nicht der Zweck einer Sitemap: dort "
            "stehen die Seiten, die gefunden werden sollen. Der Nachweis nennt jede Adresse und "
            "ihre Einordnung. Geprüft: {checked} von {declared} angegebenen Adressen."
        ),
        "recommendation": (
            "Schließen Sie diese Bereiche aus der Sitemap aus. Die meisten Generatoren haben "
            "dafür eine eigene Einstellung, die standardmäßig meist aus ist."
        ),
        "consequence": (
            "Die Liste der Seiten, die Sie als lesenswert ausgeben, enthält Seiten, nach denen "
            "niemand sucht. Das macht die Liste weniger nützlich und hilft den wichtigen Seiten "
            "nicht."
        ),
    },
    # ── Текст посилань ─────────────────────────────────────────────────────
    "seo.anchor_text": {
        "title": "{count} Linktexte führen jeweils auf mehrere verschiedene Seiten ({links} Links)",
        "description": (
            "Derselbe Wortlaut steht über Links, die an verschiedene Orte führen. Der Nachweis "
            "führt jede Formulierung auf, wie viele Links sie tragen und wie viele "
            "unterschiedliche Ziele sie erreichen. Navigation und Fußbereich zählen nicht — ein "
            "wiederkehrendes \"Preise\" im Kopfbereich ist ein Orientierungspunkt, kein Mangel — "
            "ebenso wenig Seiten, deren Sprache wir nicht bestimmen konnten. Googles eigene "
            "Hinweise nennen \"click here\", \"read more\", \"website\" und \"article\" "
            "als Beispiele "
            "für wenig aussagekräftigen Text."
        ),
        "recommendation": (
            "Geben Sie jedem Link einen Text, der sein Ziel benennt: \"Preisliste 2026 ansehen\" "
            "statt \"Mehr erfahren\". Stammt die Formulierung aus einer Vorlage — Artikelkarten "
            "sind der übliche Fall —, genügt eine Änderung dort, damit der Titel der Zielseite "
            "in den Link wandert. Keine Begriffe hineinstopfen: schreiben Sie, wie ein Mensch "
            "es sagen würde."
        ),
        "consequence": (
            "Leser erkennen vor dem Klick nicht, wohin ein Link führt, und raten entweder oder "
            "übergehen ihn. Auf einer Seite mit lauter gleichen Beschriftungen taugen diese "
            "nicht mehr zur Auswahl."
        ),
    },
    # ── Змішаний вміст ─────────────────────────────────────────────────────
    "tech.mixed_content.blockable": {
        "title": (
            "{count} unsichere Ressourcen auf {pages} sicheren "
            "Seiten laden womöglich gar nicht"
        ),
        "description": (
            "Diese Seiten werden über eine gesicherte Verbindung ausgeliefert, fordern aber "
            "Skripte, Stylesheets oder eingebettete Rahmen über eine ungesicherte an. "
            "Browser korrigieren diese Klasse nicht stillschweigend: sie verweigern die "
            "Anfrage, statt sie auszuführen. Was die Ressource leisten sollte, geschieht "
            "dann einfach nicht. Der Nachweis führt jede Ressource, ihren Typ, ob wir die "
            "Anfrage tatsächlich beobachtet haben und ob sie Ihnen oder einem Dritten "
            "gehört."
        ),
        "recommendation": (
            "Tragen Sie jeweils die gesicherte Adresse ein — die meisten Anbieter liefern "
            "sie seit Jahren, und die Änderung ist meist ein einziges Zeichen. Hat eine "
            "fremde Ressource überhaupt keine gesicherte Adresse, ersetzen oder entfernen "
            "Sie die Abhängigkeit: dieser Anbieter ist auf einer gesicherten Seite nicht "
            "verwendbar."
        ),
        "consequence": (
            "Ein Teil der Seite verlangt etwas, das der Browser über eine ungeschützte "
            "Verbindung nicht holt. Was darauf aufbaute — ein Formular, ein Widget, eine "
            "Zählung — kann für jeden Besucher unbemerkt ausfallen."
        ),
    },
    "tech.mixed_content.upgradeable": {
        "title": (
            "{count} Bilder oder Medien auf {pages} sicheren Seiten "
            "werden unsicher angefordert"
        ),
        "description": (
            "Moderne Browser schreiben solche Anfragen selbst auf die gesicherte Adresse "
            "um, sodass Besucher meist nichts merken. Richtig eingerichtet ist es damit "
            "nicht: das Umschreiben trägt nur, solange die gesicherte Fassung der Datei "
            "existiert, während in der Seite weiter die ungeschützte Adresse steht. Der "
            "Nachweis hält fest, was wir im Browser gesehen haben, und sagt offen, wo wir "
            "nicht nachgesehen haben."
        ),
        "recommendation": (
            "Schreiben Sie die gesicherte Adresse in die Seite, statt sich auf die "
            "Korrektur durch den Browser zu verlassen. Stammen die Ressourcen aus einer "
            "Vorlage oder Mediathek, genügt meist ein Suchen und Ersetzen über die "
            "gespeicherten Inhalte."
        ),
        "consequence": (
            "Die Seite funktioniert derzeit nur, weil Browser diese Adressen "
            "stillschweigend korrigieren. An dem Tag, an dem eine dieser Dateien unter der "
            "korrigierten Adresse fehlt, verschwindet das Bild oder Video ohne jede "
            "Warnung."
        ),
    },
    "tech.mixed_content.download": {
        "title": "{count} Downloads auf {pages} sicheren Seiten werden unsicher angeboten",
        "description": (
            "Eine von einer gesicherten Seite angebotene Datei wird über eine ungeschützte "
            "Verbindung geholt. Browser behandeln diesen Fall gesondert und können den "
            "Download blockieren oder vorher warnen. Der Nachweis führt jede Datei auf."
        ),
        "recommendation": (
            "Liefern Sie diese Dateien über die gesicherte Adresse derselben Website aus. "
            "Liegen sie auf einem fremden Host ohne gesicherte Adresse, verschieben Sie sie "
            "oder hosten Sie sie selbst."
        ),
        "consequence": (
            "Wer diese Dateien anklickt, bekommt womöglich eine Warnung oder gar nichts — "
            "auf einer Seite, die ansonsten vollständig vertrauenswürdig wirkt."
        ),
    },
    "tech.mixed_content.runtime": {
        "title": (
            "{count} unsichere Anfragen auf {pages} Seiten stammen aus Skripten, nicht aus "
            "dem Quelltext"
        ),
        "description": (
            "Wir haben diese Seiten im Browser geöffnet und Anfragen an ungeschützte "
            "Adressen beobachtet, die im Quelltext nirgends stehen. Etwas, das auf der "
            "Seite läuft, baut diese Adressen zur Laufzeit zusammen — meist ein Zähl- oder "
            "Widget-Skript. Der Nachweis führt die aufgezeichneten Adressen."
        ),
        "recommendation": (
            "Suchen Sie das Skript, das die jeweilige Adresse bildet — der Host im Nachweis "
            "nennt meist den Anbieter — und ändern Sie dessen Konfiguration oder ersetzen "
            "Sie es. Eine Suche im Quelltext findet diese Adressen nicht; sie entstehen "
            "erst beim Ausführen."
        ),
        "consequence": (
            "Die Seite greift über eine ungeschützte Verbindung nach außen, während sie "
            "sich als gesichert präsentiert. Im Quelltext ist davon nichts zu sehen, also "
            "übersteht es jede Prüfung, die nur den Code liest."
        ),
    },
    # ── Однаковий вміст під різними адресами ───────────────────────────────
    "seo.duplicate_content.unconsolidated": {
        "title": "{count} Adressgruppen liefern denselben Inhalt ({pages} Seiten)",
        "description": (
            "Jede Gruppe unten enthält Adressen, deren Seiteninhalt übereinstimmt, sobald "
            "man Navigations- und Fußtext beiseitelässt. Nirgends auf der Website steht, "
            "welche die maßgebliche ist — keine Weiterleitung zwischen ihnen, kein "
            "Canonical auf ein einzelnes Mitglied. Gleicher Inhalt ist alltäglich und kein "
            "Regelverstoß; Suchmaschinen fassen solche Seiten selbst zusammen und wählen "
            "eine aus, und welche, können wir Ihnen nicht sagen. Der Nachweis führt jede "
            "Gruppe mit ihren Mitgliedern."
        ),
        "recommendation": (
            "Entscheiden Sie, was diese Adressen sein sollen. Ist es eine Seite, behalten "
            "Sie eine Adresse und leiten die übrigen dorthin, oder lassen Sie alle "
            "Mitglieder dasselbe Canonical nennen. Sollen es verschiedene Seiten sein, "
            "geben Sie ihnen wirklich verschiedene Inhalte. Richten Sie danach interne "
            "Links und die Sitemap auf die gewählte Fassung aus."
        ),
        "consequence": (
            "Dieselbe Seite existiert unter mehreren Adressen, und nichts sagt, welche "
            "zählt. Besuche, Verlinkungen und jede Messung verteilen sich darauf, und Sie "
            "sehen nicht, wo die Leute tatsächlich ankamen."
        ),
    },
    "seo.duplicate_content.conflicting": {
        "title": "{count} Gruppen gleicher Seiten sind uneins, welche Adresse maßgeblich ist",
        "description": (
            "Diese Adressen liefern denselben Inhalt, und die Seiten selbst nennen "
            "unterschiedliche maßgebliche Adressen — oder eine, die gar nicht zur Gruppe "
            "gehört. Das ist ein Widerspruch innerhalb der Website, kein Regelverstoß: "
            "Suchmaschinen lösen ihn nach eigenem Ermessen, und ihre Wahl kann von Ihrer "
            "abweichen. Der Nachweis zeigt, was jedes Mitglied angibt."
        ),
        "recommendation": (
            "Wählen Sie eine Adresse für die Gruppe und lassen Sie alle Mitglieder sie "
            "nennen. Zeigt ein Mitglied nach außen, prüfen Sie, ob jene Adresse wirklich "
            "gemeint ist — meist stammt sie aus einer früheren Struktur."
        ),
        "consequence": (
            "Ihre Seiten geben widersprüchliche Antworten darauf, welche Fassung die echte "
            "ist. Damit wird die Entscheidung für Sie getroffen statt von Ihnen."
        ),
    },
    # ── Транспорт: стиснення й протокол ────────────────────────────────────
    "tech.transport.uncompressed": {
        "title": "{count} Textantworten kamen ohne Komprimierung an (größte {size} KB)",
        "description": (
            "Wir haben komprimierte Inhalte angefragt, und diese Antworten kamen uncodiert "
            "zurück. Der Nachweis führt jede auf: Typ, was wir angefragt haben, und beide "
            "Größen, die sich feststellen ließen. Beachten Sie, was hier steht und was "
            "nicht: beschrieben werden die erhaltenen Antworten, nicht die Fähigkeiten des "
            "Servers. Wir kündigen nur gzip und deflate an, ein Server mit ausschließlich "
            "Brotli antwortete uns also genauso. Wie viele Bytes Komprimierung spart, sagen "
            "wir nicht — dafür hätten wir sie selbst komprimieren müssen, was wir nicht "
            "getan haben."
        ),
        "recommendation": (
            "Prüfen Sie, ob die Komprimierung für diese Inhaltstypen am Server oder CDN "
            "aktiv ist. gzip genügt völlig; ein Wechsel zu Brotli oder Zstandard ist dafür "
            "nicht nötig und wäre eine eigene Entscheidung mit eigenen Abwägungen."
        ),
        "consequence": (
            "Text, der komprimiert reisen könnte, reist ganz. Jeder Besucher wartet damit "
            "auf mehr Bytes als nötig — am deutlichsten bei langsamer Mobilverbindung."
        ),
    },
    "tech.transport.http1": {
        "title": "{count} Antworten wurden über HTTP/1.1 ausgeliefert",
        "description": (
            "Unser Client bietet HTTP/2 an und einigt sich mit den meisten Websites "
            "erfolgreich darauf; bei diesen Antworten blieb die Verbindung beim älteren "
            "Protokoll. Das ist eine Beobachtung zu diesen Austauschen, keine Aussage, dass "
            "Ihr Server kein HTTP/2 beherrscht: die ausgehandelte Version hängt vom Server, "
            "von einem CDN im Pfad und vom Client ab. HTTP/2 nutzt eine Verbindung "
            "effizienter — mehrere Austausche gleichzeitig, komprimierte Header —, ob eine "
            "bestimmte Seite schneller lädt, hängt jedoch von der Seite ab. HTTP/3 prüfen "
            "wir gar nicht; dazu steht hier nichts."
        ),
        "recommendation": (
            "Prüfen Sie die HTTP/2-Einstellung am Server oder am vorgelagerten CDN. In den "
            "meisten Hosting-Oberflächen und CDNs ist das ein einzelner Schalter, der bei "
            "älteren Konfigurationen oft aus ist."
        ),
        "consequence": (
            "Zugriffe auf Ihre Website nutzen eine ältere, weniger effiziente Art, sich "
            "eine Verbindung zu teilen. Auf Seiten mit vielen gleichzeitigen Dateien zeigt "
            "sich das als zusätzliches Warten."
        ),
    },
}


# Einzeilige Domain-Hinweise: warum ein Teil des Audits nicht lief und warum
# ein Lauf wiederholt wurde oder nicht. Absichtlich getrennt von MESSAGES —
# die Begründung steht im ukrainischen Katalog.
NOTICES: dict[str, str] = {
    "notice.breadcrumb.hierarchy_unknown": (
        "es wurde zu wenig von der Website gelesen, um zu sagen, ob ihre Seiten einander "
        "untergeordnet sind; ob Brotkrumen hierher gehören, bleibt daher offen"
    ),
    "notice.about_page.candidate_unread": (
        "die Über-uns-Seite, auf die die Website verweist ({anchor}: {url}), wurde nicht "
        "gelesen; ob die Website sagt, wer dahintersteht, bleibt offen"
    ),
    "notice.about_page.candidate_unreadable": (
        "die Über-uns-Seite unter {url} konnte nicht beurteilt werden: {reasons} (Antwort {status})"
    ),
    "coverage.reason.about_page_failed_read": "die Seite lieferte kein lesbares Dokument",
    "coverage.reason.about_page_content_shell": (
        "die Antwort war eine leere Anwendungshülle: Markup ohne Haupttext"
    ),
    "coverage.reason.about_page_login_wall": (
        "der Hauptinhalt war ein Anmeldeformular, und eine Über-uns-Überschrift fehlte"
    ),
    "coverage.reason.about_page_redirect_placeholder": (
        "das Dokument leitete den Leser lediglich weiter"
    ),
    # degradations
    "notice.accessibility.no_category": (
        "keine Barrierefreiheits-Prüfungen gelaufen: der Anbieter lieferte diese Kategorie nicht"
    ),
    "notice.accessibility.not_measured": (
        "die Barrierefreiheit wurde nicht gemessen: die Geschwindigkeitsmessung war von "
        "diesem Audit ausgeschlossen"
    ),
    "notice.crawl.blind": (
        "die Website lieferte keine Seite mit Inhalt (Antwortstatus: {statuses})"
    ),
    "notice.coverage.withheld": (
        "Analysierte Seiten: {pages}. Die Gesamtbewertung der Website wird zurückgehalten: "
        "sichtbare Live-Inhalte wurden nicht geprüft ({reasons}). Eine Bewertung des "
        "Gelesenen darf nicht als Bewertung der Website gelten."
    ),
    "notice.coverage.limited": (
        "Analysierte Seiten: {pages}. Einschränkung der Abdeckung: {reasons}."
    ),
    "coverage.reason.robots_restricted": (
        "das Crawling ist durch die robots.txt der Website eingeschränkt"
    ),
    "coverage.reason.access_failures": (
        "einige erreichbare Adressen antworteten nicht — {access} von {attempted}"
    ),
    "coverage.reason.untried_live_candidates": (
        "entdeckte Seiten der Website wurden nicht geöffnet — {untried}"
    ),
    "coverage.reason.no_evidence_of_additional_live_content": (
        "keine Hinweise auf weitere Live-Inhalte gefunden"
    ),
    "notice.crawl.failures": (
        "{failed} von {attempted} Adressen antworteten nicht: das Gelesene "
        "repräsentiert die Website nicht"
    ),
    "notice.crawl.empty": (
        "{words} Wörter auf der gesamten Website, selbst nach Ausführung der Skripte; "
        "gelesene Seiten: {pages}. Es gibt nichts zu bewerten"
    ),
    "notice.crawl.empty_static": (
        "die Serverantwort enthält {words} Wörter: Der Text erscheint erst nach Ausführung "
        "der Skripte ({rendered} Wörter auf {pages} Seiten). Suchmaschinen sehen eine solche "
        "Seite, die meisten Assistenten nicht"
    ),
    "notice.crawl.entry_error": (
        "die Einstiegsadresse lieferte HTTP {status}: die Geschwindigkeit wurde auf einer "
        "Fehlerseite gemessen, nicht auf der Website"
    ),
    "notice.crawl.entry_error_stand_in": (
        "die Einstiegsadresse lieferte HTTP {status}: die Geschwindigkeit wurde auf einer "
        "Fehlerseite gemessen, nicht auf der Website; als Startseite diente stattdessen {stand_in}"
    ),
    "notice.crawl.shallow": (
        "nur die Startseite wurde gecrawlt, obwohl sie auf Unterseiten verlinkt: der Rest "
        "antwortete nicht oder lieferte kein HTML"
    ),
    "notice.module.excluded": "das Modul wurde in den Audit-Optionen abgeschaltet",
    "notice.performance.no_vitals": (
        "Core Web Vitals wurden nicht gemessen ({detail}). Die Bewertung stützt sich nur auf "
        "die Antwortzeit des Servers und statische HTML-Signale"
    ),
    "notice.performance.no_metrics": "der Anbieter lieferte keine Metriken: {detail}",
    "notice.performance.partial": "die Geschwindigkeitsdaten sind unvollständig: {detail}",
    "notice.llm.unavailable": "keine semantische Analyse gelaufen: {detail}",
    "notice.llm.disabled": "die semantische Analyse wurde in den Audit-Optionen abgeschaltet",
    "notice.llm.facts_unavailable": (
        "die semantische Analyse lieferte keine Fakten zum Unternehmen: die Prüfung, die "
        "darauf aufbaut, lief nicht"
    ),
    "notice.render.failed": "Seiten wurden nicht gerendert: {detail}",
    "notice.render.disabled": "das Rendern wurde in den Audit-Optionen abgeschaltet",
    "notice.analytics.unidentified": (
        "Messverkehr ist sichtbar, aber kein Anbieter ließ sich bestimmen ({detail}): die "
        "Aussage zur Analytik bleibt offen"
    ),
    "notice.analytics.render_incomplete": (
        "im Markup steht kein Zähler, und die Seiten, die ihn nach dem Ausführen der Skripte "
        "noch zeigen könnten, wurden nicht gerendert ({detail})"
    ),
    "notice.check.failed": "die Prüfung lief wegen eines Fehlers nicht",
    "notice.layer.failed": "ein Teil des Audits lief wegen eines Fehlers nicht",
    # retries
    "notice.retry.not_attempted": "keine Wiederholung geplant",
    "notice.retry.scheduled": "Versuch {next_attempt} von {allowed}",
    "notice.retry.exhausted": "Versuche erschöpft ({attempts}/{allowed})",
    "notice.retry.not_retryable": "Fehler vom Typ «{failure}» wiederholen wir nicht",
}


# Tarifkatalog: was der Kunde kauft, in menschlichen Worten. Absichtlich
# getrennt von MESSAGES und NOTICES — siehe den ukrainischen Katalog.
CATALOG: dict[str, str] = {
    "plan.limit.audits": "{count} Audits pro Monat",
    "plan.limit.audits_unlimited": "Unbegrenzte Audits",
    "plan.limit.pages": "Bis zu {count} Seiten pro Audit",
    "plan.limit.sites": "{count} Websites",
    "plan.limit.sites_unlimited": "Unbegrenzte Websites",
    "plan.limit.schedules": "{count} Zeitpläne",
    "plan.limit.team": "{count} Teammitglieder",
    "plan.limit.history": "{count} Tage Verlauf",
    "plan.limit.history_unlimited": "Vollständiger Verlauf",
    "plan.feature.semantic": "Semantische Analyse",
    "plan.feature.reports": "Word-Berichte",
    "plan.feature.public_reports": "Öffentliche Berichtslinks",
    "plan.feature.api": "API-Zugang",
    "plan.feature.white_label": "Berichte unter Ihrer Marke",
    "plan.cta.start_free": "Kostenlos starten",
    "plan.cta.subscribe": "Abonnieren",
    "plan.cta.contact": "Mit uns sprechen",
}
