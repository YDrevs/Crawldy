"""Formulation française des constats. Écrite pour le client, pas traduite mot à mot.

Glossaire de la langue (cohérent avec le site public FR) :
constat — finding ; preuve — evidence ; couverture — coverage ;
recommandation — recommendation ; IA — jamais « AI » comme terme
premier ; moteurs de recherche — search engines. Adresse : vous.
"""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    # ── SEO ─────────────────────────────────────────────────────────────────
    "seo.title.missing": {
        "title": "Balise <title> absente",
        "description": "La page n'a pas de balise titre — critique pour la recherche comme pour "
        "les modèles.",
        "recommendation": "Ajouter un titre unique de 30–60 caractères contenant la requête "
        "principale.",
        "consequence": (
            "La page n’a pas de titre propre. Les moteurs de recherche peuvent composer "
            "eux-mêmes l’intitulé du résultat à partir du texte de la page."
        ),
    },
    "seo.title.too_short": {
        "title": "Le titre n'explique rien ({length} caractères)",
        "description": (
            "Un titre de moins de {min} caractères ne peut pas dire de quoi parle la page."
        ),
        "recommendation": (
            "Ajouter ce que les gens cherchent réellement : le service, le lieu, le bénéfice."
        ),
        "consequence": (
            "À côté des concurrents dans les résultats, un tel titre ne donne aucune raison de "
            "cliquer chez vous."
        ),
    },
    "seo.title.too_long": {
        "title": "Seuls les {visible} premiers caractères sur {length} sont affichés",
        "description": "La recherche tronque la fin du titre.",
        "recommendation": (
            "Placer l'essentiel en tête — tout ce qui dépasse {visible} caractères n'est pas "
            "affiché."
        ),
        "consequence": (
            "Personne ne voit la fin du titre — si l'essentiel s'y trouvait, il ne passe pas."
        ),
    },
    "seo.title.duplicate": {
        "title": "Le même titre sur {count} pages",
        "description": "Des titres identiques rendent les pages indiscernables dans l'index.",
        "recommendation": "Donner à chaque page son propre titre.",
        "consequence": (
            "Pour les moteurs comme pour les gens, les pages semblent identiques : difficile de "
            "savoir laquelle il faut."
        ),
    },
    "seo.meta_description.missing": {
        "title": "Meta description absente",
        "description": "Sans elle, la recherche assemble l'extrait à partir d'un fragment "
        "aléatoire.",
        "recommendation": "Ajouter une description qui tient dans les ~{visible} caractères "
        "visibles.",
        "consequence": (
            "Aucune méta-description n’a été détectée pour cette page. Les moteurs de "
            "recherche peuvent donc créer l’extrait à partir du texte de la page."
        ),
    },
    "seo.h1.missing": {
        "title": "Pas de h1 dans la vue analysée",
        "description": (
            "La vue analysée de la page ne contient aucun titre HTML h1. Si des titres de "
            "niveaux inférieurs existent, le premier d'entre eux figure dans les preuves. Un h1 "
            "clair est une pratique recommandée de structure de document ; pour comprendre et "
            "étiqueter une page, c'est un signal possible parmi plusieurs, aux côtés du title "
            "et d'autres."
        ),
        "recommendation": (
            "Envisagez un h1 clair portant le sujet de la page — il suffit souvent de promouvoir "
            "le premier titre existant."
        ),
        "consequence": (
            "Le titre principal de la page n'est pas marqué comme le plus haut niveau dans le "
            "code. Les programmes qui lisent la structure s'appuient sur d'autres indices : le "
            "titre de l'onglet et les sous-titres."
        ),
    },
    "seo.h1.no_headings": {
        "title": "Aucun titre HTML (h1–h6) trouvé",
        "description": (
            "La vue analysée de la page ne contient aucun titre HTML h1–h6 non vide. Les titres "
            "organisent le contenu pour les lecteurs et les technologies d'assistance ; cette "
            "affirmation porte précisément sur les titres HTML — les autres mécanismes de "
            "balisage n'ont pas été évalués."
        ),
        "recommendation": (
            "Ajoutez une structure de titres claire et adaptée à cette page : un titre principal "
            "et des sous-titres de section."
        ),
        "consequence": (
            "La page n'a pas de structure de sections marquée. Les lecteurs et les lecteurs "
            "d'écran n'ont rien à quoi se raccrocher, hormis du texte continu."
        ),
    },
    "seo.h1.multiple": {
        "title": "Plusieurs éléments h1 ({count}) ; visibilité non évaluée",
        "description": (
            "La vue analysée contient {count} éléments h1 non vides. Leur visibilité CSS n'a pas "
            "été évaluée : certains peuvent être des doublons de gabarit pour différentes mises "
            "en page. Un seul h1 principal clair est une bonne pratique courante, mais plusieurs "
            "h1 sont permis par le HTML, et cette observation seule n'établit pas un problème de "
            "recherche."
        ),
        "recommendation": (
            "Si les doublons ne sont pas voulus, gardez un h1 principal et rétrogradez les autres "
            "en sous-titres."
        ),
        "consequence": (
            "Le titre principal est marqué plusieurs fois. C'est une observation sur le code de "
            "la page, pas un préjudice constaté."
        ),
    },
    "seo.heading_hierarchy": {
        "title": "Saut de titre H{previous} → H{level}",
        "description": "Un niveau sauté rend la structure plus difficile à analyser côté machine.",
        "recommendation": "Ne pas sauter de niveaux de titres.",
        "consequence": (
            "La structure de la page paraît illogique au logiciel qui la lit, et le texte se "
            "découpe moins bien en blocs de sens."
        ),
    },
    "seo.canonical.missing": {
        "title": "Pas de rel=canonical",
        "description": "",
        "recommendation": "Donner à chaque page indexable une canonical auto-référencée.",
        "consequence": (
            "Si la même page est accessible à plusieurs adresses, la recherche peut les "
            "traiter comme des pages différentes et diviser leur poids."
        ),
    },
    "seo.canonical.mismatch": {
        "title": "La canonical pointe vers une autre page",
        "description": "Cela retire la page de l'index — vérifiez que c'est voulu.",
        "recommendation": "Vérifier que la canonical ne pointe pas par erreur vers la page "
        "d'accueil.",
        "consequence": (
            "La page dit aux moteurs qu'elle n'est pas la version principale, et peut donc "
            "disparaître entièrement des résultats."
        ),
    },
    "seo.noindex": {
        "title": "La page est fermée à la recherche",
        "description": (
            "Le balisage demande aux moteurs de ne pas montrer cette page. C'est souvent "
            "délibéré — pages payantes, archives d'événements, pages pour trafic interne. "
            "Nous voyons l'instruction, pas l'intention — vérifiez qu'elle a sa place ici."
        ),
        "recommendation": (
            "Si la page doit amener des gens depuis la recherche, retirez l'instruction. Si "
            "elle est fermée à dessein, laissez tout tel quel."
        ),
        "consequence": (
            "Tant que l'instruction est là, cette page n'amène aucun visiteur depuis la "
            "recherche. Si c'est voulu, tout va bien ; sinon, le travail investi ne sert à rien."
        ),
    },
    "seo.render_delta.indexing": {
        "title": "Les signaux d’indexation diffèrent après JavaScript : {fields}",
        "description": (
            "La réponse du serveur et la page après exécution des scripts divergent sur les "
            "signaux qui décident quelle URL est indexée. Les deux valeurs figurent dans les "
            "preuves. Google exécute JavaScript, mais sa documentation évoque une file d’attente "
            "qui \"can take longer\" que quelques secondes, et rappelle que \"not all bots can "
            "run JavaScript\"."
        ),
        "recommendation": (
            "Déterminez laquelle des deux valeurs correspond à votre intention et servez-la "
            "directement dans le HTML, plutôt que via un script."
        ),
        "consequence": (
            "Deux instructions différentes coexistent pour la même page, et celle qui s’applique "
            "dépend du fait que le système visiteur exécute ou non les scripts."
        ),
    },
    "seo.render_delta.identity": {
        "title": "La présentation de la page change après JavaScript : {fields}",
        "description": (
            "Le titre ou le texte affiché dans les résultats de recherche n’est pas le même avant "
            "et après l’exécution des scripts. Les deux valeurs figurent dans les preuves. Un "
            "système qui n’exécute pas JavaScript ne voit que la réponse du serveur."
        ),
        "recommendation": (
            "Placez le titre et la description définitifs dans le HTML envoyé par le serveur ; "
            "laissez les scripts enrichir la page, pas la définir."
        ),
        "consequence": (
            "Certains systèmes décrivent votre page d’une manière et d’autres autrement : le nom "
            "que voient les gens n’est pas toujours celui que vous avez écrit."
        ),
    },
    "seo.render_delta.markup": {
        "title": "Les données structurées diffèrent après JavaScript",
        "description": (
            "Le balisage lisible par les machines n’est pas identique avant et après l’exécution "
            "des scripts : des types ou des identifiants apparaissent, disparaissent ou changent. "
            "Les preuves listent les deux ensembles."
        ),
        "recommendation": (
            "Émettez le balisage dans la réponse du serveur. Ce qui n’apparaît qu’après les "
            "scripts n’est lu que par les systèmes qui les exécutent."
        ),
        "consequence": (
            "Les informations que vous publiez sur votre activité sont lisibles pour certains "
            "systèmes et invisibles pour d’autres."
        ),
    },
    "seo.render_delta.links": {
        "title": "{count} liens internes n’existent qu’après JavaScript",
        "description": (
            "Ces liens sont absents de la réponse du serveur et n’apparaissent que dans la page "
            "rendue. Les preuves les listent. Google suit les liens trouvés après rendu, mais sa "
            "documentation rappelle que tous les robots n’exécutent pas JavaScript."
        ),
        "recommendation": (
            "Servez ces liens comme des ancres ordinaires dans le HTML. Les scripts peuvent "
            "améliorer la navigation par-dessus."
        ),
        "consequence": (
            "Des parties du site ne sont atteignables que par les systèmes qui exécutent les "
            "scripts ; pour les autres, ces pages ne sont pas liées depuis ici."
        ),
    },
    "seo.robots_txt.missing": {
        "title": "robots.txt absent",
        "description": "Les robots n'ont ni instructions ni pointeur vers votre sitemap.",
        "recommendation": "Ajouter /robots.txt avec une directive Sitemap.",
        "consequence": (
            "Les moteurs arrivent sans instructions et ne savent pas où trouver votre sitemap."
        ),
    },
    "seo.robots_txt.disallow_all": {
        "title": "robots.txt bloque tout le site",
        "description": "`Disallow: /` pour `User-agent: *` bloque toute exploration.",
        "recommendation": "Retirer Disallow: / si le site doit figurer dans la recherche.",
        "consequence": (
            "robots.txt interdit l’exploration de tout le site. Les moteurs de recherche ne "
            "liront pas les pages ; une adresse peut malgré tout apparaître dans les résultats, "
            "mais sans description ni contenu."
        ),
    },
    "seo.robots_txt.no_sitemap": {
        "title": "robots.txt sans directive Sitemap",
        "description": "",
        "recommendation": "Ajouter une ligne `Sitemap: https://.../sitemap.xml`.",
        "consequence": (
            "Les moteurs n'ont aucune indication de l'emplacement de votre liste de pages et "
            "les découvrent plus lentement."
        ),
    },
    "seo.sitemap.missing": {
        "title": "sitemap.xml introuvable",
        "description": "",
        "recommendation": "Générer une sitemap XML et la référencer depuis robots.txt.",
        "consequence": (
            "Aucun plan du site trouvé : il est absent des emplacements standard et le site n’a "
            "indiqué aucune autre adresse."
        ),
    },
    "seo.sitemap.invalid": {
        "title": "sitemap.xml ne se lit pas",
        "description": "",
        "recommendation": "Réparer le XML — une sitemap invalide est ignorée par les robots.",
        "consequence": (
            "Le plan du site existe mais ne peut pas être lu : le fichier n’est pas un XML "
            "valide. Il ne servira à rien tant que le format n’est pas corrigé."
        ),
    },
    "seo.sitemap.empty": {
        "title": "sitemap.xml est vide",
        "description": "",
        "recommendation": "Ajouter les URL de vos pages à la sitemap.",
        "consequence": "La sitemap ne contient aucune adresse et ne remplit pas son rôle.",
    },
    "seo.sitemap.coverage": {
        "title": "{count} pages explorées absentes de la sitemap",
        "description": "",
        "recommendation": "Garder la génération de la sitemap alignée sur la structure réelle du "
        "site.",
        "consequence": (
            "Une partie des pages manque dans la sitemap : la recherche les découvre plus "
            "tard, ou pas du tout."
        ),
    },
    "seo.broken_links": {
        "title": "{count} URL internes renvoient une erreur",
        "description": (
            "Nous avons suivi ces liens nous-mêmes et le serveur a répondu par une erreur. La "
            "preuve porte chaque destination cassée avec les pages qui pointent vers elle, le "
            "texte de chaque lien, et si le lien figurait dans la réponse du serveur ou n'est "
            "apparu qu'après l'exécution des scripts. Une destination sans page source n'était "
            "liée depuis aucune page lue : elle vient du sitemap."
        ),
        "recommendation": (
            "Partez de la preuve : pour chaque destination, elle nomme les pages qui pointent "
            "vers elle. Corrigez ces liens vers une adresse valide, ou supprimez-les. Quand "
            "plusieurs pages pointent vers la même adresse morte, le lien se trouve en général "
            "dans un gabarit partagé."
        ),
        "consequence": "Les visiteurs tombent sur des pages cassées — visites perdues et mauvaise "
        "impression.",
    },
    "seo.https.missing": {
        "title": "Le site n'est pas en HTTPS",
        "description": "Les sites HTTP sont marqués comme non sécurisés et classés moins bien.",
        "recommendation": "Activer TLS et rediriger HTTP vers HTTPS en 301.",
        "consequence": (
            "Les navigateurs signalent le site comme non sécurisé et affichent un avertissement "
            "avant le contenu. Ce que le visiteur en fait, nous ne le mesurons pas."
        ),
    },
    "seo.https.invalid_cert": {
        "title": "Le certificat HTTPS n'est pas valide",
        "description": (
            "Le site ne se charge qu'avec la vérification du certificat désactivée. Causes "
            "habituelles : chaîne intermédiaire incomplète, certificat auto-signé ou expiré. "
            "Les robots de recherche sautent les sites dans cet état."
        ),
        "recommendation": (
            "Réémettre le certificat et servir la chaîne intermédiaire complète. Vérifier le "
            "résultat sur ssllabs.com/ssltest — la note doit être A."
        ),
        "consequence": (
            "À la place de votre site, les visiteurs voient une page d'alerte rouge avec un "
            "bouton « Revenir en sécurité ». Presque tous l'utilisent."
        ),
    },
    "seo.https.no_hsts": {
        "title": "Pas d'en-tête HSTS",
        "description": "",
        "recommendation": "Ajouter `Strict-Transport-Security: max-age=31536000`.",
        "consequence": (
            "La première visite peut passer par une connexion non protégée — une faille "
            "petite mais réelle."
        ),
    },
    "seo.image_alt": {
        "title": "{without_alt} images sur {total} sans attribut alt",
        "description": "Le texte alt relève de l'accessibilité et sert de signal textuel aux "
        "modèles.",
        "recommendation": "Décrire le contenu de l'image ; garder alt=\"\" pour le décoratif.",
        "consequence": (
            "Les visiteurs aveugles n’entendent rien de l’image : un lecteur d’écran prend la "
            "description dans cet attribut. Un texte qui n’existe qu’à l’intérieur d’une image "
            "ne fait pas partie du contenu de la page."
        ),
    },
    "seo.thin_content": {
        "title": "Seulement {word_count} mots sur la page",
        "description": (
            "Peu de texte est un signal faible pour la recherche comme pour la citation par "
            "les modèles. Cela peut aussi signifier un rendu côté client."
        ),
        "recommendation": "Étoffer le texte principal à {threshold}+ mots, ou vérifier le SSR.",
        "consequence": (
            "Trop peu de texte pour que la page soit jugée utile : elle se classe mal et il "
            "n'y a presque rien à citer."
        ),
    },
    "seo.click_depth": {
        "title": "Peu de liens depuis cette page : {internal_links}",
        "description": (
            "Cette page renvoie vers {internal_links} autres pages du site. Ce sont les "
            "liens présents sur cette page ; cela ne dit rien du nombre de pages qui "
            "pointent VERS elle — une page vers laquelle tout le menu renvoie peut "
            "elle-même ne mener nulle part."
        ),
        "recommendation": (
            "Ajoutez depuis cette page des liens vers ce que le lecteur voudra ensuite : "
            "prestations proches, rubrique correspondante, exemple cité."
        ),
        "consequence": (
            "Qui arrive ici n'a presque nulle part où continuer : la personne repart au "
            "lieu de regarder ce que vous proposez d'autre."
        ),
    },
    "cro.no_action": {
        "title": "Rien à faire sur cette page",
        "description": (
            "Une page qui propose quelque chose n'a ni formulaire, ni téléphone ou e-mail "
            "cliquable, ni lien vers la commande, le panier ou les contacts. Celui que la "
            "page a convaincu n'a rien pour agir."
        ),
        "recommendation": (
            "Donner à la page une prochaine étape évidente et la répéter après le texte "
            "principal : un bouton de commande, un formulaire de demande ou le numéro de "
            "téléphone en lien. Une étape claire vaut mieux que trois."
        ),
        "consequence": (
            "Cette page n’offre aucune action en dehors du menu et du pied de page : ni "
            "formulaire, ni bouton, ni contact dans le texte lui-même. Qui a fini de lire et "
            "veut vous joindre doit chercher par soi-même."
        ),
    },
    "cro.phone_not_tappable": {
        "title": "Le numéro de téléphone est affiché mais ne se compose pas",
        "description": (
            "Le numéro figure sur le site mais n'est nulle part balisé comme lien d'appel. "
            "Sur téléphone, le visiteur doit le mémoriser, quitter le site et le taper à la "
            "main. Pages où nous l'avons vu : {count}."
        ),
        "recommendation": (
            "Baliser le numéro en lien tel:+… partout où il apparaît — en-tête, pied de page "
            "et page contact. Une demi-heure de travail."
        ),
        "consequence": (
            "La plupart des visiteurs arrivent sur téléphone. Au lieu de toucher pour "
            "appeler, ils doivent recopier le numéro — et une partie ne le fera tout "
            "simplement pas."
        ),
    },
    "seo.topic_islands": {
        "title": "{count} pages sur un même sujet ne se citent jamais",
        "description": (
            "Nous avons lu {count} pages couvrant le même terrain, et aucune n'en mentionne "
            "une autre. Le seul chemin de l'une à l'autre est le menu ou une page d'index — "
            "les liens de sens, ceux qui montrent que le sujet a été travaillé, manquent."
        ),
        "recommendation": (
            "Ajoutez des liens contextuels ENTRE DES PAGES RÉELLEMENT LIÉES là où ils aident "
            "vraiment le lecteur : d'une étude de cas vers une étude voisine, d'un article vers "
            "celui qui le prolonge. Il n'est pas nécessaire de relier chaque page de la section à "
            "toutes les autres — un lien posé pour satisfaire une règle n'aide ni la personne ni "
            "le moteur."
        ),
        "consequence": (
            "Les pages ne se renforcent pas. Qui en lit une ne se voit jamais proposer la "
            "suivante dont il a besoin, et le site se lit comme une pile de feuilles "
            "séparées plutôt que la preuve que l'entreprise connaît son domaine."
        ),
    },
    "seo.orphan_pages": {
        "title": "{count} pages de la sitemap sans aucun lien entrant",
        "description": (
            "La sitemap déclare ces pages, mais rien sur le site n'y mène. Les moteurs "
            "peuvent les trouver ; un visiteur, jamais, et leur statut repose sur la seule "
            "sitemap — le plus faible signal qu'un site puisse envoyer."
        ),
        "recommendation": (
            "Lier ces pages depuis leur place naturelle : le menu, leur catégorie parente ou "
            "le corps des pages proches. Si une page n'est pas destinée aux visiteurs, la "
            "retirer plutôt de la sitemap."
        ),
        "consequence": (
            "Ces pages existent, mais aucun chemin du site n'y mène. Les visiteurs ne les "
            "voient jamais, et le travail investi est perdu."
        ),
    },
    "seo.links_to_noindex": {
        "title": "{count} pages liées mais cachées de la recherche",
        "description": (
            "Le site met une page dans sa navigation et interdit en même temps aux moteurs "
            "de la montrer. L'un des deux est faux : soit la page compte pour les gens et "
            "doit être visible, soit elle est interne et n'a pas sa place au menu."
        ),
        "recommendation": (
            "Décider, pour chaque page, laquelle des deux elle est. Si elle compte, retirer "
            "l'interdiction d'indexation ; si elle est interne, retirer le lien de la "
            "navigation."
        ),
        "consequence": (
            "Un visiteur suit un lien vers une page que les moteurs doivent cacher. Le site "
            "se contredit, et une partie du chemin vers l'achat mène nulle part."
        ),
    },
    "seo.viewport": {
        "title": "Pas de meta viewport",
        "description": "Sans viewport, la page ne s'adapte pas aux écrans mobiles.",
        "recommendation": (
            "Ajouter <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."
        ),
        "consequence": (
            "Sur téléphone, la page s'affiche en version bureau rétrécie — inconfortable à "
            "lire, et Google en tient compte."
        ),
    },
    "seo.sitemap.lastmod": {
        "title": "La sitemap n'a pas de dates de modification",
        "description": "",
        "recommendation": "Ajouter lastmod à chaque URL et le mettre à jour quand la page change.",
        "consequence": (
            "Après une mise à jour du site, le plan ne porte aucune trace de ce qui a changé : "
            "rien n’y permet de distinguer une page récente d’une ancienne."
        ),
    },
    "seo.clean_url.uppercase": {
        "title": "Des majuscules dans l'URL de la page",
        "description": (
            "Les URL sont sensibles à la casse : /Services et /services sont techniquement "
            "deux pages différentes."
        ),
        "recommendation": "Passer le chemin en minuscules et rediriger l'ancien en 301.",
        "consequence": (
            "La recherche peut traiter les variantes d'écriture comme des pages différentes "
            "et diviser leur autorité."
        ),
    },
    "seo.clean_url.underscore": {
        "title": "Des tirets bas dans l'URL de la page",
        "description": "",
        "recommendation": "Remplacer les tirets bas par des tirets et rediriger en 301.",
        "consequence": (
            "Les mots de l'adresse se collent, et la recherche comprend moins bien le sujet "
            "de la page."
        ),
    },
    "seo.clean_url.query": {
        "title": "Des paramètres de requête dans l'URL de la page",
        "description": (
            "Le même contenu accessible avec des paramètres différents ressemble à plusieurs "
            "pages."
        ),
        "recommendation": "Passer à des chemins propres, ou consolider les paramètres par une "
        "canonical.",
        "consequence": (
            "Le même contenu est accessible à plusieurs adresses. Les moteurs de recherche "
            "peuvent les considérer comme des pages différentes et répartir les signaux entre "
            "elles."
        ),
    },
    # ── Préparation à l'IA / LLMO ───────────────────────────────────────────
    "ai.llms_txt.missing": {
        "title": "Pas de llms.txt (possibilité facultative)",
        "description": (
            "llms.txt est un fichier markdown à la racine qui décrit brièvement le site pour les "
            "agents d'IA : ce qu'il est, ses sections clés, des liens vers les pages principales. "
            "C'est une convention émergente à l'adoption croissante, mais toujours une "
            "proposition et non une norme : le fichier est facultatif et expérimental, et son "
            "absence n'est ni un problème de classement connu ni une exigence de visibilité "
            "auprès des modèles de langage. Son absence n'empêche pas les systèmes d'IA d'accéder "
            "au site ni de le citer."
        ),
        "recommendation": (
            "À envisager surtout si le site comporte de la documentation, des références ou un "
            "autre contenu structuré. Créez /llms.txt : un H1 avec le nom du produit, une courte "
            "description et des sections `##` listant les liens vers les pages clés. Cela ne "
            "garantit rien — ni exploration, ni citation, ni classement."
        ),
        "consequence": (
            "Des services comme ChatGPT ou Perplexity se font leur idée du site à partir de ce "
            "qu'ils trouvent eux-mêmes. Le fichier peut le leur faciliter — mais son absence ne "
            "prive le site ni d'accès ni de citations."
        ),
    },
    "ai.llms_txt.no_h1": {
        "title": "llms.txt sans H1",
        "description": "",
        "recommendation": (
            "La première ligne doit être `# Nom du projet`. Le fichier lui-même reste une option "
            "expérimentale, pas une exigence."
        ),
        "consequence": (
            "Le fichier llms.txt commence sans nom, alors que la spécification l’exige à la "
            "première ligne. Qui lit le fichier ne voit pas à quel produit il se rapporte."
        ),
    },
    "ai.llms_txt.thin": {
        "title": "llms.txt est trop maigre",
        "description": "Le fichier existe mais ne donne au modèle aucune carte du site.",
        "recommendation": (
            "Ajouter des sections `##` et 5+ liens vers les pages clés. Le fichier lui-même reste "
            "une option expérimentale, pas une exigence."
        ),
        "consequence": (
            "Le fichier de synthèse existe mais ne montre pas au modèle de quoi se compose le "
            "site — il n'apporte pas grand-chose."
        ),
    },
    "ai.jsonld.missing": {
        "title": "Aucune donnée structurée détectée dans les réponses du serveur",
        "description": (
            "Ni JSON-LD ni Microdata n'ont été détectés dans les réponses analysées ; le RDFa n'a "
            "pas été évalué. Le balisage schema.org est facultatif : il donne aux machines des "
            "indices explicites sur le sens de la page et rend les pages éligibles aux résultats "
            "enrichis, mais il ne les garantit pas et n'est pas une exigence de visibilité dans "
            "les services d'IA."
        ),
        "recommendation": (
            "Si vous décidez d'ajouter un balisage, commencez par JSON-LD sur la page d'accueil : "
            "Google recommande ce format comme le plus simple à maintenir."
        ),
        "consequence": (
            "Les machines se font une idée de la page à partir du seul texte. Des indices "
            "explicites pourraient faciliter cela — mais leur absence ne coûte au site ni "
            "présence dans la recherche ni mentions."
        ),
    },
    "ai.jsonld.invalid": {
        "title": "JSON-LD invalide",
        "description": "Le bloc ld+json ne se lit pas — le balisage est entièrement ignoré.",
        "recommendation": "Réparer la syntaxe JSON du script application/ld+json.",
        "consequence": (
            "La description lisible par machine ne peut pas être lue — l'effort de l'ajouter "
            "a été perdu."
        ),
    },
    "ai.jsonld.no_type": {
        "title": "JSON-LD sans @type",
        "description": "",
        "recommendation": "Chaque entité a besoin d'un @type issu de schema.org.",
        "consequence": (
            "Les données de la page ne sont pas étiquetées — le logiciel voit des valeurs "
            "sans savoir ce qu'elles signifient."
        ),
    },
    "ai.schema.organization": {
        "title": "Aucune entité d'organisation ou de personne dans le balisage",
        "description": (
            "Des données structurées existent, mais aucune entité d'identité — Organization ou "
            "l'un de ses sous-types, Person ou WebSite — n'a été observée sur la page d'accueil "
            "ni sur les pages « à propos » de l'échantillon. Une telle entité est facultative et "
            "n'a aucune propriété obligatoire."
        ),
        "recommendation": (
            "Pour une entreprise, une institution ou une marque personnelle, envisagez le sous- "
            "type Organization applicable ou un balisage Person/WebSite sur la page d'accueil ou "
            "« à propos ». N'ajoutez que les propriétés qui vous concernent."
        ),
        "consequence": (
            "Il n'existe pas de fiche explicite lisible par machine indiquant qui est derrière le "
            "site — les machines le déduisent du texte. C'est une piste d'amélioration, pas une "
            "panne."
        ),
    },
    "ai.entity.sameas": {
        "title": "Pas de sameAs (signaux d'entité)",
        "description": (
            "sameAs relie votre marque aux bases de connaissances externes (Wikidata, "
            "LinkedIn, GitHub, Crunchbase) — le signal d'identité premier."
        ),
        "recommendation": "Ajouter sameAs avec les liens vers les profils officiels de la marque.",
        "consequence": (
            "Rien ne confirme qu'il s'agit de la même marque que sur Wikipédia ou LinkedIn, "
            "et les modèles sont moins sûrs de vos données."
        ),
    },
    "ai.schema.breadcrumb": {
        "title": "Pas de BreadcrumbList",
        "description": "Le fil d'Ariane montre au modèle où la page se situe dans la hiérarchie.",
        "recommendation": "Ajouter BreadcrumbList aux pages intérieures.",
        "consequence": (
            "On ne sait pas à quelle section du site appartient la page — le contexte se perd."
        ),
    },
    "ai.schema.faq": {
        "title": "{count} questions sur la page sans balisage FAQPage",
        "description": (
            "Les titres sont formulés en questions, mais il n'y a ni FAQPage ni QAPage. Les "
            "paires question–réponse sont le format que les modèles traitent le mieux : "
            "balisées, elles se reprennent et se citent en bloc."
        ),
        "recommendation": (
            "Envelopper les paires question–réponse existantes dans un balisage FAQPage. Rien "
            "à réécrire — le contenu est là, seul le balisage manque."
        ),
        "consequence": (
            "Les réponses sont déjà écrites sur la page, mais sous une forme que rien ne "
            "reconnaît — les modèles citent donc le concurrent qui a balisé la même chose."
        ),
    },
    "ai.schema.content_type": {
        "title": "Page de contenu sans balisage Article/Product",
        "description": "",
        "recommendation": (
            "Ajouter Article (headline, author, datePublished, dateModified) ou Product selon "
            "le type de page."
        ),
        "consequence": (
            "Une page substantielle n'est étiquetée ni article ni produit, et n'apparaît pas "
            "dans les résultats enrichis."
        ),
    },
    "ai.opengraph": {
        "title": "Balises OG manquantes : {missing}",
        "description": "",
        "recommendation": "Compléter l'OpenGraph — réseaux sociaux et robots d'IA le lisent.",
        "consequence": (
            "Les liens vers votre site partagés en messagerie et sur les réseaux n'auront ni "
            "vraie image ni description."
        ),
    },
    "ai.lang": {
        "title": "Langue de la page non déclarée",
        "description": "L'attribut lang aide à interpréter et indexer correctement le texte.",
        "recommendation": "Ajouter <html lang=\"fr\"> (ou le code de langue correspondant).",
        "consequence": (
            "La langue n'étant pas déclarée, la page peut être montrée au mauvais public ou "
            "proposée à la traduction."
        ),
    },
    "ai.opengraph.no_image": {
        "title": "Pas de og:image",
        "description": "",
        "recommendation": "Ajouter une image 1200×630 dans la balise og:image.",
        "consequence": (
            "Les liens vers votre site apparaissent en messagerie et sur les réseaux comme un "
            "rectangle vide, et moins de gens cliquent."
        ),
    },
    "ai.schema.contact.missing": {
        "title": "Pas de balisage LocalBusiness / ContactPoint",
        "description": (
            "Pour un commerce local, c'est le principal moyen de transmettre à une machine "
            "l'adresse, le téléphone et les horaires."
        ),
        "recommendation": (
            "Ajouter JSON-LD LocalBusiness avec address, telephone, openingHoursSpecification "
            "et geo."
        ),
        "consequence": (
            "Les coordonnées figurent sur le site, mais ne sont pas balisées en données "
            "structurées d’entreprise."
        ),
    },
    "ai.schema.contact.incomplete": {
        "title": "LocalBusiness sans les champs : {missing}",
        "description": "",
        "recommendation": "Compléter le balisage — ces champs alimentent les fiches et les "
        "réponses d'IA.",
        "consequence": (
            "Votre fiche dans la recherche restera incomplète : une partie des données n'a "
            "simplement pas de source."
        ),
    },
    "ai.schema.graph": {
        "title": "Les blocs JSON-LD ne sont pas reliés entre eux",
        "description": "Plusieurs blocs séparés sans @id se lisent comme des entités sans rapport.",
        "recommendation": (
            "Donner un @id à chaque bloc et les référencer entre blocs pour former un graphe."
        ),
        "consequence": (
            "La machine voit des fragments épars au lieu d'une image cohérente de l'entreprise."
        ),
    },
    "ai.twitter_card": {
        "title": "Pas de carte Twitter/X",
        "description": "",
        "recommendation": (
            "Ajouter <meta name=\"twitter:card\" content=\"summary_large_image\"> plus "
            "twitter:title/description/image."
        ),
        "consequence": (
            "Sur X et dans plusieurs messageries, votre lien apparaît sans image ni "
            "description."
        ),
    },
    # ── Aptitude à la citation ──────────────────────────────────────────────
    "llm.direct_answer": {
        "title": "Contrôle retiré : structure du début de page",
        "description": (
            "Une version antérieure de Crawldy signalait la structure du texte en début de page. "
            "Cette heuristique a depuis été retirée : elle pouvait confondre la navigation, la "
            "ponctuation et la mise en page avec la qualité du contenu. Elle n'est plus utilisée "
            "dans les nouveaux audits ni dans la notation."
        ),
        "recommendation": (
            "Aucune action n'est requise sur la seule base de cet enregistrement retiré. Évaluez "
            "la clarté de la page pour les visiteurs à l'aide des constats et preuves actuels du "
            "rapport."
        ),
        "consequence": (
            "Cet enregistrement provient d'une version antérieure de l'audit et n'affecte pas les "
            "nouveaux résultats."
        ),
    },
    "llm.structure": {
        "title": "Texte long ({word_count} mots) sans intertitres",
        "description": "Un mur de texte se découpe mal en fragments citables.",
        "recommendation": "Découper le contenu en sections H2/H3 ; ajouter listes et tableaux.",
        "consequence": (
            "Un mur de texte : dur à lire pour une personne, dur pour un modèle d'en extraire "
            "un court fragment."
        ),
    },
    "llm.about_page": {
        "title": "Pas de page À propos",
        "description": (
            "La page À propos est la source principale d'où un modèle forme son image de "
            "l'organisation et de son autorité."
        ),
        "recommendation": "Créer /about décrivant l'entreprise, son histoire et son équipe.",
        "consequence": (
            "Parmi les pages lues, aucune n’a une adresse, un titre ou un texte de lien "
            "ressemblant à une page « À propos »."
        ),
    },
    "llm.contact_page": {
        "title": "Pas de page Contact",
        "description": (
            "Les coordonnées sont un signal de confiance de base (E-E-A-T) pour la recherche "
            "et les modèles."
        ),
        "recommendation": "Ajouter /contact avec adresse, e-mail et balisage ContactPoint.",
        "consequence": (
            "Sans coordonnées visibles, le site paraît moins digne de confiance aux visiteurs "
            "comme aux moteurs."
        ),
    },
    "llm.brand_consistency": {
        "title": "Le nom de marque est incohérent",
        "description": (
            "Le nom dans le JSON-LD n'apparaît pas dans le titre de l'accueil — un modèle "
            "peut ne pas relier le site à la marque."
        ),
        "recommendation": "Employer la même graphie de marque dans title, H1 et schema.org.",
        "consequence": (
            "Le nom de marque s'écrit différemment selon les endroits, ce qui complique "
            "l'association avec vous."
        ),
    },
    "llm.stale_content": {
        "title": "Rien sur le site n'a été mis à jour depuis {years} ans",
        "description": (
            "Aucune des pages datées que nous avons lues n'a été touchée depuis {years} ans. "
            "La question ne porte pas sur une page — un guide peut rester juste des années — "
            "mais sur le site dans son ensemble."
        ),
        "recommendation": (
            "Reprendre les pages principales et rafraîchir ce qui a vieilli : prix, contenu "
            "de la prestation, travaux récents. Mettre la date de mise à jour dans le "
            "balisage, sinon personne ne saura que quelque chose a changé."
        ),
        "consequence": (
            "La date la plus récente que nous avons trouvée sur le site remonte à plusieurs "
            "années. Un lecteur n’a aucun moyen de savoir si l’information est encore valable."
        ),
    },
    "llm.stale_content.sparse": {
        "title": "Le contenu daté le plus récent a {years} ans",
        "description": (
            "Seules {dated} des {read} pages lues portent une date : il s'agit donc des dates "
            "trouvées, pas du site entier. Une page sans date n'est pas une page ancienne — "
            "beaucoup de sites n'en publient tout simplement pas."
        ),
        "recommendation": (
            "Si le contenu a bien été mis à jour, inscrivez la date de mise à jour dans le "
            "balisage : sans elle, il n’y a aucune date à lire. Sinon, commencez par les pages "
            "les plus lues."
        ),
        "consequence": (
            "Quand les seules dates visibles remontent à des années, le lecteur suppose que le "
            "site n'est plus entretenu, même si c'est faux."
        ),
    },
    "llm.authorship": {
        "title": "Page de contenu sans author/datePublished",
        "description": "Auteur et dates sont des signaux de fraîcheur et de crédibilité.",
        "recommendation": "Ajouter author, datePublished et dateModified au balisage Article.",
        "consequence": (
            "On ne voit ni qui a écrit cela ni quand, et le contenu se lit comme moins fiable."
        ),
    },
    "llm.crawler_blocked.search": {
        "title": "{count} robots de recherche IA bloqués : {crawlers}",
        "description": (
            "Ces robots indexent les pages pour qu’un assistant puisse les trouver et les citer. "
            "robots.txt les empêche d’atteindre les pages listées dans les preuves. Il s’agit de "
            "l’accès, pas de savoir si un assistant vous cite : cela, nous ne le mesurons pas."
        ),
        "recommendation": (
            "Si le blocage n’était pas voulu, autorisez ces user-agents dans robots.txt. Gardez- "
            "les distincts des robots d’entraînement : autoriser la recherche tout en refusant "
            "l’entraînement est possible."
        ),
        "consequence": (
            "Les assistants que les gens interrogent ne peuvent pas ouvrir ces pages, ce qui peut "
            "réduire vos chances d’être cité comme source."
        ),
    },
    "llm.crawler_blocked.grounding": {
        "title": "{count} robots de grounding bloqués : {crawlers}",
        "description": (
            "Ces tokens déterminent si le contenu que le fournisseur collecte sur votre site peut "
            "servir au grounding — c’est-à-dire être transmis au modèle au moment de la requête — "
            "au sein des produits d’IA de ce même fournisseur. Google-Extended concerne Gemini "
            "Apps et Vertex AI. robots.txt les empêche d’atteindre les pages des preuves. Google "
            "précise que ce token n’affecte ni l’inclusion ni le classement dans la recherche "
            "Google : ce n’est donc pas un problème de recherche."
        ),
        "recommendation": (
            "Si le blocage n’était pas voulu, autorisez ces user-agents. Notez que le même token "
            "régit aussi l’entraînement des modèles : l’autoriser ouvre les deux, et rien ne "
            "permet aujourd’hui de les séparer dans robots.txt."
        ),
        "consequence": (
            "Le contenu collecté sur ces pages peut ne pas être utilisé comme source quand Gemini "
            "répond à une question. Cela ne dit rien des autres assistants, et votre position "
            "dans la recherche Google reste inchangée."
        ),
    },
    "llm.crawler_blocked.user": {
        "title": "{count} agents d’assistant bloqués : {crawlers}",
        "description": (
            "Ces agents ouvrent une page lorsqu’une personne le demande explicitement à un "
            "assistant. robots.txt les empêche d’atteindre les pages des preuves."
        ),
        "recommendation": (
            "Si ce n’était pas voulu, autorisez ces user-agents. Ils agissent sur demande directe "
            ": les bloquer pénalise surtout quelqu’un qui voulait déjà vous lire."
        ),
        "consequence": (
            "Votre site interdit cet agent : quand un visiteur demande à l’assistant de "
            "consulter votre page, celui-ci n’a pas le droit de la récupérer. Ce que "
            "l’assistant répond à la place, nous ne l’observons pas."
        ),
    },
    "llm.crawler_blocked.training": {
        "title": "{count} robots d’entraînement IA bloqués : {crawlers}",
        "description": (
            "Ces robots collectent de la matière pour entraîner des modèles. Seuls ceux-ci sont "
            "bloqués : l’accès recherche et assistant n’est pas touché. Refuser l’entraînement "
            "est un choix légitime sur vos propres contenus ; l’entrée figure ici pour que cela "
            "reste un choix et non un oubli."
        ),
        "recommendation": (
            "Si c’était délibéré, rien à corriger. Sinon, autorisez ces user-agents : ils ne "
            "contrôlent que l’accès à l’entraînement."
        ),
        "consequence": (
            "Vos textes restent hors de l’entraînement des modèles. C’est un choix sur vos "
            "contenus, pas un défaut du site."
        ),
    },
    "llm.client_rendered": {
        "title": "Le contenu semble rendu côté client",
        "description": (
            "Le HTML statique ne contient presque pas de texte malgré beaucoup de balisage. "
            "La plupart des robots d'IA n'exécutent pas JavaScript et verront une page vide."
        ),
        "recommendation": "Activer SSR/SSG ou le prérendu pour les pages clés.",
        "consequence": (
            "Dans la réponse même du serveur, la page est presque vide : le texte n’apparaît "
            "qu’après l’exécution des scripts. Un lecteur qui ne les exécute pas voit la "
            "version vide."
        ),
    },
    # ── Vitesse ─────────────────────────────────────────────────────────────
    "perf.core_web_vitals.lcp": {
        "title": "LCP = {value}{unit} ({strategy})",
        "description": (
            "Largest Contentful Paint — temps de rendu de l'élément principal. Le seuil "
            "« bon » est {threshold}{unit}."
        ),
        "recommendation": (
            "Optimiser l'image principale (preload, format moderne) et retirer le CSS/JS "
            "bloquant le rendu."
        ),
        "consequence": (
            "Le contenu principal de la page se charge trop lentement. Les visiteurs doivent "
            "attendre plus longtemps et peuvent quitter le site avant la fin du chargement."
        ),
    },
    "perf.core_web_vitals.inp": {
        "title": "INP = {value}{unit} ({strategy})",
        "description": (
            "Interaction to Next Paint — délai de réponse à une action. Le seuil « bon » est "
            "{threshold}{unit}."
        ),
        "recommendation": "Découper les longues tâches JS et réduire l'hydratation.",
        "consequence": (
            "La page marque des temps d'arrêt sensibles après les clics — elle paraît lente."
        ),
    },
    "perf.core_web_vitals.cls": {
        "title": "CLS = {value}{unit} ({strategy})",
        "description": (
            "Cumulative Layout Shift — instabilité visuelle au chargement. Le seuil « bon » "
            "est {threshold}{unit}."
        ),
        "recommendation": "Fixer width/height des images et réserver la place des bannières et "
        "polices.",
        "consequence": (
            "Pendant le chargement des images et des polices, le texte bouge sous les yeux, ce "
            "qui rend la page pénible à lire."
        ),
    },
    "perf.core_web_vitals.ttfb": {
        "title": "TTFB = {value}{unit} ({strategy})",
        "description": (
            "Time To First Byte — temps de réponse du serveur. Le seuil « bon » est "
            "{threshold}{unit}."
        ),
        "recommendation": "Activer cache/CDN et optimiser les requêtes de base de données.",
        "consequence": (
            "Le serveur répond trop lentement, ce qui retarde le chargement de la page."
        ),
    },
    "perf.core_web_vitals.tbt": {
        "title": "TBT = {value}{unit} ({strategy})",
        "description": (
            "Total Blocking Time — blocage du thread principal. Le seuil « bon » est "
            "{threshold}{unit}."
        ),
        "recommendation": "Réduire la quantité et le poids du JavaScript.",
        "consequence": (
            "La page a l'air chargée mais ne répond pas encore — l'état le plus agaçant pour "
            "un visiteur."
        ),
    },
    "perf.mobile_gap": {
        "title": "Sur téléphone, le site est deux fois plus lent que sur ordinateur",
        "description": (
            "Nous avons mesuré le site deux fois : tel qu'un ordinateur le voit et tel qu'un "
            "téléphone le voit. Sur ordinateur il obtient {desktop} sur 100, sur téléphone "
            "{mobile}. Google classe selon la version mobile, et la plupart des gens "
            "arrivent aussi sur téléphone."
        ),
        "recommendation": (
            "Comparer les preuves ci-dessous : elles listent les métriques plus de deux fois "
            "pires en mobile. Les coupables habituels sont les images lourdes et la quantité "
            "de JavaScript, qu'un téléphone traite bien plus lentement qu'un ordinateur."
        ),
        "consequence": (
            "Vous regardez votre site sur ordinateur et tout semble bien. Vos clients le "
            "regardent sur téléphone et voient autre chose — et une partie n'attendra pas."
        ),
    },
    "perf.server_response.slow": {
        "title": "Le serveur répond lentement ({median} ms)",
        "description": (
            "Temps médian jusqu'au premier octet sur les pages explorées. Le seuil « bon » "
            "est {threshold} ms. C'est du délai avant que le navigateur puisse rien afficher."
        ),
        "recommendation": (
            "Activer le cache serveur ou CDN et chercher les requêtes lentes."
        ),
        "consequence": "Chaque visiteur attend devant un écran vide avant que rien n'apparaisse.",
    },
    "perf.server_response.very_slow": {
        "title": "Le serveur répond très lentement ({median} ms)",
        "description": (
            "Temps médian jusqu'au premier octet sur les pages explorées, contre un seuil "
            "« bon » de {threshold} ms. À cette latence, toutes les autres métriques "
            "souffrent : le navigateur ne fait qu'attendre."
        ),
        "recommendation": (
            "C'est le premier goulot à traiter. Profiler la génération des pages côté "
            "serveur, puis ajouter cache et CDN."
        ),
        "consequence": (
            "Le serveur répond trop lentement, ce qui retarde le chargement de la page."
        ),
    },
    "perf.lighthouse_score": {
        "title": "Performance Lighthouse {score} ({strategy})",
        "description": "Un score sous 90 signifie des problèmes de vitesse sensibles.",
        "recommendation": "Commencer par les premiers points du bloc opportunities.",
        "consequence": (
            "La note globale de vitesse est basse — sur une connexion lente, le site sera "
            "pénible à utiliser."
        ),
    },
    "perf.unavailable": {
        "title": "Données de vitesse non collectées",
        "description": "Le fournisseur n'a renvoyé aucune métrique — le module vitesse n'a pas "
        "été noté.",
        "recommendation": "Vérifier PSI_API_KEY ou la disponibilité du sidecar Lighthouse.",
        "consequence": (
            "La vitesse n'a pas été mesurée cette fois, la note est donc incomplète. Ce n'est "
            "pas un problème du site."
        ),
    },
    "perf.render_blocking": {
        "title": "{count} ressources bloquant le rendu dans <head>",
        "description": "Scripts synchrones et CSS retardent le premier affichage.",
        "recommendation": "Passer les scripts en async/defer et inliner le CSS critique.",
        "consequence": (
            "Votre visiteur fixe un écran vide plusieurs secondes avant que rien n'apparaisse."
        ),
    },
    "perf.images.legacy_format": {
        "title": "{count} images pourraient être servies dans un format plus léger",
        "description": (
            "JPG et PNG ne sont pas dépassés et marchent partout — mais les mêmes images en "
            "WebP ou AVIF pèsent en général nettement moins. Le gain dépend du fichier."
        ),
        "recommendation": (
            "Servir WebP/AVIF via <picture> avec repli sur le format actuel."
        ),
        "consequence": (
            "La page charge plus lentement qu'elle pourrait — surtout sur téléphone et sur "
            "connexion lente."
        ),
    },
    "perf.images.no_dimensions": {
        "title": "{count} images sans width/height",
        "description": (
            "Sans dimensions, le navigateur ne réserve pas de place — un coût CLS direct."
        ),
        "recommendation": "Fixer width et height (ou aspect-ratio) sur chaque <img>.",
        "consequence": (
            "Pendant le chargement des images, le texte saute et devient pénible à lire."
        ),
    },
    "perf.images.no_lazy": {
        "title": "Pas de lazy loading malgré de nombreuses images",
        "description": "",
        "recommendation": "Ajouter loading=\"lazy\" aux images sous la ligne de flottaison.",
        "consequence": (
            "Le navigateur télécharge toutes les images d'un coup, y compris celles que le "
            "visiteur n'atteindra peut-être jamais."
        ),
    },
    "perf.external_fonts": {
        "title": "Les polices chargent depuis des hôtes tiers : {hosts}",
        "description": (
            "Un hôte de polices externe ajoute une connexion au chemin critique de rendu."
        ),
        "recommendation": (
            "Héberger les polices soi-même et les charger via @font-face avec font-display: swap."
        ),
        "consequence": (
            "Le navigateur attend le serveur d'un tiers avant d'afficher le texte — la page "
            "reste vide plus longtemps."
        ),
    },
    "perf.third_party": {
        "title": "{count} hôtes tiers sur la page d'accueil",
        "description": (
            "Chaque hôte externe signifie une connexion, une résolution DNS et du code "
            "d'autrui."
        ),
        "recommendation": (
            "Retirer ce qui ne sert pas la conversion : widgets en trop, trackers, outils de "
            "chat."
        ),
        "consequence": (
            "Le site dépend de la vitesse et de la disponibilité de serveurs d'autrui, dont "
            "chacun peut le ralentir."
        ),
    },
    "perf.third_party.weight": {
        "title": "Le code tiers fait {share} de la page ({kb} Ko)",
        "description": (
            "Nous avons ouvert la page dans un vrai navigateur et pesé tout ce qu'elle "
            "charge. {share} du total vient de domaines tiers — widgets, chats, trackers, "
            "publicité. Chacun doit arriver avant que la page soit pleinement utilisable."
        ),
        "recommendation": (
            "Traiter les domaines les plus lourds listés dans les preuves. Charger après "
            "coup ce qui n'est pas nécessaire au-dessus de la ligne de flottaison, et "
            "supprimer ce que personne n'utilise."
        ),
        "consequence": (
            "La vitesse de votre site dépend des serveurs d'autres entreprises. Si leur "
            "journée est mauvaise, celle de vos visiteurs aussi — et vous n'y pouvez rien."
        ),
    },
    "perf.page_weight": {
        "title": "La page pèse {megabytes} Mo avant toute image",
        "description": (
            "C'est le balisage seul, sans images ni scripts : {words} mots dans un seul "
            "document. Une page ordinaire fait des dizaines ou centaines de kilo-octets. "
            "Causes habituelles : spam de commentaires, catalogue déversé dans la page ou "
            "traces d'une intrusion."
        ),
        "recommendation": (
            "Regarder ce qui occupe la place : ouvrir la page et chercher du texte que vous "
            "n'avez jamais ajouté. Si ce sont des commentaires, les couper ou les modérer ; "
            "si ce sont des liens inconnus et du charabia, vérifier le site pour intrusion "
            "et changer les mots de passe."
        ),
        "consequence": (
            "Une page de ce poids met longtemps à charger même avec une bonne connexion, et sur "
            "un téléphone elle peut ne pas s’ouvrir du tout."
        ),
    },
    "perf.page_weight.truncated": {
        "title": "La page est trop volumineuse pour être lue en entier : au moins {megabytes} Mo",
        "description": (
            "Le balisage a dépassé la limite jusqu'où nous lisons, si bien que {words} mots "
            "n'en sont même pas la totalité. Un document de cette taille n'est jamais un "
            "accident : d'ordinaire spam de commentaires, catalogue déversé ou séquelles "
            "d'une intrusion. Tout ce que nous disons d'autre sur cette page porte sur la "
            "partie lue."
        ),
        "recommendation": (
            "Vérifier la page à la main : l'ouvrir et voir d'où vient la masse. Des liens "
            "inconnus ou du texte que vous n'avez pas écrit signalent une intrusion "
            "probable — changer les mots de passe et faire vérifier le site. Supprimer les "
            "commentaires indésirables de la base, pas seulement de l'affichage."
        ),
        "consequence": (
            "Sur téléphone, on abandonnera très probablement avant la fin du chargement. Les "
            "moteurs aussi ne la lisent qu'en partie — et le lu peut se révéler être le "
            "texte de quelqu'un d'autre, pas le vôtre."
        ),
    },
    "perf.responsive_images": {
        "title": "{count} images sans tailles responsives",
        "description": "",
        "recommendation": "Ajouter srcset et sizes pour que les téléphones chargent une version "
        "réduite.",
        "consequence": (
            "Les téléphones téléchargent les photos à la même taille que les ordinateurs : la "
            "page s'ouvre plus lentement et consomme le forfait du visiteur."
        ),
    },
    # ── Protection et mesure ────────────────────────────────────────────────
    "tech.security_headers.none": {
        "title": "Aucun en-tête de protection détecté sur la réponse testée",
        "description": (
            "Aucun des en-têtes de protection vérifiés ({headers}) n'est présent sur la réponse. "
            "Ce sont des mécanismes de protection supplémentaires ; leur absence, à elle seule, "
            "n'indique pas un incident de sécurité, mais signifie généralement que la "
            "configuration n'a pas encore été traitée."
        ),
        "recommendation": (
            "Voyez avec le développeur lesquels de ces mécanismes conviennent à votre "
            "application. On commence d'habitude par X-Content-Type-Options: nosniff, le plus sûr "
            "pour la compatibilité."
        ),
        "consequence": (
            "Les protections côté navigateur pour les visiteurs ne sont pas configurées du tout. "
            "Le site n'en est pas cassé — mais il lui manque la marge que ces mécanismes offrent "
            "gratuitement."
        ),
    },
    "tech.security_headers.missing": {
        "title": "{count} protections facultatives du navigateur non détectées",
        "description": (
            "Non détectées sur la réponse testée : {headers}. Ce sont des protections "
            "supplémentaires du navigateur pour les visiteurs. Leur absence, à elle seule, "
            "n'indique pas un incident de sécurité et n'est pas une exigence directe de "
            "visibilité dans la recherche ou les systèmes d'IA."
        ),
        "recommendation": (
            "Passez la configuration en revue avec le développeur du site : les en-têtes "
            "pertinents dépendent de l'application, et les activer à l'aveugle peut casser des "
            "pages qui fonctionnent."
        ),
        "consequence": (
            "Une partie des protections standard du navigateur pour les visiteurs n'est pas "
            "activée. C'est une marge qui manque, pas une brèche : le site n'en est ni compromis "
            "ni privé de lecteurs."
        ),
    },
    "tech.crawler_blocked": {
        "title": "Le site répond aux robots par le statut {status} au lieu d'une page",
        "description": (
            "Notre agent a reçu {status} et n’a vu aucune page avec du contenu. La protection "
            "anti-bots traite souvent GPTBot, ClaudeBot et PerplexityBot de la même façon : "
            "leurs requêtes arrivent aussi d’un navigateur inconnu. Google peut, lui, passer "
            "librement — il est reconnu séparément. Nous avons testé un agent, le nôtre ; nous "
            "n’avons pas vérifié comment le site répond aux autres."
        ),
        "recommendation": (
            "Dans les réglages de protection (Cloudflare, WAF, fail2ban), autoriser les "
            "robots de recherche et d'IA par leurs user-agents et plages d'IP. Vérifier le "
            "résultat avec l'inspection d'URL de la Search Console."
        ),
        "consequence": (
            "Le site n’a pas laissé entrer notre programme : aucune page n’a pu être lue. Les "
            "mêmes réglages arrêtent souvent aussi les robots des services d’IA, mais nous "
            "n’avons pas vérifié si ce site les bloque — le reste du rapport ne repose que sur "
            "ce qui se voyait de l’extérieur."
        ),
    },
    "tech.analytics.missing": {
        "title": "Aucun système d’analyse d’audience n’a été détecté sur le site",
        "description": (
            "Nous avons ouvert la page dans un vrai navigateur et exécuté tout son "
            "JavaScript. Aucun compteur n'est apparu — ni Google Analytics ou GTM, ni "
            "Plausible, Matomo, Segment ou PostHog, ni script de mesure maison."
        ),
        "recommendation": (
            "Installer Google Analytics 4 et vérifier le site dans la Search Console. Les "
            "deux sont gratuits et se mettent en place en une heure environ."
        ),
        "consequence": (
            "Aucun script d’analyse d’audience n’a été détecté sur les pages lues."
        ),
    },
    "tech.analytics.unconfirmed": {
        "title": "Aucun tag de mesure trouvé dans le code source",
        "description": (
            "Le HTML ne porte ni Google Analytics ou GTM ni alternative. Nous avons toutefois "
            "regardé sans exécuter JavaScript, et certains tags s'injectent après le "
            "chargement — un de ceux-là nous aurait échappé."
        ),
        "recommendation": (
            "Confirmer si un tag est réellement installé, par exemple dans les rapports de "
            "l'outil lui-même. Sinon, ajouter Google Analytics 4."
        ),
        "consequence": (
            "Si rien ne mesure les visites, vous ignorez combien de gens viennent et ce "
            "qu'ils font — il n'y a rien sur quoi fonder les améliorations."
        ),
    },
    "tech.form_protection.unprotected": {
        "title": (
            "Contrôle obsolète : aucun marqueur de protection visible trouvé dans le formulaire"
        ),
        "description": (
            "Enregistrement d'un audit antérieur : aucun marqueur anti-abus visible côté client "
            "n'avait été détecté dans le formulaire. Ce contrôle n'évaluait pas les mécanismes "
            "côté serveur ni invisibles ; cet enregistrement seul ne prouve pas que le "
            "formulaire était sans protection."
        ),
        "recommendation": (
            "Aucune action distincte n'est nécessaire sur la seule base de cet enregistrement "
            "hérité. Jugez l'état des formulaires d'après les constats actuels du rapport."
        ),
        "consequence": (
            "Cet enregistrement provient d'une version antérieure de l'audit et n'affecte pas "
            "les nouveaux résultats."
        ),
    },
    "tech.form_protection.no_visible_marker": {
        "title": (
            "Aucune protection visible contre les robots n’a été détectée dans le formulaire."
        ),
        "description": (
            "Aucune protection visible n’a été trouvée dans le HTML initial ni dans le "
            "formulaire rendu. Une protection côté serveur peut néanmoins exister, sans pouvoir "
            "être confirmée par cette vérification passive."
        ),
        "recommendation": (
            "Si des envois automatiques indésirables sont un problème réel ou un risque "
            "important, demandez au développeur ou au prestataire quels contrôles anti-abus "
            "côté serveur sont en place. Choisissez des moyens proportionnés au formulaire et "
            "au risque, en tenant compte du confort et de l'accessibilité ; le CAPTCHA n'est "
            "pas obligatoire, et tout widget côté client doit s'appuyer sur une validation côté "
            "serveur."
        ),
        "consequence": (
            "Le formulaire lui-même ne montre aucun signe visible de vérification qu'un humain "
            "l'envoie. C'est une observation sur le code de la page, pas un défaut prouvé : la "
            "vérification peut s'exécuter côté serveur, où nous ne la voyons pas."
        ),
    },
    "tech.form_protection.get_method": {
        "title": (
            "{count} formulaires envoient des données avec GET"
        ),
        "title.one": "{count} formulaire envoie des données avec GET",
        "description": (
            "Un formulaire en GET place les valeurs saisies dans l'URL de la requête. Ces URL "
            "peuvent rester dans l'historique du navigateur et apparaître dans les journaux du "
            "serveur ou du proxy et dans des liens copiés. Utilisez POST pour les formulaires "
            "recueillant des données personnelles ou non publiques ; POST seul n'est ni un "
            "chiffrement ni un contrôle de sécurité complet — HTTPS reste requis séparément."
        ),
        "recommendation": (
            "Passer la méthode en post — les données de formulaire n'ont rien à faire dans "
            "la barre d'adresse."
        ),
        "consequence": (
            "Ce qu'une personne tape dans le formulaire finit dans l'adresse de la page et peut "
            "rester dans l'historique du navigateur et les journaux."
        ),
    },
    "tech.email_exposed": {
        "title": "{count} adresses e-mail exposées dans le code source",
        "description": (
            "Les liens mailto: en clair sont moissonnés par les collecteurs automatiques."
        ),
        "recommendation": "Remplacer par un formulaire de contact ou assembler l'adresse en "
        "script.",
        "consequence": (
            "Les robots à spam finiront par collecter l'adresse et le courrier indésirable "
            "arrivera. C'est une gêne plus qu'une menace : la boîte elle-même ne risque rien."
        ),
    },
    "tech.caching": {
        "title": "Les pages sont servies sans règles de cache",
        "description": "Ni Cache-Control, ni ETag, ni Last-Modified sur {count} pages vérifiées.",
        "recommendation": "Configurer Cache-Control et ETag au niveau serveur ou CDN.",
        "consequence": (
            "Le navigateur retélécharge la page à chaque fois, même quand rien n'a changé."
        ),
    },
    "tech.soft_404": {
        "title": "Une page inexistante renvoie le statut {status}",
        "description": (
            "Le serveur répond par un succès pour une adresse qui n'existe pas. On attend 404."
        ),
        "recommendation": "Configurer le serveur pour renvoyer 404 aux adresses inexistantes.",
        "consequence": (
            "La page répond « tout va bien » alors qu’elle affiche une erreur. Tout ce qui se "
            "fie au code de réponse — un navigateur, un moteur de recherche, notre propre "
            "programme — la prend pour une vraie page."
        ),
    },
    "tech.host_canonical": {
        "title": "Le site s'ouvre aussi sur {host}",
        "description": (
            "Les deux variantes d'hôte servent du contenu et ne redirigent pas vers une seule."
        ),
        "recommendation": (
            "Mettre en place une redirection 301 permanente de l'hôte secondaire vers le "
            "principal."
        ),
        "consequence": (
            "Le même site existe à deux adresses, et la recherche divise son autorité entre "
            "elles au lieu de la compter en entier."
        ),
    },
    "tech.nap.phone_mismatch": {
        "title": "Le site affiche {count} numéros de téléphone différents",
        "description": "Des pages différentes affichent des numéros différents.",
        "recommendation": "Garder un numéro, ou dire explicitement quel numéro sert à quoi.",
        "consequence": (
            "Plusieurs numéros de téléphone ont été trouvés, mais aucun n’est identifié "
            "comme numéro de contact principal."
        ),
    },
    "tech.nap.phone_not_e164": {
        "title": "{count} numéros ne sont pas au format international",
        "description": (
            "Un lien tel: doit porter le plus, l'indicatif du pays et le numéro — sans "
            "espaces, parenthèses ni tirets. Actuellement, par exemple : {example}."
        ),
        "recommendation": (
            "Normaliser chaque tel: au format international : un plus, l'indicatif, puis les "
            "chiffres sans séparateurs. Le texte visible peut rester lisible."
        ),
        "consequence": (
            "Sur téléphone, un tel numéro ne se compose pas toujours d'une seule pression."
        ),
    },
    "tech.nap.schema_mismatch": {
        "title": "Le téléphone du balisage ne correspond pas à celui des pages",
        "description": (
            "Le JSON-LD transmet un numéro aux machines pendant que le site en montre un "
            "autre aux gens."
        ),
        "recommendation": "Aligner telephone des données structurées sur le numéro de vos "
        "contacts.",
        "consequence": (
            "Votre fiche dans la recherche peut afficher le mauvais numéro — les appels "
            "iront au mauvais endroit."
        ),
    },
    "seo.meta_description.too_long": {
        "title": "Seuls les {visible} premiers caractères sur {length} sont affichés",
        "description": (
            "La recherche tronque le reste. Une description plus longue n'est pas une "
            "erreur — les robots d'IA la lisent en entier — mais dans les résultats, les "
            "gens ne voient que le début."
        ),
        "recommendation": (
            "S'assurer que l'essentiel et l'appel à l'action tiennent dans les {visible} "
            "premiers caractères."
        ),
        "consequence": (
            "Si le message principal est en fin de description, personne ne le lit dans la "
            "recherche."
        ),
    },
    "seo.meta_description.too_short": {
        "title": "La description est trop maigre ({length} caractères)",
        "description": "Sous {min} caractères, elle ne peut ni expliquer ni convaincre.",
        "recommendation": "Dire ce qu'est le service, pour qui, et quoi faire ensuite.",
        "consequence": (
            "Il n'y a presque rien sous votre résultat — les gens choisissent le concurrent "
            "qui a écrit quelque chose."
        ),
    },
    "llm.unstated_facts.offering": {
        "title": (
            "Les pages lues ne disent pas ce que vend l’entreprise"
        ),
        "description": (
            "Après lecture du site entier, aucun produit ni service concret ne peut être "
            "nommé. Les formules comme « des solutions pour votre entreprise » ne répondent "
            "pas à la question avec laquelle arrive un acheteur."
        ),
        "recommendation": (
            "Dire sur l'accueil, en une phrase, ce que vous vendez — pas « des solutions "
            "clé en main » mais « nous installons la vidéosurveillance »."
        ),
        "consequence": (
            "Les pages que nous avons lues ne disent pas ce que vous vendez. Ni une personne ni "
            "un service de recherche ou d’IA n’a de source pour cela."
        ),
    },
    "llm.unstated_facts.location": {
        "title": "Le site ne dit jamais où vous opérez",
        "description": (
            "Ni ville, ni région, ni pays nulle part sur le site. Pour une activité de "
            "proximité, c'est le premier filtre d'un acheteur : il cherche quelqu'un près de "
            "chez lui."
        ),
        "recommendation": (
            "Mettre ville et adresse dans le pied de page de chaque page et sur la page "
            "contact. Si vous couvrez plus large, lister les localités desservies."
        ),
        "consequence": (
            "À la question « qui fait ça dans ma ville », le site n'a rien à répondre : il "
            "ne dit jamais où vous êtes. Vous serez donc moins souvent proposé précisément "
            "aux acheteurs pour qui venir chez vous serait commode."
        ),
    },
    "llm.unstated_facts.pricing": {
        "title": "Le site ne dit jamais combien ça coûte",
        "description": (
            "Ni prix, ni grille tarifaire, ni proposition claire d'établir un devis. Le prix "
            "est la première question d'un acheteur, et le site n'y répond pas."
        ),
        "recommendation": (
            "Publier les prix, ou au moins une fourchette « de–à ». Si chaque prestation se "
            "chiffre au cas par cas, le dire franchement et donner un formulaire de devis."
        ),
        "consequence": (
            "L'acheteur vous compare aux concurrents et vous écarte en premier : leur prix "
            "est visible, pas le vôtre. Ne rien dire du prix se lit comme « cher »."
        ),
    },
    "ai.jsonld.partial": {
        "title": "Observation retirée : le balisage n'était pas sur toutes les pages",
        "description": (
            "Une version antérieure de Crawldy signalait la couverture partielle comme un défaut. "
            "Cette observation a été retirée : le balisage n'a pas à figurer sur chaque page, et "
            "les audits récents ne traitent pas la couverture partielle comme un problème."
        ),
        "recommendation": (
            "Aucune action n'est requise sur la seule base de cet enregistrement retiré."
        ),
        "consequence": (
            "Cet enregistrement provient d'une version antérieure de l'audit et n'affecte pas les "
            "nouveaux résultats."
        ),
    },
    "tech.demo_content": {
        "title": "Le contenu de démonstration du thème est encore sur le site",
        "description": (
            "{count} signes trouvés qu'une partie du site est la démo d'un thème jamais "
            "remplacé : personnes inventées dans l'équipe, numéro de téléphone factice, "
            "e-mail sur le domaine de l'éditeur du thème, ou gabarits du constructeur de "
            "pages restés accessibles publiquement."
        ),
        "recommendation": (
            "Supprimer ou remplacer les pages et contacts de démo. Garder les gabarits du "
            "constructeur hors de l'index."
        ),
        "consequence": (
            "Les visiteurs voient des gens qui ne travaillent pas pour vous et des contacts "
            "que vous n'avez pas. Cela abîme la confiance plus fort que des défauts "
            "techniques — et moteurs comme assistants lisent ces pages comme la vérité sur "
            "votre entreprise."
        ),
    },
    "a11y.blocking": {
        "title": "{count} obstacles qui empêchent d'utiliser le site",
        "description": (
            "Il ne s'agit pas d'esthétique. Zoom bloqué, bouton ou lien sans nom, champ sans "
            "étiquette — la personne ne peut simplement pas faire ce pour quoi elle est "
            "venue : lire sur téléphone, toucher, remplir le formulaire."
        ),
        "recommendation": (
            "Retirer user-scalable=no du viewport, donner aux boutons et liens un texte ou "
            "un aria-label, étiqueter les champs de formulaire."
        ),
        "consequence": (
            "Certains visiteurs risquent de ne pas pouvoir utiliser certaines parties de la "
            "page. Des problèmes d’accessibilité concernent des boutons, des liens ou des "
            "champs de formulaire."
        ),
    },
    "a11y.failures": {
        "title": "{count} remarques d'accessibilité",
        "description": (
            "Un passage automatique de Lighthouse a trouvé des endroits où le contenu est "
            "plus dur à lire ou à atteindre au clavier. Personne ne vérifie automatiquement "
            "la pleine conformité — cela demande des tests manuels."
        ),
        "recommendation": (
            "Parcourir la liste dans les preuves. La plupart se corrigent avec des attributs "
            "de balisage, sans rien redessiner."
        ),
        "consequence": (
            "Les personnes qui voient mal, sur de vieux téléphones ou au clavier plutôt "
            "qu'à la souris trouvent le site plus dur à utiliser qu'il ne devrait l'être."
        ),
    },
    # ── Мовні версії ───────────────────────────────────────────────────────
    "seo.hreflang_invalid": {
        "title": "{count} versions déclarées utilisent une valeur que Google refuse : {values}",
        "description": (
            "Google accepte ici une forme plus étroite qu'on ne le croit : une langue selon ISO "
            "639-1, éventuellement une écriture selon ISO 15924, éventuellement un pays selon "
            "ISO 3166-1 Alpha 2 — dans cet ordre — plus le réservé x-default. D'où zh-Hant et "
            "zh-Hans-US valides, en_US, en-UK et en-US-Latn non. La preuve indique ce qui "
            "cloche dans chaque valeur ; l'erreur la plus fréquente est un code pays à la place "
            "de la langue."
        ),
        "recommendation": (
            "Corrigez chaque valeur listée dans la preuve : trait d'union et non tiret bas, "
            "en-GB et non uk ou en-UK, la langue avant le pays. La preuve note aussi lequel des "
            "trois emplacements porte chaque valeur."
            "Un cas n'a aucune forme valide : une langue sans code ISO 639-1 (asturien, "
            "cachoube et autres ; signalés not_a_language dans la preuve). Elle ne peut "
            "être représentée par aucun code de langue hreflang valide, car la grammaire "
            "de Google n'en possède pas. Ne substituez pas le code d'une autre langue : "
            "une page en asturien déclarée comme espagnole trompe à la fois les moteurs "
            "de recherche et les lecteurs. Supprimez la valeur et laissez cette version "
            "sans hreflang."
            "Si la même valeur figure aussi dans les ensembles réciproques des autres versions "
            "linguistiques, supprimez-la également : sinon la moitié du site continuera de "
            "pointer vers un code invalide."
        ),
        "consequence": (
            "Les marqueurs de versions linguistiques sont écrits sous une forme que les moteurs "
            "de recherche n’acceptent pas : ils restent sans effet. Les pages destinées à "
            "d’autres pays ne sont pas déclarées."
        ),
    },
    "seo.hreflang_reciprocity.self": {
        "title": "La page déclare {count} versions sans jamais se nommer elle-même",
        "description": (
            "Un ensemble de versions déclarées doit inclure la page qui le porte, en pointant "
            "vers sa propre adresse. Sans cette auto-référence l'ensemble est incomplet et peut "
            "être écarté. Une entrée x-default pointant ici ne compte pas : elle signifie « "
            "venez ici si rien ne correspond »."
        ),
        "recommendation": (
            "Ajoutez, à côté des autres, une entrée pour la langue de cette page pointant vers "
            "cette adresse exacte. N'importe lequel des trois emplacements convient : la page "
            "elle-même, l'en-tête HTTP ou le plan du site."
        ),
        "consequence": (
            "La page énumère les autres versions existantes sans jamais dire laquelle elle est, "
            "si bien que le groupe entier peut être écarté et les visiteurs envoyés au mauvais "
            "endroit."
        ),
    },
    "seo.hreflang_reciprocity.return": {
        "title": "{count} des {checked} versions ouvertes ne renvoient pas vers cette page",
        "description": (
            "La déclaration ne vaut que si les deux côtés la font : si cette page nomme une "
            "autre comme sa version, celle-ci doit nommer celle-ci en retour. Nous avons ouvert "
            "{checked} des {declared} adresses déclarées ici et n'avons trouvé aucun renvoi sur "
            "celles listées dans la preuve. Sur celles que nous n'avons pas ouvertes, nous "
            "n'affirmons rien."
        ),
        "recommendation": (
            "Sur chaque page nommée dans la preuve, ajoutez l'entrée qui renvoie vers cette "
            "adresse. Si elles sortent du même gabarit, c'est en général une seule "
            "modification."
        ),
        "consequence": (
            "Le lien entre les deux pages n'est déclaré que d'un côté ; les moteurs de "
            "recherche peuvent donc les traiter comme deux pages distinctes qui se "
            "concurrencent au lieu d'une même page pour deux publics."
        ),
    },
    "seo.hreflang_conflict.duplicate": {
        "title": "{value} est déclaré pour {count} adresses différentes",
        "description": (
            "Une valeur ne peut désigner qu'une seule adresse. Quand elle en désigne plusieurs, "
            "on ne sait laquelle était visée, et Google peut écarter toutes les déclarations de "
            "la page, pas seulement celle qui se contredit. La preuve liste les adresses "
            "concurrentes et l'origine de chacune."
        ),
        "recommendation": (
            "Gardez une adresse par valeur. Regardez d'abord l'origine dans la preuve : si deux "
            "des trois emplacements se contredisent, le plus ancien vient souvent d'une "
            "configuration précédente et peut disparaître."
        ),
        "consequence": (
            "La page donne deux réponses différentes à la même question, et les moteurs de "
            "recherche préfèrent écarter tout le réglage plutôt que deviner lequel comptait."
        ),
    },
    "seo.hreflang_conflict.x_default": {
        "title": "{value} désigne {count} adresses différentes",
        "description": (
            "x-default désigne la page servie lorsqu'aucune des versions déclarées ne "
            "correspond au visiteur. En déclarer plusieurs laisse ce cas indéfini — or c'est le "
            "seul cas où l'on tranche pour tous ceux que vous n'aviez pas prévus."
        ),
        "recommendation": (
            "Choisissez une seule adresse de repli et retirez les autres. C'est en général une "
            "page qui tranche d'elle-même : sélecteur de pays ou de variante."
        ),
        "consequence": (
            "Un visiteur venu d'un pays que vous n'aviez pas prévu peut arriver sur l'une ou "
            "l'autre des deux pages, et ce n'est plus vous qui décidez laquelle."
        ),
    },
    "seo.hreflang_conflict.canonical": {
        "title": "La page déclare ses versions tout en envoyant la recherche vers {canonical}",
        "description": (
            "Une page participant à un ensemble de versions déclarées doit être son propre "
            "canonical. Ici le canonical nomme une autre adresse : les déclarations décrivent "
            "donc une page que le site lui-même demande de ne pas montrer. Les deux "
            "instructions se contredisent, et Google tranche à sa manière."
        ),
        "recommendation": (
            "Décidez quelle page fait foi : faites pointer le canonical vers cette adresse, ou "
            "déplacez les déclarations vers la page que le canonical nomme."
        ),
        "consequence": (
            "La page affirme deux choses opposées à la fois : qu'elle existe pour d'autres "
            "pays, et que ce n'est pas elle qu'il faut montrer. Les moteurs de recherche "
            "tranchent seuls, rarement comme vous l'auriez voulu."
        ),
    },
    "seo.hreflang_broken.unreachable": {
        "title": "{count} versions déclarées n'ont pas renvoyé de page en état de marche",
        "description": (
            "Nous avons ouvert ces adresses nous-mêmes et le serveur n'a pas répondu "
            "correctement. La preuve porte chaque adresse et le code renvoyé : c'est mesuré, "
            "pas supposé. Les adresses que nous n'avons pas ouvertes n'y figurent pas."
        ),
        "recommendation": (
            "Pour chaque adresse de la preuve, corrigez-la vers la page qui existe aujourd'hui "
            "ou retirez-la de l'ensemble. La cause la plus courante est une adresse héritée "
            "d'une version antérieure du site."
        ),
        "consequence": (
            "Une partie des adresses proposées aux visiteurs d'autres pays ne mène nulle part. "
            "Celui qu'on y envoie voit une erreur au lieu de votre page."
        ),
    },
    "seo.hreflang_broken.noindex": {
        "title": "{count} versions déclarées sont fermées à la recherche",
        "description": (
            "L'adresse est déclarée comme une version à montrer et porte en même temps un "
            "noindex, l'instruction de ne pas la montrer. Les deux s'annulent. Nous avons lu "
            "l'instruction sur la page elle-même et la preuve la cite."
        ),
        "recommendation": (
            "Décidez ce qui était voulu : retirez le noindex de ces pages, ou sortez-les de "
            "l'ensemble des versions déclarées."
        ),
        "consequence": (
            "Une page est proposée comme celle d'un autre pays tout en étant marquée comme une "
            "page à ne pas faire apparaître dans les recherches. Les visiteurs de ce pays n'y "
            "seront pas envoyés."
        ),
    },
    "seo.hreflang_missing": {
        "title": "Des pages existent en {count} langues ({languages}) sans version déclarée",
        "description": (
            "Les pages que nous avons lues déclarent des langues différentes, et nulle part il "
            "n'est dit qu'elles sont versions les unes des autres : ni sur les pages, ni dans "
            "un en-tête HTTP, ni dans le plan du site. Traductions du même contenu ou sections "
            "distinctes, cela ne se voit pas de l'extérieur — d'où une raison de vérifier "
            "plutôt qu'une conclusion. La preuve range les adresses par langue."
        ),
        "recommendation": (
            "S'il s'agit de versions du même contenu, déclarez-le. Un seul des trois "
            "emplacements suffit — Google les tient pour équivalents — et pour des pages "
            "générées le plan du site revient le moins cher."
        ),
        "consequence": (
            "Quelqu'un qui cherche en français peut se voir présenter la page écrite dans une "
            "autre langue, parce que rien n'indique aux moteurs de recherche que ces pages vont "
            "ensemble."
        ),
    },
    # ── Перенаправлення ────────────────────────────────────────────────────
    "seo.redirect_chain": {
        "title": "L'adresse passe par {count} redirections avant que la page s'ouvre",
        "description": (
            "Le navigateur a demandé une adresse et a été renvoyé plus d'une fois avant que "
            "quoi que ce soit lui soit servi. La preuve porte chaque saut avec son code et "
            "l'adresse visée. Une redirection est ordinaire — http vers https, ou une ancienne "
            "adresse vers celle qui la remplace ; une chaîne signifie le plus souvent deux "
            "règles empilées au fil du temps, chacune écrite sans connaître l'autre."
        ),
        "recommendation": (
            "Faites pointer la première règle directement sur l'adresse finale, pour que la "
            "chaîne se réduise à une seule étape. Si la preuve nomme des pages qui pointent "
            "vers l'adresse de départ, corrigez aussi ces liens : la redirection disparaît "
            "alors du chemin au lieu d'être raccourcie."
        ),
        "consequence": (
            "Chaque saut supplémentaire est un aller-retour de plus vers le serveur avant que "
            "rien n'apparaisse : la page commence à se charger plus tard que nécessaire. Cela "
            "se voit surtout sur un téléphone."
        ),
    },
    "seo.redirect_loop.repeated": {
        "title": "Le chemin de redirection revient sur une adresse déjà visitée",
        "description": (
            "Une adresse apparaît plusieurs fois sur le chemin de la page : le parcours est "
            "revenu sur lui-même avant d'aboutir. La preuve porte la séquence entière et les "
            "adresses répétées. Ce parcours a abouti, la page était donc atteignable — mais les "
            "règles décrivent un cercle, et une petite modification le referme."
        ),
        "recommendation": (
            "Comparez les règles d'où sort l'adresse répétée de la preuve. En général deux "
            "d'entre elles s'envoient le trafic l'une à l'autre, et seul l'ordre d'évaluation "
            "maintient le cercle ouvert."
        ),
        "consequence": (
            "L'adresse ramène le visiteur là où il était déjà passé. Cela fonctionne "
            "aujourd'hui, mais une petite modification de l'une des règles suffit pour que la "
            "page cesse de s'ouvrir."
        ),
    },
    "seo.redirect_loop.limit": {
        "title": "{url} a continué de rediriger sans jamais livrer de page",
        "description": (
            "Nous avons suivi {followed} redirections depuis cette adresse et nous nous sommes "
            "arrêtés sans page. C'est tout ce que nous pouvons affirmer : la séquence ne s'est "
            "pas terminée en autant d'étapes. Où elle tournait, et même si elle tournait, nous "
            "l'ignorons : aucune page ne nous a jamais été rendue."
        ),
        "recommendation": (
            "Ouvrez cette adresse dans un navigateur et regardez la barre d'adresse. Si elle se "
            "stabilise, la chaîne est seulement longue et la première règle doit viser "
            "l'adresse finale ; si elle continue de changer, deux règles s'envoient le trafic "
            "l'une à l'autre."
        ),
        "consequence": (
            "Cette adresse ne s'ouvre pas du tout. Qui suit un lien vers elle — un visiteur, ou "
            "un moteur de recherche qui tente de lire la page — ne reçoit rien."
        ),
    },
    "seo.redirect_target": {
        "title": "La redirection aboutit à une adresse qui a répondu {status}",
        "description": (
            "La règle fonctionne et renvoie le navigateur, mais la destination ne rend pas de "
            "page. Nous avons lu le code nous-mêmes ; la preuve porte le chemin complet. La "
            "cause n'est en général pas la redirection mais la destination : la page a été "
            "retirée après la règle qui pointe vers elle."
        ),
        "recommendation": (
            "Faites pointer la règle vers une adresse qui existe aujourd'hui, ou supprimez-la. "
            "Si la preuve nomme des pages liant vers l'adresse de départ, mettez aussi ces "
            "liens à jour."
        ),
        "consequence": (
            "L'adresse mène le visiteur vers une page d'erreur. Comme la redirection elle-même "
            "fonctionne, le site paraît traiter correctement cette adresse jusqu'au moment où "
            "quelqu'un voit l'échec."
        ),
    },
    # ── Узгодженість карти сайту ───────────────────────────────────────────
    "seo.sitemap_consistency.error": {
        "title": "{count} adresses du sitemap ont répondu par une erreur à l'ouverture",
        "description": (
            "Le sitemap demande aux moteurs de recherche de trouver ces adresses, et le serveur "
            "n'y a rendu aucune page. Nous avons ouvert chacune nous-mêmes ; la preuve porte "
            "l'adresse et le code renvoyé. Sur {declared} adresses déclarées, nous en avons "
            "vérifié {checked} : le reste, nous ne l'avons pas ouvert, et il ne compte ici "
            "ni dans un sens ni dans l'autre."
        ),
        "recommendation": (
            "Retirez ces adresses du sitemap, ou rétablissez les pages qui s'y trouvaient. Un "
            "sitemap produit depuis la base continue souvent de lister des pages supprimées "
            "depuis l'interface."
        ),
        "consequence": (
            "Vous désignez aux moteurs de recherche des pages qui ne s'ouvrent pas. L'effort "
            "est perdu, et qui atteint l'une de ces adresses autrement voit une erreur."
        ),
    },
    "seo.sitemap_consistency.redirects": {
        "title": "{count} adresses du sitemap redirigent ailleurs",
        "description": (
            "Un sitemap devrait porter l'adresse où la page se trouve finalement, non une "
            "adresse qui y renvoie. Chacune de celles-ci fait suivre le navigateur ; la preuve "
            "donne la destination et le nombre de sauts. Sur {declared} adresses déclarées, "
            "{checked} vérifiées."
        ),
        "recommendation": (
            "Remplacez chaque entrée par l'adresse à laquelle elle aboutit — la preuve porte "
            "les deux. Si le sitemap est produit automatiquement, le générateur lit sans doute "
            "une adresse enregistrée avant le dernier déplacement."
        ),
        "consequence": (
            "La liste d'adresses que vous publiez n'est pas celle où les visiteurs arrivent "
            "réellement. Chacune coûte une étape de plus avant l'affichage de la page."
        ),
    },
    "seo.sitemap_consistency.noindex": {
        "title": "{count} adresses du sitemap sont fermées à la recherche",
        "description": (
            "Ces pages portent une instruction noindex et figurent aussi dans le sitemap. Les "
            "deux disent le contraire : l'une demande de trouver la page, l'autre de ne pas "
            "l'afficher. Nous avons lu l'instruction sur la page elle-même ; la preuve note si "
            "elle était dans la réponse du serveur ou est apparue après les scripts. Vérifiées "
            ": {checked} sur {declared} adresses déclarées."
        ),
        "recommendation": (
            "Décidez ce qui était voulu. Si la page ne doit pas apparaître dans les recherches, "
            "sortez-la du sitemap ; si elle le doit, retirez le noindex."
        ),
        "consequence": (
            "Votre site demande que ces pages soient trouvées et, sur ces mêmes pages, qu'elles "
            "ne soient pas affichées. Quelle que soit celle qui l'emporte, l'une des deux ne "
            "fait pas ce que vous vouliez."
        ),
    },
    "seo.sitemap_consistency.canonical": {
        "title": "{count} adresses du sitemap désignent une autre adresse comme principale",
        "description": (
            "Chacune de ces pages déclare un canonical différent de l'adresse listée dans le "
            "sitemap. Le sitemap devrait porter l'adresse que la page elle-même tient pour "
            "principale. La preuve montre les deux, et si l'adresse canonique figure aussi dans "
            "le sitemap. Nous ne prétendons pas savoir quelle adresse un moteur retiendra. "
            "Vérifiées : {checked} sur {declared}."
        ),
        "recommendation": (
            "Inscrivez l'adresse canonique dans le sitemap à la place. Si la preuve montre "
            "qu'elle en est absente, l'y ajouter est en général la correction."
        ),
        "consequence": (
            "Le sitemap et les pages ne s'accordent pas sur l'adresse réelle. Vous demandez "
            "qu'une version soit trouvée tandis que la page en désigne une autre."
        ),
    },
    "seo.sitemap_consistency.not_for_search": {
        "title": "{count} pages de service figurent dans le sitemap",
        "description": (
            "Les pages de connexion, les paniers et les archives ne sont pas l'objet d'un "
            "sitemap : on y liste les pages qui méritent d'être trouvées. La preuve nomme "
            "chaque adresse et la catégorie qui lui a été attribuée. Vérifiées : {checked} sur "
            "{declared} adresses "
            "déclarées."
        ),
        "recommendation": (
            "Excluez ces sections du sitemap. La plupart des générateurs ont un réglage pour "
            "cela, généralement désactivé par défaut."
        ),
        "consequence": (
            "La liste de pages que vous présentez comme dignes d'intérêt contient des pages que "
            "personne ne cherche. Cela rend la liste moins utile sans aider celles qui "
            "comptent."
        ),
    },
    # ── Текст посилань ─────────────────────────────────────────────────────
    "seo.anchor_text": {
        "title": (
            "{count} libellés de liens mènent chacun vers plusieurs pages différentes ({links} "
            "liens)"
        ),
        "description": (
            "Le même libellé sert à des liens qui mènent à des endroits différents. La preuve "
            "porte chaque formulation, combien de liens la portent et combien de destinations "
            "distinctes ils atteignent. La navigation et le pied de page sont exclus — un "
            "\"Tarifs\" répété dans l'en-tête est un repère, non un défaut — de même que les "
            "pages dont nous n'avons pas pu établir la langue. Les recommandations de Google "
            "citent elles-mêmes \"click here\", \"read more\", \"website\" et \"article\" comme "
            "exemples de textes peu parlants."
        ),
        "recommendation": (
            "Donnez à chaque lien un texte qui nomme sa destination : \"Voir les tarifs 2026\" "
            "plutôt que \"En savoir plus\". Si la formulation vient d'un gabarit — les cartes "
            "d'articles en sont le cas courant —, une seule modification y suffit pour que le "
            "titre de la page cible passe dans le lien. N'entassez pas de termes : écrivez "
            "comme une personne le dirait."
        ),
        "consequence": (
            "Le lecteur ne voit pas où mène un lien avant de cliquer : il devine ou passe son "
            "chemin. Sur une page de libellés identiques, ceux-ci cessent d'être un moyen de "
            "choisir."
        ),
    },
    # ── Змішаний вміст ─────────────────────────────────────────────────────
    "tech.mixed_content.blockable": {
        "title": (
            "{count} ressources non sécurisées sur {pages} pages sécurisées risquent de ne "
            "pas charger"
        ),
        "description": (
            "Ces pages sont servies par une connexion sécurisée mais réclament des scripts, "
            "des feuilles de style ou des cadres intégrés par une connexion non sécurisée. "
            "Les navigateurs ne corrigent pas discrètement cette catégorie : ils refusent "
            "la requête au lieu de l'exécuter, et ce que faisait la ressource peut donc "
            "simplement ne pas avoir lieu. La preuve porte chaque ressource, son type, si "
            "nous avons vu le navigateur la demander réellement, et si elle vous appartient "
            "ou à un tiers."
        ),
        "recommendation": (
            "Faites pointer chacune vers son adresse sécurisée : la plupart des "
            "fournisseurs en servent une depuis des années, et la correction tient souvent "
            "à un caractère. Si une ressource tierce n'a aucune adresse sécurisée, "
            "remplacez ou supprimez la dépendance : ce fournisseur n'est pas utilisable sur "
            "une page sécurisée."
        ),
        "consequence": (
            "Une partie de la page réclame quelque chose que le navigateur n'ira pas "
            "chercher par une connexion non protégée. Ce qui en dépendait — un formulaire, "
            "un widget, une mesure — peut cesser de fonctionner sans bruit pour tous les "
            "visiteurs."
        ),
    },
    "tech.mixed_content.upgradeable": {
        "title": (
            "{count} images ou médias sur {pages} pages sécurisées sont demandés sans "
            "protection"
        ),
        "description": (
            "Les navigateurs modernes réécrivent eux-mêmes ces requêtes vers l'adresse "
            "sécurisée, si bien que le visiteur ne remarque généralement rien. Cela ne veut "
            "pas dire que la configuration est correcte : la réécriture ne tient que tant "
            "que la version sécurisée du fichier existe, alors que la page contient "
            "toujours l'adresse non protégée. La preuve note ce que nous avons vu le "
            "navigateur faire, et dit clairement où nous n'avons pas regardé."
        ),
        "recommendation": (
            "Inscrivez l'adresse sécurisée dans la page plutôt que de compter sur la "
            "correction du navigateur. Si les ressources viennent d'un gabarit ou d'une "
            "médiathèque, une simple recherche-remplacement sur le contenu enregistré "
            "suffit en général."
        ),
        "consequence": (
            "La page fonctionne aujourd'hui parce que les navigateurs corrigent ces "
            "adresses en silence. Le jour où l'un de ces fichiers manquera à l'adresse "
            "corrigée, l'image ou la vidéo disparaîtra sans le moindre avertissement."
        ),
    },
    "tech.mixed_content.download": {
        "title": (
            "{count} téléchargements sur {pages} pages sécurisées passent par un lien non "
            "sécurisé"
        ),
        "description": (
            "Un fichier proposé au téléchargement depuis une page sécurisée est récupéré "
            "par une connexion non protégée. Les navigateurs traitent ce cas à part et "
            "peuvent bloquer le téléchargement ou avertir la personne avant qu'il commence. "
            "La preuve porte chaque fichier."
        ),
        "recommendation": (
            "Servez ces fichiers depuis l'adresse sécurisée du même site. S'ils se trouvent "
            "sur un autre hôte dépourvu d'adresse sécurisée, déplacez-les ou hébergez-les "
            "vous-même."
        ),
        "consequence": (
            "Qui clique sur ces fichiers peut recevoir un avertissement, ou rien du tout, "
            "sur une page qui paraît par ailleurs parfaitement fiable."
        ),
    },
    "tech.mixed_content.runtime": {
        "title": (
            "{count} requêtes non sécurisées sur {pages} pages "
            "viennent de scripts, pas du code"
        ),
        "description": (
            "Nous avons ouvert ces pages dans un navigateur et observé des requêtes vers "
            "des adresses non protégées qui n'apparaissent nulle part dans le code. Quelque "
            "chose qui s'exécute sur la page construit ces adresses au fil de l'eau — le "
            "plus souvent un script de mesure ou de widget. La preuve porte les adresses "
            "enregistrées."
        ),
        "recommendation": (
            "Trouvez le script qui construit chaque adresse — l'hôte indiqué dans la preuve "
            "nomme en général le fournisseur — puis changez sa configuration ou "
            "remplacez-le. Chercher ces adresses dans le code ne donnera rien : elles sont "
            "assemblées à l'exécution."
        ),
        "consequence": (
            "La page sort vers l'extérieur par une connexion non protégée tout en se "
            "présentant comme sécurisée. Rien dans le code ne le montre, donc cela survit à "
            "toute revue qui se contente de lire le code."
        ),
    },
    # ── Однаковий вміст під різними адресами ───────────────────────────────
    "seo.duplicate_content.unconsolidated": {
        "title": "{count} groupes d'adresses renvoient le même contenu ({pages} pages)",
        "description": (
            "Chaque groupe ci-dessous réunit des adresses dont le contenu coïncide une fois "
            "écarté le texte de navigation et de pied de page. Rien sur le site n'indique "
            "laquelle est la principale : ni redirection entre elles, ni canonical "
            "désignant un seul membre. Le contenu dupliqué est courant et n'enfreint aucune "
            "règle ; les moteurs de recherche regroupent ces pages d'eux-mêmes et en "
            "choisissent une, et laquelle, nous ne pouvons pas vous le dire. La preuve "
            "porte chaque groupe et ce que déclare chaque membre."
        ),
        "recommendation": (
            "Décidez ce que ces adresses doivent être. S'il s'agit d'une seule page, gardez "
            "une adresse et renvoyez-y les autres, ou faites déclarer le même canonical à "
            "tous les membres. S'il s'agit de pages distinctes, donnez-leur un contenu "
            "réellement différent. Faites ensuite pointer les liens internes et le sitemap "
            "vers la version retenue."
        ),
        "consequence": (
            "La même page existe à plusieurs adresses et rien ne dit laquelle compte. Les "
            "visites, les liens et toute mesure se répartissent entre elles, et vous ne "
            "voyez pas où les gens sont réellement arrivés."
        ),
    },
    "seo.duplicate_content.conflicting": {
        "title": "{count} groupes de pages identiques ne s'accordent pas sur l'adresse principale",
        "description": (
            "Ces adresses renvoient le même contenu, et les pages elles-mêmes désignent des "
            "adresses principales différentes — ou une qui ne fait pas partie du groupe. "
            "C'est une contradiction interne au site, pas une infraction : les moteurs de "
            "recherche trancheront à leur manière, et leur choix peut différer du vôtre. La "
            "preuve montre ce que déclare chaque membre."
        ),
        "recommendation": (
            "Choisissez une adresse pour le groupe et faites-la désigner par tous les "
            "membres. Si un membre pointe hors du groupe, vérifiez que cette adresse est "
            "bien celle voulue : elle vient le plus souvent d'une structure antérieure."
        ),
        "consequence": (
            "Vos pages donnent des réponses contradictoires sur la version réelle : la "
            "décision est donc prise à votre place plutôt que par vous."
        ),
    },
    # ── Транспорт: стиснення й протокол ────────────────────────────────────
    "tech.transport.uncompressed": {
        "title": "{count} réponses texte sont arrivées sans compression (la plus grande {size} Ko)",
        "description": (
            "Nous avons demandé du contenu compressé et ces réponses sont revenues non "
            "encodées. La preuve porte chacune d'elles : son type, ce que nous avons "
            "demandé et les deux tailles que nous avons pu établir. Notez ce qui est dit et "
            "ce qui ne l'est pas : cela décrit les réponses reçues, non les capacités du "
            "serveur. Nous n'annonçons que gzip et deflate ; un serveur ne proposant que "
            "Brotli nous répondrait de la même façon. Combien d'octets la compression "
            "économiserait, nous ne le disons pas : il aurait fallu les compresser "
            "nous-mêmes, ce que nous n'avons pas fait."
        ),
        "recommendation": (
            "Vérifiez si la compression est activée pour ces types de contenu sur le "
            "serveur ou le CDN. gzip suffit amplement : nul besoin de passer à Brotli ou "
            "Zstandard pour corriger cela, et ce serait une décision distincte avec ses "
            "propres arbitrages."
        ),
        "consequence": (
            "Du texte qui pourrait voyager compressé voyage entier : chaque visiteur attend "
            "donc plus d'octets que la page n'a besoin d'envoyer. Cela se voit surtout sur "
            "une connexion mobile lente."
        ),
    },
    "tech.transport.http1": {
        "title": "{count} réponses ont été servies en HTTP/1.1",
        "description": (
            "Notre client propose HTTP/2 et le négocie avec succès sur la plupart des sites "
            "; pour ces réponses, la connexion s'en est tenue au protocole plus ancien. "
            "C'est une observation sur ces échanges, non une affirmation que votre serveur "
            "ne gère pas HTTP/2 : la version négociée dépend du serveur, d'un éventuel CDN "
            "sur le chemin et du client. HTTP/2 exploite mieux une connexion — plusieurs "
            "échanges à la fois et en-têtes compressés — mais qu'une page donnée charge "
            "plus vite dépend de la page. Nous ne testons pas HTTP/3 du tout : rien ici "
            "n'en dit quoi que ce soit."
        ),
        "recommendation": (
            "Vérifiez le réglage HTTP/2 sur le serveur ou le CDN placé devant. Dans la "
            "plupart des panneaux d'hébergement et des CDN, c'est un simple interrupteur, "
            "souvent désactivé sur les configurations anciennes."
        ),
        "consequence": (
            "Les requêtes vers votre site utilisent une manière plus ancienne et moins "
            "efficace de partager une connexion. Sur les pages qui chargent beaucoup de "
            "fichiers à la fois, cela se traduit par de l'attente en plus."
        ),
    },
}


# Avis d'une ligne du domaine : pourquoi une partie de l'audit n'a pas
# tourné, pourquoi un lancement a été retenté ou non. Séparés de MESSAGES à
# dessein — le raisonnement est dans le catalogue ukrainien.
NOTICES: dict[str, str] = {
    "notice.breadcrumb.hierarchy_unknown": (
        "le site a été trop peu lu pour dire si ses pages dépendent les unes des autres ; savoir "
        "si un fil d'Ariane a sa place ici reste indécis"
    ),
    "notice.about_page.candidate_unread": (
        "la page À propos vers laquelle le site renvoie ({anchor} : {url}) n'a pas été "
        "lue ; savoir si le site dit qui est derrière reste indécis"
    ),
    "notice.about_page.candidate_unreadable": (
        "la page À propos à l'adresse {url} n'a pas pu être évaluée : {reasons} (réponse {status})"
    ),
    "coverage.reason.about_page_failed_read": "la page n'a pas renvoyé de document lisible",
    "coverage.reason.about_page_content_shell": (
        "la réponse était une coquille d'application vide : du balisage sans texte principal"
    ),
    "coverage.reason.about_page_login_wall": (
        "le contenu principal était un formulaire de connexion, sans titre À propos"
    ),
    "coverage.reason.about_page_redirect_placeholder": (
        "le document se contentait de rediriger le lecteur ailleurs"
    ),
    # degradations
    "notice.accessibility.no_category": (
        "aucune vérification d'accessibilité n'a tourné : le fournisseur n'a pas renvoyé "
        "cette catégorie"
    ),
    "notice.accessibility.not_measured": (
        "l'accessibilité n'a pas été mesurée : la mesure de vitesse a été exclue de cet audit"
    ),
    "notice.crawl.blind": (
        "le site n'a renvoyé aucune page avec du contenu (statuts de réponse : {statuses})"
    ),
    "notice.coverage.withheld": (
        "Pages analysées : {pages}. La note globale du site est retenue : du contenu vivant "
        "visible n'a pas été inspecté ({reasons}). Une note du contenu lu ne peut pas tenir "
        "lieu de note du site."
    ),
    "notice.coverage.limited": "Pages analysées : {pages}. Limite de couverture : {reasons}.",
    "coverage.reason.robots_restricted": (
        "l'exploration est restreinte par les règles robots.txt du site"
    ),
    "coverage.reason.access_failures": (
        "certaines URL accessibles n'ont pas répondu — {access} sur {attempted}"
    ),
    "coverage.reason.untried_live_candidates": (
        "des pages découvertes du site n'ont pas été ouvertes — {untried}"
    ),
    "coverage.reason.no_evidence_of_additional_live_content": (
        "aucun indice d'autre contenu vivant n'a été trouvé"
    ),
    "notice.crawl.failures": (
        "{failed} adresses sur {attempted} n'ont pas répondu : ce que nous avons lu ne "
        "représente pas le site"
    ),
    "notice.crawl.empty": (
        "{words} mots sur l'ensemble du site même après exécution des scripts ; pages lues : "
        "{pages}. Il n'y a rien à évaluer"
    ),
    "notice.crawl.empty_static": (
        "la réponse du serveur contient {words} mots : le texte n'apparaît qu'après exécution "
        "des scripts ({rendered} mots sur {pages} pages). Les moteurs de recherche voient "
        "cette page, la plupart des assistants non"
    ),
    "notice.crawl.entry_error": (
        "l'adresse d'entrée a renvoyé HTTP {status} : la vitesse a été mesurée sur une page "
        "d'erreur, pas sur le site"
    ),
    "notice.crawl.entry_error_stand_in": (
        "l'adresse d'entrée a renvoyé HTTP {status} : la vitesse a été mesurée sur une page "
        "d'erreur, pas sur le site ; {stand_in} a servi de page d'accueil à la place"
    ),
    "notice.crawl.shallow": (
        "seule la page d'accueil a été explorée, bien qu'elle pointe vers des pages "
        "internes : le reste n'a pas répondu ou n'a pas renvoyé de HTML"
    ),
    "notice.module.excluded": "le module a été désactivé dans les options de l'audit",
    "notice.performance.no_vitals": (
        "les Core Web Vitals n'ont pas été mesurés ({detail}). La note repose uniquement "
        "sur le temps de réponse du serveur et les signaux du HTML statique"
    ),
    "notice.performance.no_metrics": "le fournisseur n'a renvoyé aucune métrique : {detail}",
    "notice.performance.partial": "les données de vitesse sont incomplètes : {detail}",
    "notice.llm.unavailable": "aucune analyse sémantique n'a tourné : {detail}",
    "notice.llm.disabled": "l'analyse sémantique a été désactivée dans les options de l'audit",
    "notice.llm.facts_unavailable": (
        "l'analyse sémantique n'a renvoyé aucun fait sur l'entreprise : la vérification qui en "
        "dépend n'a pas tourné"
    ),
    "notice.render.failed": "les pages n'ont pas été rendues : {detail}",
    "notice.render.disabled": "le rendu a été désactivé dans les options de l'audit",
    "notice.analytics.unidentified": (
        "du trafic de mesure est visible, mais aucun fournisseur n'a pu être identifié "
        "({detail}) : la conclusion sur l'analytique reste ouverte"
    ),
    "notice.analytics.render_incomplete": (
        "le balisage ne contient aucun compteur, et les pages qui pourraient encore le révéler "
        "après l'exécution des scripts n'ont pas été rendues ({detail})"
    ),
    "notice.check.failed": "la vérification n'a pas tourné à cause d'une erreur",
    "notice.layer.failed": "une partie de l'audit n'a pas tourné à cause d'une erreur",
    # retries
    "notice.retry.not_attempted": "aucune reprise n'était prévue",
    "notice.retry.scheduled": "tentative {next_attempt} sur {allowed}",
    "notice.retry.exhausted": "tentatives épuisées ({attempts}/{allowed})",
    "notice.retry.not_retryable": "nous ne relançons pas les échecs de type « {failure} »",
}


# Catalogue des formules : ce que le client achète, en mots humains. Séparé
# de MESSAGES et NOTICES à dessein — voir le catalogue ukrainien.
CATALOG: dict[str, str] = {
    "plan.limit.audits": "{count} audits par mois",
    "plan.limit.audits_unlimited": "Audits illimités",
    "plan.limit.pages": "Jusqu'à {count} pages par audit",
    "plan.limit.sites": "{count} sites",
    "plan.limit.sites_unlimited": "Sites illimités",
    "plan.limit.schedules": "{count} programmations",
    "plan.limit.team": "{count} membres d'équipe",
    "plan.limit.history": "{count} jours d'historique",
    "plan.limit.history_unlimited": "Historique complet",
    "plan.feature.semantic": "Analyse sémantique",
    "plan.feature.reports": "Rapports Word",
    "plan.feature.public_reports": "Liens de rapport publics",
    "plan.feature.api": "Accès API",
    "plan.feature.white_label": "Rapports à votre marque",
    "plan.cta.start_free": "Commencer gratuitement",
    "plan.cta.subscribe": "S'abonner",
    "plan.cta.contact": "Nous parler",
}
