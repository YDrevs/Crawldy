"""Redacción en español de los hallazgos. Escrita para el cliente, no traducida palabra por palabra.

Glosario del idioma (coherente con el sitio público ES):
hallazgo — finding; prueba — evidence; cobertura — coverage;
recomendación — recommendation; IA — nunca «AI» como término primario;
buscadores — search engines. Tratamiento: tú (como en el sitio público).
"""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    # ── SEO ─────────────────────────────────────────────────────────────────
    "seo.title.missing": {
        "title": "Falta la etiqueta <title>",
        "description": "La página no tiene etiqueta de título — crítico para la búsqueda y los "
        "modelos.",
        "recommendation": "Añade un título único de 30–60 caracteres con la consulta principal.",
        "consequence": (
            "La página no tiene título propio. Los buscadores pueden construir el encabezado "
            "del resultado por su cuenta, a partir del texto de la página."
        ),
    },
    "seo.title.too_short": {
        "title": "El título no explica nada ({length} caracteres)",
        "description": (
            "Un título de menos de {min} caracteres no puede decir de qué trata la página."
        ),
        "recommendation": (
            "Añade lo que la gente busca de verdad: el servicio, el lugar, el beneficio."
        ),
        "consequence": (
            "Junto a los competidores en los resultados, un titular así no da ninguna razón "
            "para hacer clic en ti."
        ),
    },
    "seo.title.too_long": {
        "title": "Solo se muestran los primeros {visible} de {length} caracteres",
        "description": "La búsqueda recorta el final del título.",
        "recommendation": (
            "Pon lo importante al principio — nada más allá de {visible} caracteres se muestra."
        ),
        "consequence": (
            "Nadie ve el final del titular — si la clave estaba ahí, no llega."
        ),
    },
    "seo.title.duplicate": {
        "title": "El mismo título en {count} páginas",
        "description": "Títulos idénticos hacen las páginas indistinguibles en el índice.",
        "recommendation": "Da a cada página su propio título.",
        "consequence": (
            "Para los buscadores y para la gente las páginas parecen idénticas: cuesta saber "
            "cuál es la que hace falta."
        ),
    },
    "seo.meta_description.missing": {
        "title": "Falta la meta descripción",
        "description": "Sin ella, la búsqueda arma el fragmento con un trozo de texto aleatorio.",
        "recommendation": "Añade una descripción que quepa en los ~{visible} caracteres visibles.",
        "consequence": (
            "No se detectó una metadescripción en esta página. Los buscadores pueden crear "
            "el fragmento a partir del texto de la página."
        ),
    },
    "seo.h1.missing": {
        "title": "No hay h1 en la vista analizada",
        "description": (
            "La vista analizada de la página no contiene ningún encabezado HTML h1. Si existen "
            "encabezados de niveles inferiores, el primero de ellos se muestra en las "
            "evidencias. Un h1 claro es una práctica recomendada de estructura del documento; "
            "para entender y etiquetar una página es una señal posible entre varias, junto con "
            "el title y otras."
        ),
        "recommendation": (
            "Considere un h1 claro con el tema de la página: a menudo basta con promover el "
            "primer encabezado existente."
        ),
        "consequence": (
            "El encabezado principal de la página no está marcado como el de mayor nivel en el "
            "código. Los programas que leen la estructura se apoyan en otras pistas: el título de "
            "la pestaña y los subencabezados."
        ),
    },
    "seo.h1.no_headings": {
        "title": "No se encontraron encabezados HTML (h1–h6)",
        "description": (
            "La vista analizada de la página no contiene encabezados HTML h1–h6 con texto. Los "
            "encabezados organizan el contenido para lectores y tecnologías de asistencia; esta "
            "afirmación cubre específicamente los encabezados HTML — otros mecanismos de marcado "
            "no se evaluaron."
        ),
        "recommendation": (
            "Añada una estructura clara de encabezados adecuada a esta página: uno principal y "
            "subencabezados de sección."
        ),
        "consequence": (
            "La página no tiene estructura de secciones marcada. Los lectores y los lectores de "
            "pantalla no tienen a qué agarrarse salvo texto continuo."
        ),
    },
    "seo.h1.multiple": {
        "title": "Varios elementos h1 ({count}); visibilidad no evaluada",
        "description": (
            "La vista analizada contiene {count} elementos h1 con texto. Su visibilidad CSS no se "
            "evaluó: algunos pueden ser duplicados de plantilla para distintos diseños. Un único "
            "h1 principal claro es una práctica común, pero varios h1 están permitidos por el "
            "HTML, y esta observación por sí sola no establece un problema de búsqueda."
        ),
        "recommendation": (
            "Si los duplicados no son intencionados, conserve un h1 principal y convierta el "
            "resto en subencabezados."
        ),
        "consequence": (
            "El encabezado principal está marcado más de una vez. Es una observación sobre el "
            "código de la página, no un daño detectado."
        ),
    },
    "seo.heading_hierarchy": {
        "title": "Salto de encabezado H{previous} → H{level}",
        "description": "Saltarse un nivel hace la estructura más difícil de analizar por máquina.",
        "recommendation": "No te saltes niveles de encabezado.",
        "consequence": (
            "La estructura de la página parece ilógica al software que la lee, y el texto se "
            "divide peor en bloques con sentido."
        ),
    },
    "seo.canonical.missing": {
        "title": "Sin rel=canonical",
        "description": "",
        "recommendation": "Da a cada página indexable una canonical autorreferenciada.",
        "consequence": (
            "Si la misma página es accesible en varias direcciones, la búsqueda puede "
            "tratarlas como páginas distintas y repartir el peso."
        ),
    },
    "seo.canonical.mismatch": {
        "title": "La canonical apunta a otra página",
        "description": "Esto saca la página del índice — comprueba que sea intencionado.",
        "recommendation": "Comprueba que la canonical no apunte por error a la portada.",
        "consequence": (
            "La página dice a los buscadores que no es la versión principal, así que puede "
            "desaparecer por completo de los resultados."
        ),
    },
    "seo.noindex": {
        "title": "La página está cerrada a la búsqueda",
        "description": (
            "El marcado pide a los buscadores no mostrar esta página. A menudo es "
            "deliberado — landings de pago, archivos de eventos, páginas para tráfico "
            "interno. Vemos la instrucción, no la intención — comprueba si corresponde aquí."
        ),
        "recommendation": (
            "Si la página debe traer gente desde la búsqueda, quita la instrucción. Si está "
            "cerrada a propósito, déjalo todo como está."
        ),
        "consequence": (
            "Mientras la instrucción siga, esta página no trae visitantes desde la búsqueda. "
            "Si es lo que quieres, todo bien; si no, el trabajo invertido no sirve de nada."
        ),
    },
    "seo.render_delta.indexing": {
        "title": "Las señales de indexación cambian tras ejecutar JavaScript: {fields}",
        "description": (
            "La respuesta del servidor y la página tras ejecutar los scripts no coinciden en las "
            "señales que deciden qué URL se indexa. La evidencia recoge ambos valores. Google sí "
            "renderiza JavaScript, pero su documentación indica que la página espera en una cola "
            "que \"can take longer\" que unos segundos, y que \"not all bots can run "
            "JavaScript\"."
        ),
        "recommendation": (
            "Comprueba cuál de los dos valores es el que quieres y entrégalo ya en el HTML de la "
            "respuesta, en lugar de fijarlo con un script."
        ),
        "consequence": (
            "Existen dos instrucciones distintas para la misma página, y cuál se aplica depende "
            "de si el sistema que la visita ejecuta scripts."
        ),
    },
    "seo.render_delta.identity": {
        "title": "Cómo se presenta la página cambia tras ejecutar JavaScript: {fields}",
        "description": (
            "El encabezado o el texto que se muestra en los resultados de búsqueda no son iguales "
            "antes y después de ejecutar los scripts. La evidencia recoge ambos valores. Un "
            "sistema que no ejecuta JavaScript solo ve la respuesta."
        ),
        "recommendation": (
            "Coloca el encabezado y la descripción definitivos en el HTML que envía el servidor; "
            "deja que los scripts mejoren la página, no que la definan."
        ),
        "consequence": (
            "Unos sistemas describen tu página de una forma y otros de otra, así que el nombre "
            "que ve la gente no siempre es el que escribiste."
        ),
    },
    "seo.render_delta.markup": {
        "title": "Los datos estructurados cambian tras ejecutar JavaScript",
        "description": (
            "El marcado legible por máquinas no es el mismo antes y después de ejecutar los "
            "scripts: aparecen, desaparecen o cambian tipos e identificadores. La evidencia "
            "enumera ambos conjuntos."
        ),
        "recommendation": (
            "Emite el marcado en la respuesta del servidor. Lo que solo aparece tras los scripts "
            "únicamente lo leen los sistemas que los ejecutan."
        ),
        "consequence": (
            "Los datos que publicas sobre tu negocio son legibles para unos sistemas e invisibles "
            "para otros."
        ),
    },
    "seo.render_delta.links": {
        "title": "{count} enlaces internos existen solo tras ejecutar JavaScript",
        "description": (
            "Estos enlaces no están en la respuesta del servidor y aparecen solo en la página "
            "renderizada. La evidencia los enumera. Google sigue los enlaces que encuentra tras "
            "renderizar, pero su documentación recuerda que no todos los bots ejecutan "
            "JavaScript."
        ),
        "recommendation": (
            "Entrega estos enlaces como anclas normales en el HTML. Los scripts pueden mejorar la "
            "navegación por encima de eso."
        ),
        "consequence": (
            "Partes del sitio solo son accesibles para sistemas que ejecutan scripts; para el "
            "resto, esas páginas no están enlazadas desde aquí."
        ),
    },
    "seo.robots_txt.missing": {
        "title": "Falta robots.txt",
        "description": "Los rastreadores no reciben instrucciones ni señal de tu sitemap.",
        "recommendation": "Añade /robots.txt con una directiva Sitemap.",
        "consequence": (
            "Los buscadores llegan sin instrucciones y no saben dónde está tu sitemap."
        ),
    },
    "seo.robots_txt.disallow_all": {
        "title": "robots.txt bloquea el sitio entero",
        "description": "`Disallow: /` para `User-agent: *` bloquea todo el rastreo.",
        "recommendation": "Quita Disallow: / si el sitio debe estar en la búsqueda.",
        "consequence": (
            "robots.txt prohíbe el rastreo de todo el sitio. Los buscadores no leerán las "
            "páginas; una dirección aún puede aparecer en los resultados, pero sin descripción "
            "y sin contenido detrás."
        ),
    },
    "seo.robots_txt.no_sitemap": {
        "title": "robots.txt sin directiva Sitemap",
        "description": "",
        "recommendation": "Añade una línea `Sitemap: https://.../sitemap.xml`.",
        "consequence": (
            "Los buscadores no reciben ninguna pista de dónde vive tu lista de páginas y las "
            "descubren más despacio."
        ),
    },
    "seo.sitemap.missing": {
        "title": "sitemap.xml no encontrado",
        "description": "",
        "recommendation": "Genera un sitemap XML y referéncialo desde robots.txt.",
        "consequence": (
            "No se encontró ningún mapa del sitio: no está en las ubicaciones estándar y el sitio "
            "no indicó otra dirección."
        ),
    },
    "seo.sitemap.invalid": {
        "title": "sitemap.xml no se puede leer",
        "description": "",
        "recommendation": "Arregla el XML — un sitemap inválido es ignorado por los rastreadores.",
        "consequence": (
            "El mapa del sitio existe pero no se puede leer: el archivo no se analiza como XML. "
            "No servirá de nada hasta que se corrija el formato."
        ),
    },
    "seo.sitemap.empty": {
        "title": "sitemap.xml está vacío",
        "description": "",
        "recommendation": "Añade las URL de tus páginas al sitemap.",
        "consequence": "El sitemap no contiene direcciones y no cumple su función.",
    },
    "seo.sitemap.coverage": {
        "title": "{count} páginas rastreadas no están en el sitemap",
        "description": "",
        "recommendation": "Mantén la generación del sitemap alineada con la estructura real.",
        "consequence": (
            "Parte de las páginas falta en el sitemap: la búsqueda se entera de ellas más "
            "tarde o nunca."
        ),
    },
    "seo.broken_links": {
        "title": "{count} URL internas devuelven error",
        "description": (
            "Seguimos estos enlaces nosotros mismos y el servidor respondió con un error. La "
            "evidencia recoge cada destino roto junto con las páginas que enlazan a él, el "
            "texto de cada enlace y si el enlace estaba en la respuesta del servidor o apareció "
            "solo tras ejecutarse los scripts. Un destino sin páginas de origen no estaba "
            "enlazado en ninguna página que leyéramos: viene del sitemap."
        ),
        "recommendation": (
            "Trabaje desde la evidencia: para cada destino nombra las páginas que apuntan a él. "
            "Cambie esos enlaces a una dirección que funcione, o retírelos. Cuando varias "
            "páginas enlazan a la misma dirección muerta, el enlace suele estar en una "
            "plantilla compartida."
        ),
        "consequence": "Los visitantes caen en páginas rotas — visitas perdidas y mala impresión.",
    },
    "seo.https.missing": {
        "title": "El sitio no está en HTTPS",
        "description": "Los sitios HTTP se marcan como no seguros y se posicionan peor.",
        "recommendation": "Activa TLS y redirige HTTP a HTTPS con un 301.",
        "consequence": (
            "Los navegadores marcan el sitio como no seguro y muestran un aviso antes del "
            "contenido. Qué hace el visitante con ese aviso no lo medimos."
        ),
    },
    "seo.https.invalid_cert": {
        "title": "El certificado HTTPS no es válido",
        "description": (
            "El sitio solo carga con la verificación del certificado desactivada. Las causas "
            "habituales: cadena intermedia incompleta, certificado autofirmado o caducado. "
            "Los rastreadores de búsqueda se saltan los sitios en este estado."
        ),
        "recommendation": (
            "Reemite el certificado y sirve la cadena intermedia completa. Comprueba el "
            "resultado en ssllabs.com/ssltest — la nota debe ser A."
        ),
        "consequence": (
            "En lugar de tu sitio, los visitantes ven una página roja de aviso con un botón "
            "de «Volver a un sitio seguro». Casi todos lo pulsan."
        ),
    },
    "seo.https.no_hsts": {
        "title": "Sin cabecera HSTS",
        "description": "",
        "recommendation": "Añade `Strict-Transport-Security: max-age=31536000`.",
        "consequence": (
            "La primera visita puede viajar por una conexión sin proteger — una brecha "
            "pequeña pero real."
        ),
    },
    "seo.image_alt": {
        "title": "{without_alt} de {total} imágenes sin alt",
        "description": "El texto alt es accesibilidad y a la vez señal textual para los modelos.",
        "recommendation": "Describe el contenido de la imagen; deja alt=\"\" para lo decorativo.",
        "consequence": (
            "Los visitantes ciegos no oyen nada sobre la imagen: un lector de pantalla toma la "
            "descripción de ese atributo. El texto que solo existe dentro de una imagen no "
            "forma parte del contenido de la página."
        ),
    },
    "seo.thin_content": {
        "title": "Solo {word_count} palabras en la página",
        "description": (
            "Poco texto es una señal débil para la búsqueda y para la cita por modelos. "
            "También puede significar que el contenido se renderiza en el cliente."
        ),
        "recommendation": "Amplía el texto principal a {threshold}+ palabras, o verifica el SSR.",
        "consequence": (
            "Hay demasiado poco texto para que la página se considere útil: se posiciona "
            "débil y casi no hay nada que citar."
        ),
    },
    "seo.click_depth": {
        "title": "Pocos enlaces desde esta página: {internal_links}",
        "description": (
            "Esta página enlaza a {internal_links} páginas más del sitio. Se cuentan los "
            "enlaces encontrados en esta página, así que no dice nada sobre cuántas "
            "páginas enlazan HACIA ella: una página a la que apunta todo el menú puede no "
            "llevar a ninguna parte."
        ),
        "recommendation": (
            "Añade enlaces desde esta página a lo que el lector querrá después: servicios "
            "relacionados, la categoría correspondiente, el caso que respalda lo que dices."
        ),
        "consequence": (
            "Quien llega aquí casi no tiene adónde seguir, así que se marcha en lugar de "
            "seguir viendo lo que ofreces."
        ),
    },
    "cro.no_action": {
        "title": "En esta página no hay nada que hacer",
        "description": (
            "Una página que ofrece algo no tiene formulario, ni teléfono o correo "
            "pulsable, ni enlace al pedido, al carrito o a los contactos. Quien quedó "
            "convencido no tiene con qué actuar."
        ),
        "recommendation": (
            "Da a la página un siguiente paso evidente y repítelo tras el texto principal: "
            "un botón de pedido, un formulario de consulta o el teléfono como enlace. Un "
            "paso claro funciona mejor que tres."
        ),
        "consequence": (
            "Esta página no ofrece ninguna acción fuera del menú y el pie: ni formulario, ni "
            "botón, ni contacto en el propio texto. Quien termina de leer y quiere ponerse en "
            "contacto tiene que buscarlo por su cuenta."
        ),
    },
    "cro.phone_not_tappable": {
        "title": "El teléfono está impreso pero no se puede marcar",
        "description": (
            "El número aparece en el sitio pero nunca está marcado como enlace de llamada. "
            "En el móvil, el visitante tiene que memorizarlo, salir del sitio y teclearlo a "
            "mano. Páginas donde lo vimos: {count}."
        ),
        "recommendation": (
            "Marca el número como enlace tel:+… en todas partes — cabecera, pie y página de "
            "contacto. Media hora de trabajo."
        ),
        "consequence": (
            "La mayoría de los visitantes llega con el móvil. En vez de tocar para llamar, "
            "tienen que copiar el número — y una parte simplemente no lo hará."
        ),
    },
    "seo.topic_islands": {
        "title": "{count} páginas de un mismo tema nunca se enlazan entre sí",
        "description": (
            "Leímos {count} páginas que cubren el mismo terreno y ninguna menciona a otra. "
            "El único camino de una a la siguiente es el menú o una página índice — faltan "
            "las conexiones de sentido, las que muestran que el tema se trabajó."
        ),
        "recommendation": (
            "Añada enlaces contextuales ENTRE PÁGINAS REALMENTE RELACIONADAS donde de verdad "
            "ayuden al lector: de un caso a otro afín, de un artículo al que lo continúa. No hace "
            "falta enlazar cada página de la sección con todas las demás: un enlace puesto para "
            "cumplir una regla no ayuda ni a la persona ni al buscador."
        ),
        "consequence": (
            "Las páginas no se refuerzan entre sí. Quien lee una nunca ve la siguiente que "
            "necesita, y el sitio se lee como un montón de hojas sueltas y no como prueba "
            "de que la empresa domina su campo."
        ),
    },
    "seo.orphan_pages": {
        "title": "{count} páginas del sitemap sin ningún enlace entrante",
        "description": (
            "El sitemap declara estas páginas, pero nada en el sitio lleva a ellas. Los "
            "buscadores pueden encontrarlas; un visitante, nunca, y su posición descansa "
            "solo en el sitemap — la señal más débil que un sitio puede enviar."
        ),
        "recommendation": (
            "Enlaza estas páginas desde donde corresponden: el menú, su categoría o el "
            "texto de páginas afines. Si una página no es para visitantes, sácala mejor del "
            "sitemap."
        ),
        "consequence": (
            "Estas páginas existen, pero desde el propio sitio no hay camino hacia ellas. "
            "Los visitantes nunca las ven, y el trabajo invertido se pierde."
        ),
    },
    "seo.links_to_noindex": {
        "title": "{count} páginas enlazadas pero ocultas de la búsqueda",
        "description": (
            "El sitio pone una página en su navegación y a la vez prohíbe a los buscadores "
            "mostrarla. Una de las dos cosas está mal: o la página importa a la gente y "
            "debe ser visible, o es interna y no pinta nada en el menú."
        ),
        "recommendation": (
            "Decide cuál de las dos es cada página. Si importa, quita la prohibición de "
            "indexar; si es interna, quita el enlace de la navegación."
        ),
        "consequence": (
            "Un visitante sigue un enlace a una página que los buscadores deben ocultar. El "
            "sitio se contradice, y parte del camino hacia la compra no lleva a ninguna parte."
        ),
    },
    "seo.viewport": {
        "title": "Sin meta viewport",
        "description": "Sin viewport, la página no se adapta a pantallas móviles.",
        "recommendation": (
            "Añade <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."
        ),
        "consequence": (
            "En el móvil la página aparece como una versión de escritorio encogida — "
            "incómoda de leer, y Google lo tiene en cuenta."
        ),
    },
    "seo.sitemap.lastmod": {
        "title": "El sitemap no tiene fechas de modificación",
        "description": "",
        "recommendation": "Añade lastmod a cada URL y actualízalo cuando cambie la página.",
        "consequence": (
            "Después de actualizar el sitio, el mapa no lleva ninguna señal de qué cambió: no "
            "hay nada en él para distinguir una página nueva de una antigua."
        ),
    },
    "seo.clean_url.uppercase": {
        "title": "Mayúsculas en la URL de la página",
        "description": (
            "Las URL distinguen mayúsculas: /Services y /services son técnicamente páginas "
            "distintas."
        ),
        "recommendation": "Pasa la ruta a minúsculas y redirige la antigua con un 301.",
        "consequence": (
            "La búsqueda puede tratar variantes de escritura como páginas distintas y "
            "repartir su autoridad."
        ),
    },
    "seo.clean_url.underscore": {
        "title": "Guiones bajos en la URL de la página",
        "description": "",
        "recommendation": "Sustituye los guiones bajos por guiones y redirige con un 301.",
        "consequence": (
            "Las palabras de la dirección se pegan, y la búsqueda entiende peor el tema de "
            "la página."
        ),
    },
    "seo.clean_url.query": {
        "title": "Parámetros de consulta en la URL de la página",
        "description": (
            "El mismo contenido accesible con parámetros distintos parece varias páginas."
        ),
        "recommendation": "Pasa a rutas limpias, o consolida los parámetros con una canonical.",
        "consequence": (
            "El mismo contenido está disponible en varias direcciones. Los buscadores pueden "
            "tratarlas como páginas distintas y repartir las señales entre ellas."
        ),
    },
    # ── Preparación para la IA / LLMO ───────────────────────────────────────
    "ai.llms_txt.missing": {
        "title": "No hay llms.txt (oportunidad opcional)",
        "description": (
            "llms.txt es un archivo markdown en la raíz que describe brevemente el sitio para "
            "agentes de IA: qué es, secciones clave, enlaces a las páginas principales. Es una "
            "convención emergente con adopción creciente, pero sigue siendo una propuesta y no un "
            "estándar: el archivo es opcional y experimental, y su ausencia no es ni un problema "
            "conocido de posicionamiento ni un requisito de visibilidad en los modelos de "
            "lenguaje. Su ausencia no impide que los sistemas de IA accedan al sitio ni lo citen."
        ),
        "recommendation": (
            "Conviene considerarlo sobre todo cuando el sitio tiene documentación, referencia u "
            "otro contenido estructurado. Cree /llms.txt: un H1 con el nombre del producto, una "
            "descripción breve y secciones `##` con enlaces a las páginas clave. No garantiza "
            "nada: ni rastreo, ni citas, ni posiciones."
        ),
        "consequence": (
            "Servicios como ChatGPT o Perplexity se forman su idea del sitio con lo que "
            "encuentran por sí mismos. El archivo puede facilitárselo, pero su ausencia no le "
            "quita al sitio ni acceso ni citas."
        ),
    },
    "ai.llms_txt.no_h1": {
        "title": "llms.txt sin H1",
        "description": "",
        "recommendation": (
            "La primera línea debe ser `# Nombre del proyecto`. El archivo en sí sigue siendo una "
            "opción experimental, no un requisito."
        ),
        "consequence": (
            "El archivo llms.txt empieza sin nombre, aunque la especificación lo exige en la "
            "primera línea. Quien lea el archivo no verá a qué producto pertenece."
        ),
    },
    "ai.llms_txt.thin": {
        "title": "llms.txt es demasiado escueto",
        "description": "El archivo existe pero no da al modelo ningún mapa del sitio.",
        "recommendation": (
            "Añade secciones `##` y 5+ enlaces a páginas clave. El archivo en sí sigue siendo una "
            "opción experimental, no un requisito."
        ),
        "consequence": (
            "El archivo de resumen existe pero no muestra al modelo de qué se compone el "
            "sitio — aporta poco."
        ),
    },
    "ai.jsonld.missing": {
        "title": "No se detectaron datos estructurados en las respuestas del servidor",
        "description": (
            "En las respuestas analizadas no se detectó ni JSON-LD ni Microdata; RDFa no se "
            "evaluó. El marcado schema.org es opcional: da a las máquinas pistas explícitas sobre "
            "el significado de la página y habilita la elegibilidad para resultados enriquecidos, "
            "pero no los garantiza ni es un requisito de visibilidad en servicios de IA."
        ),
        "recommendation": (
            "Si decide añadir marcado, empiece con JSON-LD en la página principal: Google "
            "recomienda ese formato como el más fácil de mantener."
        ),
        "consequence": (
            "Las máquinas se forman su idea de la página solo a partir del texto. Las pistas "
            "explícitas podrían facilitarlo, pero su ausencia no le cuesta al sitio ni presencia "
            "en buscadores ni menciones."
        ),
    },
    "ai.jsonld.invalid": {
        "title": "JSON-LD inválido",
        "description": "El bloque ld+json no se puede leer — el marcado se ignora por completo.",
        "recommendation": "Arregla la sintaxis JSON del script application/ld+json.",
        "consequence": (
            "La descripción legible por máquina no se puede leer — el esfuerzo de añadirla "
            "fue en vano."
        ),
    },
    "ai.jsonld.no_type": {
        "title": "JSON-LD sin @type",
        "description": "",
        "recommendation": "Cada entidad necesita un @type de schema.org.",
        "consequence": (
            "Los datos de la página están sin etiquetar — el software ve valores pero no "
            "sabe qué significan."
        ),
    },
    "ai.schema.organization": {
        "title": "El marcado no muestra una entidad de organización o persona",
        "description": (
            "Hay datos estructurados, pero en la página principal y en las páginas «quiénes "
            "somos» de la muestra no se observó ninguna entidad de identidad: ni Organization ni "
            "sus subtipos, ni Person, ni WebSite. Esa entidad es opcional y no tiene propiedades "
            "obligatorias."
        ),
        "recommendation": (
            "Para una empresa, institución o marca personal, considere el subtipo de Organization "
            "aplicable o el marcado Person/WebSite en la página principal o en «quiénes somos». "
            "Añada solo las propiedades que le correspondan."
        ),
        "consequence": (
            "No hay una ficha explícita legible por máquinas que diga quién está detrás del "
            "sitio: las máquinas lo infieren del texto. Es una oportunidad de mejora, no una "
            "avería."
        ),
    },
    "ai.entity.sameas": {
        "title": "Sin sameAs (señales de entidad)",
        "description": (
            "sameAs vincula tu marca con bases de conocimiento externas (Wikidata, LinkedIn, "
            "GitHub, Crunchbase) — la señal de identidad primaria."
        ),
        "recommendation": "Añade sameAs con enlaces a los perfiles oficiales de la marca.",
        "consequence": (
            "No hay confirmación de que sea la misma marca que en Wikipedia o LinkedIn, y "
            "los modelos confían menos en tus datos."
        ),
    },
    "ai.schema.breadcrumb": {
        "title": "Sin BreadcrumbList",
        "description": "Las migas de pan muestran al modelo dónde está la página en la jerarquía.",
        "recommendation": "Añade BreadcrumbList a las páginas interiores.",
        "consequence": (
            "No queda claro a qué sección del sitio pertenece la página — se pierde contexto."
        ),
    },
    "ai.schema.faq": {
        "title": "{count} preguntas en la página sin marcado FAQPage",
        "description": (
            "Los encabezados están formulados como preguntas, pero no hay marcado FAQPage ni "
            "QAPage. Los pares pregunta–respuesta son el formato que mejor manejan los "
            "modelos: marcados, se pueden tomar y citar enteros."
        ),
        "recommendation": (
            "Envuelve los pares pregunta–respuesta existentes en marcado FAQPage. No hay "
            "que reescribir nada — el contenido ya está, solo falta el marcado."
        ),
        "consequence": (
            "Las respuestas ya están escritas en la página, pero en una forma que nada "
            "reconoce — así que los modelos citan al competidor que marcó lo mismo."
        ),
    },
    "ai.schema.content_type": {
        "title": "Página de contenido sin marcado Article/Product",
        "description": "",
        "recommendation": (
            "Añade Article (headline, author, datePublished, dateModified) o Product, según "
            "el tipo de página."
        ),
        "consequence": (
            "Una página sustancial no está etiquetada ni como artículo ni como producto, y "
            "no aparece en los resultados enriquecidos."
        ),
    },
    "ai.opengraph": {
        "title": "Etiquetas OG ausentes: {missing}",
        "description": "",
        "recommendation": "Completa el OpenGraph — lo leen las redes sociales y los rastreadores "
        "de IA.",
        "consequence": (
            "Los enlaces a tu sitio compartidos en mensajería y redes no tendrán imagen ni "
            "descripción propias."
        ),
    },
    "ai.lang": {
        "title": "Idioma de la página sin declarar",
        "description": "El atributo lang ayuda a interpretar e indexar el texto correctamente.",
        "recommendation": "Añade <html lang=\"es\"> (o el código de idioma que corresponda).",
        "consequence": (
            "Al no declararse el idioma, la página puede mostrarse al público equivocado u "
            "ofrecerse para traducción."
        ),
    },
    "ai.opengraph.no_image": {
        "title": "Sin og:image",
        "description": "",
        "recommendation": "Añade una imagen de 1200×630 en la meta etiqueta og:image.",
        "consequence": (
            "Los enlaces a tu sitio aparecen en mensajería y redes como un rectángulo "
            "vacío, y menos gente hace clic."
        ),
    },
    "ai.schema.contact.missing": {
        "title": "Sin marcado LocalBusiness / ContactPoint",
        "description": (
            "Para un negocio local es la vía principal de entregar a una máquina la "
            "dirección, el teléfono y el horario."
        ),
        "recommendation": (
            "Añade JSON-LD LocalBusiness con address, telephone, openingHoursSpecification y "
            "geo."
        ),
        "consequence": (
            "Los datos de contacto aparecen en el sitio, pero no están marcados como datos "
            "estructurados del negocio."
        ),
    },
    "ai.schema.contact.incomplete": {
        "title": "LocalBusiness sin los campos: {missing}",
        "description": "",
        "recommendation": "Completa el marcado — estos campos alimentan las fichas y las "
        "respuestas de IA.",
        "consequence": (
            "Tu ficha en la búsqueda quedará incompleta: parte de los datos simplemente no "
            "tiene de dónde salir."
        ),
    },
    "ai.schema.graph": {
        "title": "Los bloques JSON-LD no están conectados entre sí",
        "description": "Varios bloques sueltos sin @id se leen como entidades sin relación.",
        "recommendation": (
            "Da a cada bloque un @id y referencia unos desde otros para formar un grafo."
        ),
        "consequence": (
            "La máquina ve fragmentos dispersos de datos en vez de una imagen coherente de "
            "la empresa."
        ),
    },
    "ai.twitter_card": {
        "title": "Sin tarjeta de Twitter/X",
        "description": "",
        "recommendation": (
            "Añade <meta name=\"twitter:card\" content=\"summary_large_image\"> más "
            "twitter:title/description/image."
        ),
        "consequence": (
            "En X y en varias mensajerías tu enlace aparece sin imagen ni descripción."
        ),
    },
    # ── Aptitud para ser citado ─────────────────────────────────────────────
    "llm.direct_answer": {
        "title": "Comprobación retirada: estructura del inicio de la página",
        "description": (
            "Una versión anterior de Crawldy señalaba la estructura del texto al comienzo de la "
            "página. Esta heurística se retiró porque podía confundir la navegación, la "
            "puntuación y la maquetación con la calidad del contenido. Ya no se usa en auditorías "
            "nuevas ni en la puntuación."
        ),
        "recommendation": (
            "No se requiere ninguna acción basada únicamente en este registro retirado. Evalúe la "
            "claridad de la página para los visitantes con los hallazgos y pruebas actuales del "
            "informe."
        ),
        "consequence": (
            "Este registro procede de una versión anterior de la auditoría y no afecta a los "
            "resultados nuevos."
        ),
    },
    "llm.structure": {
        "title": "Texto largo ({word_count} palabras) sin subtítulos",
        "description": "Un muro de texto se segmenta peor en fragmentos citables.",
        "recommendation": "Divide el contenido en secciones H2/H3; añade listas y tablas.",
        "consequence": (
            "Un muro de texto: difícil de leer para una persona, y difícil para un modelo "
            "extraer de él un fragmento corto."
        ),
    },
    "llm.about_page": {
        "title": "Sin página Sobre nosotros",
        "description": (
            "La página Sobre nosotros es la fuente principal de la que un modelo forma su "
            "imagen de la organización y su autoridad."
        ),
        "recommendation": "Crea /about describiendo la empresa, su historia y su equipo.",
        "consequence": (
            "Entre las páginas leídas, ninguna tiene una dirección, un título o un texto de "
            "enlace que parezca una página «Sobre nosotros»."
        ),
    },
    "llm.contact_page": {
        "title": "Sin página de Contacto",
        "description": (
            "Los datos de contacto son una señal básica de confianza (E-E-A-T) para la "
            "búsqueda y los modelos."
        ),
        "recommendation": "Añade /contact con dirección, correo y marcado ContactPoint.",
        "consequence": (
            "Sin datos de contacto visibles, el sitio parece menos fiable tanto a los "
            "visitantes como a los buscadores."
        ),
    },
    "llm.brand_consistency": {
        "title": "El nombre de marca es inconsistente",
        "description": (
            "El nombre del JSON-LD no aparece en el título de la portada — un modelo puede "
            "no conectar el sitio con la marca."
        ),
        "recommendation": "Usa la misma grafía de marca en title, H1 y schema.org.",
        "consequence": (
            "El nombre de marca se escribe distinto en distintos sitios, lo que dificulta "
            "asociarlo contigo."
        ),
    },
    "llm.stale_content": {
        "title": "Nada en el sitio se ha actualizado en {years} años",
        "description": (
            "Ninguna de las páginas con fecha que leímos se ha tocado en {years} años. La "
            "cuestión no es una página concreta — una guía puede seguir siendo válida "
            "años — sino el sitio en su conjunto."
        ),
        "recommendation": (
            "Repasa las páginas principales y refresca lo envejecido: precios, qué incluye "
            "el servicio, trabajos recientes. Pon la fecha de actualización en el marcado, "
            "o nadie sabrá que algo cambió."
        ),
        "consequence": (
            "La fecha más reciente que encontramos en el sitio tiene años. Un lector no tiene "
            "cómo saber si la información sigue vigente."
        ),
    },
    "llm.stale_content.sparse": {
        "title": "El material fechado más reciente tiene {years} años",
        "description": (
            "Solo {dated} de las {read} páginas leídas llevan fecha, así que esto habla de las "
            "fechas encontradas, no del sitio completo. Una página sin fecha no es una página "
            "antigua: muchos sitios simplemente no las publican."
        ),
        "recommendation": (
            "Si el material se ha actualizado, registra la fecha de actualización en el "
            "marcado: sin ella no hay de dónde leer la fecha. Si no se ha actualizado, empieza "
            "por las páginas que más se leen."
        ),
        "consequence": (
            "Cuando las únicas fechas visibles tienen años, el lector supone que el sitio ya no "
            "se mantiene, aunque no sea cierto."
        ),
    },
    "llm.authorship": {
        "title": "Página de contenido sin author/datePublished",
        "description": "Autoría y fechas son señales de frescura y credibilidad.",
        "recommendation": "Añade author, datePublished y dateModified al marcado Article.",
        "consequence": (
            "No se ve quién escribió esto ni cuándo, y el material se lee como menos fiable."
        ),
    },
    "llm.crawler_blocked.search": {
        "title": "{count} rastreadores de búsqueda con IA bloqueados: {crawlers}",
        "description": (
            "Estos rastreadores indexan páginas para que un asistente pueda encontrarlas y "
            "citarlas. robots.txt les impide llegar a las páginas indicadas en la evidencia. Se "
            "trata del acceso, no de si algún asistente te menciona: eso no lo medimos."
        ),
        "recommendation": (
            "Si el bloqueo no era intencionado, permite estos user-agent en robots.txt. Mantenlos "
            "separados de los de entrenamiento: puedes permitir la búsqueda y seguir rechazando "
            "el entrenamiento."
        ),
        "consequence": (
            "Los asistentes a los que la gente pregunta no pueden abrir estas páginas, lo que "
            "puede reducir tus opciones de aparecer como fuente."
        ),
    },
    "llm.crawler_blocked.grounding": {
        "title": "{count} rastreadores de grounding bloqueados: {crawlers}",
        "description": (
            "Estos tokens controlan si el contenido que el proveedor recoge de tu sitio puede "
            "usarse para grounding — es decir, entregarse al modelo en el momento de la consulta "
            "— dentro de los productos de IA de ese mismo proveedor. Google-Extended abarca "
            "Gemini Apps y Vertex AI. robots.txt les impide llegar a las páginas de la evidencia. "
            "Google señala que este token no afecta a la inclusión ni al posicionamiento en la "
            "Búsqueda de Google, así que no es un problema de búsqueda."
        ),
        "recommendation": (
            "Si el bloqueo no era intencionado, permite estos user-agent. Ten en cuenta que el "
            "mismo token también rige el entrenamiento de modelos, así que permitirlo habilita "
            "ambos; hoy no se pueden separar en robots.txt."
        ),
        "consequence": (
            "El contenido recogido de estas páginas puede no usarse como fuente cuando Gemini "
            "responde a una pregunta. Esto no dice nada sobre otros asistentes, y tu posición en "
            "la Búsqueda de Google no cambia."
        ),
    },
    "llm.crawler_blocked.user": {
        "title": "{count} agentes de asistente bloqueados: {crawlers}",
        "description": (
            "Estos agentes abren una página cuando una persona se lo pide expresamente a un "
            "asistente. robots.txt les impide llegar a las páginas de la evidencia."
        ),
        "recommendation": (
            "Si no era intencionado, permite estos user-agent. Actúan por petición directa de una "
            "persona, así que bloquearlos afecta sobre todo a quien ya quería leerte."
        ),
        "consequence": (
            "Tu sitio prohíbe a este agente, así que cuando un visitante pide al asistente que "
            "mire tu página, no tiene permiso para descargarla. Qué responde el asistente en su "
            "lugar no lo observamos."
        ),
    },
    "llm.crawler_blocked.training": {
        "title": "{count} rastreadores de entrenamiento bloqueados: {crawlers}",
        "description": (
            "Estos rastreadores recogen material para entrenar modelos. Aquí solo están "
            "bloqueados ellos: el acceso de búsqueda y de asistente no se ve afectado. Rechazar "
            "el entrenamiento es una decisión legítima sobre tu contenido, y queda registrada "
            "para que siga siendo una decisión y no un descuido."
        ),
        "recommendation": (
            "Si fue deliberado, no hay nada que corregir. Si no, permite estos user-agent: solo "
            "controlan el acceso para entrenamiento."
        ),
        "consequence": (
            "Tus textos quedan fuera del entrenamiento de modelos. Es una decisión sobre tu "
            "contenido, no un defecto del sitio."
        ),
    },
    "llm.client_rendered": {
        "title": "El contenido parece renderizarse en el cliente",
        "description": (
            "El HTML estático casi no contiene texto pese a mucho marcado. La mayoría de "
            "los rastreadores de IA no ejecuta JavaScript y verá una página vacía."
        ),
        "recommendation": "Activa SSR/SSG o prerenderizado para las páginas clave.",
        "consequence": (
            "En la propia respuesta del servidor la página está casi vacía: el texto aparece "
            "solo después de ejecutar los scripts. Un lector que no los ejecuta ve la versión "
            "vacía."
        ),
    },
    # ── Velocidad ───────────────────────────────────────────────────────────
    "perf.core_web_vitals.lcp": {
        "title": "LCP = {value}{unit} ({strategy})",
        "description": (
            "Largest Contentful Paint — tiempo hasta pintar el elemento principal. El umbral "
            "«bueno» es {threshold}{unit}."
        ),
        "recommendation": (
            "Optimiza la imagen principal (preload, formato moderno) y quita el CSS/JS que "
            "bloquea el renderizado."
        ),
        "consequence": (
            "El contenido principal de la página tarda demasiado en cargar. Los visitantes "
            "tienen que esperar más y pueden abandonar el sitio antes de que termine de "
            "cargar."
        ),
    },
    "perf.core_web_vitals.inp": {
        "title": "INP = {value}{unit} ({strategy})",
        "description": (
            "Interaction to Next Paint — retraso de respuesta a una acción. El umbral "
            "«bueno» es {threshold}{unit}."
        ),
        "recommendation": "Trocea las tareas largas de JS y reduce la hidratación.",
        "consequence": (
            "La página se atasca visiblemente al responder a los clics — se siente lenta."
        ),
    },
    "perf.core_web_vitals.cls": {
        "title": "CLS = {value}{unit} ({strategy})",
        "description": (
            "Cumulative Layout Shift — inestabilidad visual durante la carga. El umbral "
            "«bueno» es {threshold}{unit}."
        ),
        "recommendation": "Fija width/height en imágenes y reserva sitio para banners y fuentes.",
        "consequence": (
            "Mientras cargan las imágenes y las fuentes, el texto se mueve ante los ojos y la "
            "página resulta incómoda de leer."
        ),
    },
    "perf.core_web_vitals.ttfb": {
        "title": "TTFB = {value}{unit} ({strategy})",
        "description": (
            "Time To First Byte — tiempo de respuesta del servidor. El umbral «bueno» es "
            "{threshold}{unit}."
        ),
        "recommendation": "Activa caché/CDN y optimiza las consultas a la base de datos.",
        "consequence": (
            "El servidor responde demasiado lento, lo que retrasa la carga de la página."
        ),
    },
    "perf.core_web_vitals.tbt": {
        "title": "TBT = {value}{unit} ({strategy})",
        "description": (
            "Total Blocking Time — bloqueo del hilo principal. El umbral «bueno» es "
            "{threshold}{unit}."
        ),
        "recommendation": "Reduce la cantidad y el peso del JavaScript.",
        "consequence": (
            "La página parece cargada pero aún no responde — el estado más irritante para "
            "un visitante."
        ),
    },
    "perf.mobile_gap": {
        "title": "En el móvil el sitio es el doble de lento que en el ordenador",
        "description": (
            "Medimos el sitio dos veces: como lo ve un ordenador y como lo ve un móvil. En "
            "ordenador saca {desktop} de 100; en móvil, {mobile}. Google clasifica por la "
            "versión móvil, y la mayoría de la gente también llega desde el móvil."
        ),
        "recommendation": (
            "Compara las pruebas de abajo: listan las métricas más de dos veces peores en "
            "móvil. Los culpables habituales son imágenes pesadas y la cantidad de "
            "JavaScript, que un móvil procesa mucho más despacio que un escritorio."
        ),
        "consequence": (
            "Tú miras tu sitio en el ordenador y todo parece bien. Tus clientes lo miran en "
            "el móvil y ven otra cosa — y parte de ellos no esperará."
        ),
    },
    "perf.server_response.slow": {
        "title": "El servidor responde despacio ({median} ms)",
        "description": (
            "Mediana del tiempo hasta el primer byte en las páginas rastreadas. El umbral "
            "«bueno» es {threshold} ms. Es retraso antes de que el navegador pueda pintar "
            "nada."
        ),
        "recommendation": (
            "Activa caché en el servidor o CDN y busca consultas lentas a la base de datos."
        ),
        "consequence": "Cada visitante espera ante una pantalla vacía antes de que algo aparezca.",
    },
    "perf.server_response.very_slow": {
        "title": "El servidor responde muy despacio ({median} ms)",
        "description": (
            "Mediana del tiempo hasta el primer byte en las páginas rastreadas, frente a un "
            "umbral «bueno» de {threshold} ms. Con esta latencia sufre cualquier otra "
            "métrica: el navegador simplemente espera."
        ),
        "recommendation": (
            "Es el primer cuello de botella a resolver. Perfila la generación de páginas en "
            "el servidor y añade luego caché y un CDN."
        ),
        "consequence": (
            "El servidor responde demasiado lento, lo que retrasa la carga de la página."
        ),
    },
    "perf.lighthouse_score": {
        "title": "Rendimiento Lighthouse {score} ({strategy})",
        "description": "Una puntuación bajo 90 significa problemas de velocidad apreciables.",
        "recommendation": "Empieza por los primeros puntos del bloque de oportunidades.",
        "consequence": (
            "La nota global de velocidad es baja — con una conexión lenta el sitio será "
            "difícil de usar."
        ),
    },
    "perf.unavailable": {
        "title": "Datos de velocidad no recogidos",
        "description": "El proveedor no devolvió métricas — el módulo de velocidad no se puntuó.",
        "recommendation": "Comprueba PSI_API_KEY o la disponibilidad del sidecar de Lighthouse.",
        "consequence": (
            "La velocidad no se midió esta vez, así que la puntuación es incompleta. No es "
            "un problema del sitio."
        ),
    },
    "perf.render_blocking": {
        "title": "{count} recursos que bloquean el renderizado en <head>",
        "description": "Scripts síncronos y CSS retrasan el primer pintado.",
        "recommendation": "Añade async/defer a los scripts y pon el CSS crítico inline.",
        "consequence": (
            "Tu visitante mira una pantalla en blanco varios segundos antes de que algo "
            "aparezca."
        ),
    },
    "perf.images.legacy_format": {
        "title": "{count} imágenes podrían servirse en un formato más ligero",
        "description": (
            "JPG y PNG no están obsoletos y funcionan en todas partes — pero las mismas "
            "imágenes en WebP o AVIF suelen pesar bastante menos. La ganancia depende del "
            "archivo."
        ),
        "recommendation": (
            "Sirve WebP/AVIF mediante <picture> con reserva al formato actual."
        ),
        "consequence": (
            "La página carga más despacio de lo que podría — sobre todo en el móvil y con "
            "conexión lenta."
        ),
    },
    "perf.images.no_dimensions": {
        "title": "{count} imágenes sin width/height",
        "description": (
            "Sin dimensiones el navegador no reserva sitio — un coste directo de CLS."
        ),
        "recommendation": "Fija width y height (o aspect-ratio) en cada <img>.",
        "consequence": (
            "Mientras cargan las imágenes, el texto salta y se vuelve incómodo de leer."
        ),
    },
    "perf.images.no_lazy": {
        "title": "Sin carga diferida pese a muchas imágenes",
        "description": "",
        "recommendation": "Añade loading=\"lazy\" a las imágenes bajo la línea de pliegue.",
        "consequence": (
            "El navegador descarga todas las imágenes a la vez, incluidas las que el "
            "visitante quizá nunca llegue a ver."
        ),
    },
    "perf.external_fonts": {
        "title": "Las fuentes cargan de hosts de terceros: {hosts}",
        "description": (
            "Un host de fuentes externo añade una conexión a la ruta crítica de renderizado."
        ),
        "recommendation": (
            "Aloja las fuentes tú mismo y cárgalas con @font-face y font-display: swap."
        ),
        "consequence": (
            "El navegador espera al servidor de otro antes de mostrar texto — la página "
            "sigue vacía más tiempo."
        ),
    },
    "perf.third_party": {
        "title": "{count} hosts de terceros en la portada",
        "description": (
            "Cada host externo supone una conexión aparte, una consulta DNS y código ajeno."
        ),
        "recommendation": (
            "Quita lo que no sirva a la conversión: widgets de más, trackers, chats."
        ),
        "consequence": (
            "El sitio depende de la velocidad y disponibilidad de servidores ajenos, y "
            "cualquiera de ellos puede frenarlo."
        ),
    },
    "perf.third_party.weight": {
        "title": "El código de terceros es {share} de la página ({kb} KB)",
        "description": (
            "Abrimos la página en un navegador real y pesamos todo lo que carga. {share} "
            "del total viene de dominios ajenos — widgets, chats, trackers, publicidad. "
            "Cada uno debe llegar antes de que la página sea plenamente usable."
        ),
        "recommendation": (
            "Repasa los dominios más pesados listados en las pruebas. Carga después lo que "
            "no haga falta sobre el pliegue, y elimina lo que nadie usa."
        ),
        "consequence": (
            "La velocidad de tu sitio depende de los servidores de otras empresas. Si "
            "tienen un mal día, tus visitantes también — y no puedes hacer nada."
        ),
    },
    "perf.page_weight": {
        "title": "La página pesa {megabytes} MB antes de cualquier imagen",
        "description": (
            "Eso es solo el marcado, sin imágenes ni scripts: {words} palabras en un solo "
            "documento. Una página normal pesa decenas o cientos de kilobytes. Las causas "
            "habituales: spam de comentarios, un catálogo volcado en la página o rastros de "
            "una intrusión."
        ),
        "recommendation": (
            "Mira qué ocupa el espacio: abre la página y busca texto que nunca añadiste. Si "
            "son comentarios, desactívalos o modéralos; si son enlaces desconocidos y "
            "galimatías, revisa el sitio por si está comprometido y cambia las contraseñas."
        ),
        "consequence": (
            "Una página de este peso tarda mucho en cargar incluso con buena conexión, y en el "
            "teléfono puede no abrirse en absoluto."
        ),
    },
    "perf.page_weight.truncated": {
        "title": "La página es demasiado grande para leerla entera: al menos {megabytes} MB",
        "description": (
            "El marcado superó el límite hasta el que leemos, así que {words} palabras ni "
            "siquiera son el total. Un documento de este tamaño nunca es casual: "
            "normalmente spam de comentarios, un catálogo volcado o las secuelas de una "
            "intrusión. Todo lo demás que decimos de esta página se refiere a la parte "
            "leída."
        ),
        "recommendation": (
            "Revisa la página a mano: ábrela y mira de dónde sale el grueso. Enlaces "
            "desconocidos o texto que no escribiste apuntan a un compromiso probable — "
            "cambia las contraseñas y haz revisar el sitio. Borra los comentarios de spam "
            "de la base de datos, no solo de la vista."
        ),
        "consequence": (
            "Quien llegue con el móvil probablemente se rinda antes de que cargue. Los "
            "buscadores también la leen solo en parte — y lo leído puede resultar ser "
            "texto de otro y no el tuyo."
        ),
    },
    "perf.responsive_images": {
        "title": "{count} imágenes sin tamaños adaptables",
        "description": "",
        "recommendation": "Añade srcset y sizes para que los móviles descarguen una versión menor.",
        "consequence": (
            "Los móviles descargan las fotos al mismo tamaño que los ordenadores: la página "
            "abre más despacio y consume los datos del visitante."
        ),
    },
    # ── Protección y analítica ──────────────────────────────────────────────
    "tech.security_headers.none": {
        "title": "No se detectaron cabeceras de protección en la respuesta analizada",
        "description": (
            "Ninguna de las cabeceras de protección comprobadas ({headers}) está presente en la "
            "respuesta. Son mecanismos adicionales de protección; su ausencia por sí sola no "
            "indica un incidente de seguridad, pero suele significar que la configuración aún no "
            "se ha abordado."
        ),
        "recommendation": (
            "Hable con el desarrollador sobre cuáles de estos mecanismos convienen a su "
            "aplicación. Se suele empezar por X-Content-Type-Options: nosniff, la más segura en "
            "compatibilidad."
        ),
        "consequence": (
            "Las protecciones del navegador para los visitantes no están configuradas en "
            "absoluto. El sitio no está roto por ello, pero le falta el margen que estos "
            "mecanismos dan gratis."
        ),
    },
    "tech.security_headers.missing": {
        "title": "No se detectaron {count} protecciones opcionales del navegador",
        "description": (
            "No se detectaron en la respuesta analizada: {headers}. Son mecanismos adicionales de "
            "protección del navegador para los visitantes. Su ausencia por sí sola no indica un "
            "incidente de seguridad ni es un requisito directo de visibilidad en buscadores o "
            "sistemas de IA."
        ),
        "recommendation": (
            "Revise la configuración con el desarrollador del sitio: qué cabeceras convienen "
            "depende de la aplicación, y activarlas a ciegas puede romper páginas que funcionan."
        ),
        "consequence": (
            "Parte de las protecciones estándar del navegador para los visitantes no está "
            "activada. Es margen que falta, no una brecha: el sitio no queda comprometido ni "
            "pierde lectores por ello."
        ),
    },
    "tech.crawler_blocked": {
        "title": "El sitio responde a los robots con estado {status} en vez de una página",
        "description": (
            "Nuestro agente recibió {status} y no vio ninguna página con contenido. La "
            "protección contra bots suele tratar igual a GPTBot, ClaudeBot y PerplexityBot: sus "
            "peticiones también llegan desde un navegador desconocido. Google, en cambio, puede "
            "pasar — se le reconoce aparte. Probamos con un agente, el nuestro; cómo responde "
            "el sitio a los demás no lo comprobamos."
        ),
        "recommendation": (
            "En los ajustes de protección (Cloudflare, WAF, fail2ban) permite los "
            "rastreadores de búsqueda y de IA por sus user-agents y rangos de IP. Verifica "
            "el resultado con la inspección de URL de Search Console."
        ),
        "consequence": (
            "El sitio no dejó entrar a nuestro programa: no se pudo leer ni una sola página. "
            "Los mismos ajustes suelen detener también a los bots de los servicios de IA, pero "
            "no comprobamos si este sitio los bloquea: el resto del informe se apoya solo en lo "
            "visible desde fuera."
        ),
    },
    "tech.analytics.missing": {
        "title": "No se detectó ningún sistema de analítica en el sitio",
        "description": (
            "Abrimos la página en un navegador real y ejecutamos todo su JavaScript. No "
            "apareció ningún contador — ni Google Analytics o GTM, ni Plausible, Matomo, "
            "Segment o PostHog, ni script de medición propio."
        ),
        "recommendation": (
            "Instala Google Analytics 4 y verifica el sitio en Search Console. Ambos son "
            "gratuitos y se montan en una hora."
        ),
        "consequence": (
            "En las páginas leídas no se detectó ningún script de analítica."
        ),
    },
    "tech.analytics.unconfirmed": {
        "title": "Ningún tag de analítica en el código fuente",
        "description": (
            "El HTML no lleva Google Analytics ni GTM ni alternativa. Eso sí, miramos sin "
            "ejecutar JavaScript, y algunos tags se inyectan después de cargar — uno de "
            "esos no lo habríamos visto."
        ),
        "recommendation": (
            "Confirma si de verdad hay un tag instalado, por ejemplo en los informes de la "
            "propia herramienta. Si no, añade Google Analytics 4."
        ),
        "consequence": (
            "Si nada mide las visitas, no sabes cuánta gente viene ni qué hace — no hay en "
            "qué basar las mejoras."
        ),
    },
    "tech.form_protection.unprotected": {
        "title": (
            "Comprobación obsoleta: no se halló un marcador de protección visible en el "
            "formulario"
        ),
        "description": (
            "Registro de una auditoría anterior: dentro del formulario no se detectó un "
            "marcador anti-abuso visible del lado del cliente. Aquella comprobación no evaluaba "
            "los mecanismos del servidor ni los invisibles; este registro por sí solo no prueba "
            "que el formulario estuviera desprotegido."
        ),
        "recommendation": (
            "No hace falta ninguna acción basada solo en este registro heredado. Valore el "
            "estado de los formularios según los hallazgos actuales del informe."
        ),
        "consequence": (
            "Este registro procede de una versión anterior de la auditoría y no afecta a los "
            "resultados nuevos."
        ),
    },
    "tech.form_protection.no_visible_marker": {
        "title": (
            "No se detectó protección visible contra bots en el formulario."
        ),
        "description": (
            "No se encontró protección visible ni en el HTML inicial ni en el formulario "
            "renderizado. Puede existir protección en el servidor, pero esta comprobación "
            "pasiva no puede confirmarla."
        ),
        "recommendation": (
            "Si los envíos automáticos no deseados son un problema real o un riesgo material, "
            "pregunte al desarrollador o proveedor qué controles anti-abuso del lado del "
            "servidor están activos. Elija medidas proporcionadas al formulario y al riesgo del "
            "usuario, y considere la fricción y la accesibilidad; el CAPTCHA no es obligatorio, "
            "y cualquier widget del lado del cliente debe respaldarse con validación en el "
            "servidor."
        ),
        "consequence": (
            "El propio formulario no muestra señales visibles de comprobar que lo envía una "
            "persona. Es una observación sobre el código de la página, no un defecto probado: "
            "la comprobación puede ejecutarse en el servidor, donde no la vemos."
        ),
    },
    "tech.form_protection.get_method": {
        "title": (
            "{count} formularios envían datos mediante GET"
        ),
        "title.one": "{count} formulario envía datos mediante GET",
        "description": (
            "Un formulario con método GET coloca los valores introducidos en la URL de la "
            "petición. Esas URL pueden quedar en el historial del navegador y aparecer en "
            "registros del servidor o del proxy y en enlaces copiados. Use POST para "
            "formularios con datos personales o no públicos; POST por sí solo no es cifrado ni "
            "un control de seguridad completo — HTTPS se requiere aparte."
        ),
        "recommendation": (
            "Cambia el método a post — los datos del formulario no deben acabar en la "
            "barra de direcciones."
        ),
        "consequence": (
            "Lo que una persona escribe en el formulario acaba en la dirección de la página y "
            "puede quedar en el historial del navegador y en los registros."
        ),
    },
    "tech.email_exposed": {
        "title": "{count} direcciones de correo expuestas en el código",
        "description": (
            "Los enlaces mailto: con la dirección en claro los cosechan los recolectores "
            "automáticos."
        ),
        "recommendation": "Sustitúyelos por un formulario de contacto o monta la dirección por "
        "script.",
        "consequence": (
            "Los bots de spam irán cosechando la dirección y empezará a llegar basura. Es "
            "una molestia más que una amenaza: el buzón en sí no corre peligro."
        ),
    },
    "tech.caching": {
        "title": "Las páginas se sirven sin reglas de caché",
        "description": "Sin Cache-Control, ETag ni Last-Modified en {count} páginas revisadas.",
        "recommendation": "Configura Cache-Control y ETag a nivel de servidor o CDN.",
        "consequence": (
            "El navegador vuelve a descargar la página cada vez, aunque nada haya cambiado."
        ),
    },
    "tech.soft_404": {
        "title": "Una página inexistente devuelve el estado {status}",
        "description": (
            "El servidor responde con éxito a una dirección que no existe. Se espera 404."
        ),
        "recommendation": "Configura el servidor para devolver 404 en direcciones inexistentes.",
        "consequence": (
            "La página responde «todo correcto» mientras muestra un error. Todo lo que se guía "
            "por el código de respuesta — un navegador, un buscador, nuestro propio programa — "
            "la toma por una página real."
        ),
    },
    "tech.host_canonical": {
        "title": "El sitio también abre en {host}",
        "description": (
            "Ambas variantes de host sirven contenido y no redirigen a una sola."
        ),
        "recommendation": (
            "Configura una redirección 301 permanente del host secundario al principal."
        ),
        "consequence": (
            "El mismo sitio existe en dos direcciones, y la búsqueda reparte su autoridad "
            "entre ellas en vez de contarla entera."
        ),
    },
    "tech.nap.phone_mismatch": {
        "title": "El sitio muestra {count} teléfonos distintos",
        "description": "Páginas distintas muestran números de contacto distintos.",
        "recommendation": "Deja un número, o di explícitamente qué número es para qué.",
        "consequence": (
            "Se encontraron varios números de teléfono, pero ninguno está identificado como "
            "número de contacto principal."
        ),
    },
    "tech.nap.phone_not_e164": {
        "title": "{count} números no están en formato internacional",
        "description": (
            "Un enlace tel: debe llevar el más, el prefijo del país y el número — sin "
            "espacios, paréntesis ni guiones. Ahora mismo, por ejemplo: {example}."
        ),
        "recommendation": (
            "Normaliza cada tel: al formato internacional: un más, el prefijo del país y "
            "los dígitos sin separadores. El texto visible puede seguir siendo legible."
        ),
        "consequence": (
            "En el móvil, un número así no siempre se marca con un solo toque."
        ),
    },
    "tech.nap.schema_mismatch": {
        "title": "El teléfono del marcado no coincide con el de las páginas",
        "description": (
            "El JSON-LD entrega a las máquinas un número mientras el sitio muestra otro a "
            "las personas."
        ),
        "recommendation": "Sincroniza telephone de los datos estructurados con el número de tus "
        "contactos.",
        "consequence": (
            "Tu ficha en la búsqueda puede mostrar el número equivocado — las llamadas irán "
            "a otro sitio."
        ),
    },
    "seo.meta_description.too_long": {
        "title": "Solo se muestran los primeros {visible} de {length} caracteres",
        "description": (
            "La búsqueda recorta el resto. Una descripción más larga no es un error — los "
            "rastreadores de IA la leen entera — pero en los resultados la gente solo ve el "
            "principio."
        ),
        "recommendation": (
            "Asegúrate de que la idea y la llamada a la acción caben en los primeros "
            "{visible} caracteres."
        ),
        "consequence": (
            "Si el mensaje principal está al final de la descripción, nadie lo lee en la "
            "búsqueda."
        ),
    },
    "seo.meta_description.too_short": {
        "title": "La descripción es demasiado escueta ({length} caracteres)",
        "description": "Con menos de {min} caracteres no puede explicar ni convencer.",
        "recommendation": "Di qué es el servicio, para quién, y qué hacer a continuación.",
        "consequence": (
            "Bajo tu resultado casi no hay nada — la gente elige al competidor que escribió "
            "algo."
        ),
    },
    "llm.unstated_facts.offering": {
        "title": (
            "Las páginas leídas no dicen qué vende la empresa"
        ),
        "description": (
            "Tras leer todo el sitio, no se puede nombrar un producto o servicio concreto. "
            "Frases como «soluciones para tu negocio» no responden a la pregunta con la "
            "que llega un comprador."
        ),
        "recommendation": (
            "Di en la portada, en una frase, qué vendes — no «soluciones integrales» sino "
            "«instalamos videovigilancia»."
        ),
        "consequence": (
            "Las páginas que leímos no dicen qué vendes. Ni una persona ni un servicio de "
            "búsqueda o de IA tiene de dónde sacarlo."
        ),
    },
    "llm.unstated_facts.location": {
        "title": "El sitio nunca dice dónde trabajas",
        "description": (
            "Ni ciudad, ni región, ni país en ninguna parte. Para un negocio de zona es el "
            "primer filtro del comprador: busca a alguien cerca."
        ),
        "recommendation": (
            "Pon la ciudad y la dirección en el pie de cada página y en la página de "
            "contacto. Si cubres más zona, lista las localidades que atiendes."
        ),
        "consequence": (
            "A la pregunta «quién hace esto en mi ciudad» el sitio no tiene qué responder: "
            "nunca dice dónde estás. Así te sugieren menos justo a los compradores a los "
            "que les vendría bien acudir a ti."
        ),
    },
    "llm.unstated_facts.pricing": {
        "title": "El sitio nunca dice cuánto cuesta",
        "description": (
            "Ni precios, ni tarifas, ni una oferta clara de preparar presupuesto. El precio "
            "es lo primero que pregunta un comprador, y el sitio no responde."
        ),
        "recommendation": (
            "Publica precios, o al menos un rango «desde–hasta». Si cada trabajo se "
            "presupuesta aparte, dilo claramente y da un formulario para pedirlo."
        ),
        "consequence": (
            "El comprador te compara con la competencia y te descarta primero: su precio se "
            "ve, el tuyo no. Callar el precio se lee como «caro»."
        ),
    },
    "ai.jsonld.partial": {
        "title": "Observación retirada: el marcado no estaba en todas las páginas",
        "description": (
            "Una versión anterior de Crawldy señalaba la cobertura parcial como defecto. Esa "
            "observación se retiró: el marcado no tiene que estar en todas las páginas, y las "
            "auditorías nuevas no tratan la cobertura parcial como problema."
        ),
        "recommendation": (
            "No se requiere ninguna acción basada únicamente en este registro retirado."
        ),
        "consequence": (
            "Este registro procede de una versión anterior de la auditoría y no afecta a los "
            "resultados nuevos."
        ),
    },
    "tech.demo_content": {
        "title": "El contenido de demostración de la plantilla sigue en el sitio",
        "description": (
            "Encontramos {count} señales de que parte del sitio son datos de demo de un "
            "tema nunca sustituido: personas inventadas en el equipo, un teléfono de "
            "relleno, un correo en el dominio del vendedor del tema, o piezas de plantilla "
            "del maquetador accesibles públicamente."
        ),
        "recommendation": (
            "Quita o sustituye las páginas y contactos de demo. Mantén las piezas del "
            "maquetador fuera del índice."
        ),
        "consequence": (
            "Los visitantes ven a personas que no trabajan contigo y contactos que no "
            "tienes. Eso daña la confianza más que los fallos técnicos — y buscadores y "
            "asistentes leen esas páginas como la verdad sobre tu empresa."
        ),
    },
    "a11y.blocking": {
        "title": "{count} barreras que impiden usar el sitio",
        "description": (
            "No va de estética. Zoom bloqueado, un botón o enlace sin nombre, un campo sin "
            "etiqueta — la persona simplemente no puede hacer aquello a lo que vino: leer "
            "en el móvil, tocar, rellenar el formulario."
        ),
        "recommendation": (
            "Quita user-scalable=no del viewport, da a botones y enlaces texto o un "
            "aria-label, etiqueta los campos del formulario."
        ),
        "consequence": (
            "Es posible que algunos visitantes no puedan utilizar partes de la página. Los "
            "problemas de accesibilidad afectan a botones, enlaces o campos de formulario."
        ),
    },
    "a11y.failures": {
        "title": "{count} observaciones de accesibilidad",
        "description": (
            "Un pase automático de Lighthouse encontró puntos donde el contenido es más "
            "difícil de leer o de alcanzar con teclado. Nadie verifica automáticamente el "
            "cumplimiento completo — eso requiere pruebas manuales."
        ),
        "recommendation": (
            "Repasa la lista de las pruebas. La mayoría se arregla con atributos de "
            "marcado, sin rediseñar nada."
        ),
        "consequence": (
            "Las personas con poca vista, con móviles antiguos o que usan teclado en vez de "
            "ratón encuentran el sitio más difícil de usar de lo necesario."
        ),
    },
    # ── Мовні версії ───────────────────────────────────────────────────────
    "seo.hreflang_invalid": {
        "title": "{count} versiones declaradas usan un valor que Google no acepta: {values}",
        "description": (
            "Google admite aquí una forma más estrecha de lo que parece: un idioma según ISO "
            "639-1, opcionalmente una escritura según ISO 15924, opcionalmente un país según "
            "ISO 3166-1 Alpha 2 — en ese orden — más el reservado x-default. Por eso zh-Hant y "
            "zh-Hans-US son válidos y en_US, en-UK o en-US-Latn no lo son. La evidencia indica "
            "qué falla en cada valor; lo más frecuente es poner un código de país donde va el "
            "idioma."
        ),
        "recommendation": (
            "Corrija cada valor de la evidencia: guion en lugar de guion bajo, en-GB en lugar "
            "de uk o en-UK, y el idioma antes del país. La evidencia también registra en cuál "
            "de los tres sitios está cada valor."
            "Un caso no tiene forma válida: un idioma sin código ISO 639-1 (asturiano, "
            "casubio y otros; marcados como not_a_language en la evidencia). No puede "
            "representarse con ningún código de idioma hreflang válido, porque la "
            "gramática de Google no tiene ninguno para él. No sustituya el código por el "
            "de otro idioma: una página en asturiano declarada como español induce a "
            "error tanto a los buscadores como a los lectores. Elimine el valor y deje "
            "esa versión sin hreflang."
            "Si el mismo valor aparece también en los conjuntos recíprocos de otras versiones de "
            "idioma, elimínelo allí también: de lo contrario, media web seguirá apuntando a un "
            "código no válido."
        ),
        "consequence": (
            "Las marcas de las versiones de idioma están escritas en un formato que los "
            "buscadores no aceptan, así que no surten efecto. Las páginas destinadas a otros "
            "países quedan sin declarar."
        ),
    },
    "seo.hreflang_reciprocity.self": {
        "title": "La página declara {count} versiones y nunca se nombra a sí misma",
        "description": (
            "Un conjunto de versiones declaradas debe incluir la propia página en la que está, "
            "apuntando a su propia dirección. Sin esa autorreferencia el conjunto queda "
            "incompleto y puede descartarse. Una entrada x-default que apunte aquí no cuenta: "
            "significa \"venid aquí si nada encaja\"."
        ),
        "recommendation": (
            "Añada, junto a las demás, una entrada para el idioma de esta página que apunte a "
            "esta misma dirección. Sirve cualquiera de los tres sitios: la propia página, la "
            "cabecera HTTP o el mapa del sitio."
        ),
        "consequence": (
            "La página enumera qué otras versiones existen pero nunca dice cuál es ella, así "
            "que el grupo entero puede descartarse y los visitantes acabar donde no toca."
        ),
    },
    "seo.hreflang_reciprocity.return": {
        "title": "{count} de las {checked} versiones que abrimos no apuntan de vuelta",
        "description": (
            "La declaración solo funciona si la hacen ambas partes: si esta página nombra a "
            "otra como su versión, esa debe nombrar a esta a cambio. Abrimos {checked} de las "
            "{declared} direcciones declaradas aquí y en las que figuran en la evidencia no "
            "encontramos entrada de vuelta. Sobre las que no abrimos no afirmamos nada."
        ),
        "recommendation": (
            "En cada página de la evidencia añada la entrada que apunta de vuelta a esta "
            "dirección. Si se generan desde la misma plantilla, suele ser un solo cambio."
        ),
        "consequence": (
            "El vínculo entre ambas páginas está declarado solo por un lado, así que los "
            "buscadores pueden tratarlas como páginas distintas que compiten entre sí en vez de "
            "como una misma página para dos públicos."
        ),
    },
    "seo.hreflang_conflict.duplicate": {
        "title": "{value} está declarado para {count} direcciones distintas",
        "description": (
            "Un valor puede señalar exactamente una dirección. Cuando señala varias, no se sabe "
            "cuál se quiso decir y Google puede descartar todas las declaraciones de la página, "
            "no solo la contradictoria. La evidencia lista las direcciones en conflicto y de "
            "dónde sale cada una."
        ),
        "recommendation": (
            "Deje una dirección por valor. Mire primero el origen en la evidencia: si dos de "
            "los tres sitios se contradicen, el más antiguo suele venir de una configuración "
            "anterior y puede retirarse."
        ),
        "consequence": (
            "La página da dos respuestas distintas a la misma pregunta, y los buscadores "
            "prefieren descartar el ajuste entero antes que adivinar cuál valía."
        ),
    },
    "seo.hreflang_conflict.x_default": {
        "title": "{value} nombra {count} direcciones distintas",
        "description": (
            "x-default marca la página que se muestra cuando ninguna de las versiones "
            "declaradas encaja con el visitante. Declarar varias deja ese caso sin definir, y "
            "es justo el caso en el que se decide por todos los que usted no previó."
        ),
        "recommendation": (
            "Elija una dirección de reserva y retire las demás. Lo habitual es una página que "
            "decide sola: con selector de país o de variante."
        ),
        "consequence": (
            "A quien llega desde un país que usted no previó puede llevársele a cualquiera de "
            "dos páginas, y cuál de ellas ya no lo decide usted."
        ),
    },
    "seo.hreflang_conflict.canonical": {
        "title": "La página declara sus versiones y a la vez manda la búsqueda a {canonical}",
        "description": (
            "Una página que participa en un conjunto de versiones declaradas debe ser su propio "
            "canonical. Aquí el canonical nombra otra dirección, de modo que las declaraciones "
            "describen una página que el propio sitio pide no mostrar. Ambas instrucciones se "
            "contradicen y Google resuelve la contradicción a su criterio."
        ),
        "recommendation": (
            "Decida cuál es la página buena: haga que el canonical apunte a esta dirección, o "
            "traslade las declaraciones a la página que el canonical nombra."
        ),
        "consequence": (
            "La página dice dos cosas opuestas a la vez: que existe para otros países y que no "
            "es ella la que conviene mostrar. Los buscadores lo resuelven solos, y normalmente "
            "no como usted querría."
        ),
    },
    "seo.hreflang_broken.unreachable": {
        "title": "{count} versiones declaradas no devolvieron una página que funcione",
        "description": (
            "Abrimos esas direcciones nosotros mismos y el servidor no respondió correctamente. "
            "La evidencia recoge cada dirección con el código que devolvió: está medido, no "
            "supuesto. Las direcciones que no abrimos no figuran aquí."
        ),
        "recommendation": (
            "Para cada dirección de la evidencia, corríjala hacia la página que existe hoy o "
            "retírela del conjunto. La causa más común es una dirección heredada de una versión "
            "anterior del sitio."
        ),
        "consequence": (
            "Parte de las direcciones ofrecidas a visitantes de otros países no lleva a ninguna "
            "parte. Quien acabe allí verá un error en lugar de su página."
        ),
    },
    "seo.hreflang_broken.noindex": {
        "title": "{count} versiones declaradas están cerradas a la búsqueda",
        "description": (
            "La dirección se declara como versión que merece mostrarse y a la vez lleva un "
            "noindex, la instrucción de no mostrarla. Ambas se anulan. La instrucción la leímos "
            "en la propia página y la evidencia la cita."
        ),
        "recommendation": (
            "Decida qué se pretendía: quite el noindex de esas páginas o sáquelas del conjunto "
            "de versiones declaradas."
        ),
        "consequence": (
            "Una página se ofrece como la de otro país y a la vez se marca como una que no debe "
            "aparecer en las búsquedas. A los visitantes de ese país no se les llevará allí."
        ),
    },
    "seo.hreflang_missing": {
        "title": "Hay páginas en {count} idiomas ({languages}) y ninguna versión declarada",
        "description": (
            "Las páginas que leímos declaran idiomas distintos entre sí, y en ningún sitio "
            "consta que sean versiones unas de otras: ni en las páginas, ni en una cabecera "
            "HTTP, ni en el mapa del sitio. Si son traducciones del mismo contenido o secciones "
            "separadas no se ve desde fuera, por eso es un motivo para revisar y no una "
            "conclusión. La evidencia ordena las direcciones por idioma."
        ),
        "recommendation": (
            "Si son versiones del mismo contenido, declárelo. Basta con uno de los tres sitios "
            "— Google los considera equivalentes — y para páginas generadas el mapa del sitio "
            "suele salir más barato."
        ),
        "consequence": (
            "A quien busca en español pueden mostrarle la página escrita en otro idioma, porque "
            "nada indica a los buscadores que esas páginas van juntas."
        ),
    },
    # ── Перенаправлення ────────────────────────────────────────────────────
    "seo.redirect_chain": {
        "title": "La dirección pasa por {count} redirecciones antes de abrir la página",
        "description": (
            "El navegador pidió una dirección y fue enviado más de una vez antes de recibir "
            "nada. La evidencia recoge cada salto con su código y la dirección a la que "
            "apuntaba. Una redirección es normal — de http a https, o de una dirección antigua "
            "a su sustituta; una cadena suele ser dos reglas superpuestas con el tiempo, cada "
            "una escrita sin saber de la otra."
        ),
        "recommendation": (
            "Haga que la primera regla apunte directamente a la dirección final, para que la "
            "cadena se reduzca a un solo paso. Si la evidencia lista páginas que enlazan a la "
            "dirección de partida, corrija también esos enlaces: así la redirección desaparece "
            "del camino en lugar de acortarse."
        ),
        "consequence": (
            "Cada salto de más es otra ida y vuelta al servidor antes de que aparezca nada, así "
            "que la página empieza a cargar más tarde de lo necesario. Se nota sobre todo en el "
            "móvil."
        ),
    },
    "seo.redirect_loop.repeated": {
        "title": "El camino de redirecciones vuelve a una dirección por la que ya pasó",
        "description": (
            "Una dirección aparece más de una vez camino de la página: el recorrido se dobló "
            "sobre sí mismo antes de terminar. La evidencia recoge la secuencia completa y las "
            "direcciones repetidas. Este recorrido terminó, así que la página era alcanzable, "
            "pero las reglas describen un círculo y un cambio pequeño lo cierra."
        ),
        "recommendation": (
            "Compare las reglas que producen la dirección repetida de la evidencia. Lo habitual "
            "es que dos de ellas se envíen el tráfico entre sí, y que solo el orden de "
            "evaluación mantenga el círculo abierto."
        ),
        "consequence": (
            "La dirección devuelve al visitante a un punto por el que ya había pasado. Hoy "
            "funciona, pero basta un cambio pequeño en cualquiera de las reglas para que la "
            "página deje de abrirse."
        ),
    },
    "seo.redirect_loop.limit": {
        "title": "{url} siguió redirigiendo y nunca entregó una página",
        "description": (
            "Seguimos {followed} redirecciones desde esta dirección y paramos sin haber "
            "recibido página. Solo podemos afirmar eso: la secuencia no terminó en ese número "
            "de pasos. Dónde daba vueltas, o si las daba, no lo sabemos, porque nunca nos "
            "devolvieron una página que examinar."
        ),
        "recommendation": (
            "Abra esta dirección en un navegador y mire la barra de direcciones. Si se detiene, "
            "la cadena solo es larga y la primera regla debería apuntar a la dirección final; "
            "si sigue cambiando, dos reglas se envían el tráfico entre sí."
        ),
        "consequence": (
            "Esta dirección no abre. Quien siga un enlace hacia ella — una persona, o un "
            "buscador que intenta leer la página — no recibe nada."
        ),
    },
    "seo.redirect_target": {
        "title": "La redirección termina en una dirección que respondió {status}",
        "description": (
            "La regla funciona y envía el navegador, pero el destino no devuelve página. El "
            "código lo leímos nosotros; la evidencia recoge el camino completo. La causa no "
            "suele ser la redirección sino el destino: la página se retiró después que la regla "
            "que apunta a ella."
        ),
        "recommendation": (
            "Apunte la regla a una dirección que exista ahora, o retírela. Si la evidencia "
            "lista páginas que enlazan a la dirección de partida, actualice también esos "
            "enlaces."
        ),
        "consequence": (
            "La dirección lleva al visitante a una página de error. Como la redirección en sí "
            "funciona, el sitio parece tratar bien esa dirección hasta el momento en que "
            "alguien ve el fallo."
        ),
    },
    # ── Узгодженість карти сайту ───────────────────────────────────────────
    "seo.sitemap_consistency.error": {
        "title": "{count} direcciones del sitemap respondieron con un error al abrirlas",
        "description": (
            "El sitemap pide a los buscadores que encuentren estas direcciones, y el servidor "
            "no devolvió página en ellas. Abrimos cada una nosotros; la evidencia recoge la "
            "dirección y el código con que respondió. De las {declared} direcciones declaradas "
            "comprobamos {checked}: el resto no lo abrimos, y aquí no cuenta ni a favor ni "
            "en contra."
        ),
        "recommendation": (
            "Retire estas direcciones del sitemap, o restaure las páginas que había detrás. Un "
            "sitemap generado desde la base de datos suele seguir listando páginas borradas "
            "desde la interfaz."
        ),
        "consequence": (
            "Está señalando a los buscadores páginas que no abren. El esfuerzo de descargarlas "
            "se pierde, y quien llegue a una de esas direcciones por otra vía verá un error."
        ),
    },
    "seo.sitemap_consistency.redirects": {
        "title": "{count} direcciones del sitemap redirigen a otro sitio",
        "description": (
            "Un sitemap debería listar la dirección donde la página vive finalmente, no una que "
            "reenvía a ella. Cada una de estas pasa el navegador más allá; la evidencia recoge "
            "el destino y el número de saltos. De {declared} direcciones declaradas comprobamos "
            "{checked}."
        ),
        "recommendation": (
            "Sustituya cada entrada por la dirección en la que termina — la evidencia trae las "
            "dos. Si el sitemap se genera, el generador probablemente lee una dirección "
            "guardada de antes del último traslado."
        ),
        "consequence": (
            "La lista de direcciones que publica no es aquella a la que la gente llega de "
            "verdad. Cada una cuesta un paso de más antes de que aparezca la página."
        ),
    },
    "seo.sitemap_consistency.noindex": {
        "title": "{count} direcciones del sitemap están cerradas a la búsqueda",
        "description": (
            "Estas páginas llevan una instrucción noindex y además figuran en el sitemap. Las "
            "dos dicen lo contrario: una pide que se encuentre la página, la otra que no se "
            "muestre. Leímos la instrucción en la propia página; la evidencia anota si estaba "
            "en la respuesta del servidor o apareció tras los scripts. Comprobadas {checked} de "
            "{declared} direcciones declaradas."
        ),
        "recommendation": (
            "Decida qué se pretendía. Si la página no debe salir en búsquedas, quítela del "
            "sitemap; si debe, retire el noindex."
        ),
        "consequence": (
            "Su sitio pide que se encuentren estas páginas y, en esas mismas páginas, pide que "
            "no se muestren. Gane la que gane, una de las dos no hace lo que usted quería."
        ),
    },
    "seo.sitemap_consistency.canonical": {
        "title": "{count} direcciones del sitemap señalan otra dirección como la principal",
        "description": (
            "Cada una de estas páginas declara un canonical distinto de la dirección listada en "
            "el sitemap. En el sitemap debería estar la dirección que la propia página "
            "considera principal. La evidencia muestra ambas y si la canónica aparece también "
            "en el sitemap. No afirmamos saber qué dirección elegirá finalmente un buscador. "
            "Comprobadas {checked} de {declared}."
        ),
        "recommendation": (
            "Ponga la dirección canónica en el sitemap en lugar de la actual. Si la evidencia "
            "muestra que la canónica no está en el sitemap, añadirla suele ser la solución."
        ),
        "consequence": (
            "El sitemap y las páginas no coinciden sobre cuál es la dirección real. Usted pide "
            "que se encuentre una versión mientras la página apunta a otra."
        ),
    },
    "seo.sitemap_consistency.not_for_search": {
        "title": "{count} páginas de servicio figuran en el sitemap",
        "description": (
            "Las páginas de acceso, los carritos y los archivos no son para lo que sirve un "
            "sitemap: allí se listan las páginas que conviene encontrar. La evidencia nombra "
            "cada dirección y cómo se clasificó. Comprobadas {checked} de {declared} "
            "direcciones declaradas."
        ),
        "recommendation": (
            "Excluya estas secciones del sitemap. La mayoría de generadores tiene un ajuste "
            "para esto, y suele venir desactivado."
        ),
        "consequence": (
            "La lista de páginas que presenta como dignas de encontrarse incluye páginas que "
            "nadie busca. Eso hace la lista menos útil y no ayuda a las que sí importan."
        ),
    },
    # ── Текст посилань ─────────────────────────────────────────────────────
    "seo.anchor_text": {
        "title": (
            "{count} textos de enlace llevan cada uno a varias páginas distintas ({links} "
            "enlaces)"
        ),
        "description": (
            "La misma redacción se usa en enlaces que llevan a sitios diferentes. La evidencia "
            "recoge cada frase, cuántos enlaces la llevan y a cuántos destinos "
            "distintos "
            "llegan. La navegación y el pie no cuentan — un \"Precios\" repetido en la cabecera "
            "es una referencia, no un defecto —, ni tampoco las páginas cuyo idioma no pudimos "
            "establecer. La propia guía de Google cita \"click "
            "here\", \"read more\", \"website\" y "
            "\"article\" como ejemplos de texto que dice poco al lector."
        ),
        "recommendation": (
            "Dé a cada enlace un texto que nombre su destino: \"Ver la lista de precios 2026\" en "
            "lugar de \"Saber más\". Si la frase viene de una plantilla — las tarjetas de "
            "artículo son el caso habitual —, basta un cambio ahí para que el título de la "
            "página de destino pase al enlace. No amontone términos: escriba como hablaría una "
            "persona."
        ),
        "consequence": (
            "Quien lee no sabe adónde lleva un enlace antes de pulsarlo, así que adivina o lo "
            "salta. En una página llena de etiquetas idénticas, las etiquetas dejan de servir "
            "para elegir."
        ),
    },
    # ── Змішаний вміст ─────────────────────────────────────────────────────
    "tech.mixed_content.blockable": {
        "title": "{count} recursos inseguros en {pages} páginas seguras podrían no cargarse",
        "description": (
            "Estas páginas se sirven por una conexión segura pero piden scripts, hojas de "
            "estilo o marcos incrustados por una insegura. Los navegadores no arreglan esta "
            "clase en silencio: rechazan la petición en lugar de realizarla, así que lo que "
            "hiciera ese recurso simplemente puede no ocurrir. La evidencia recoge cada "
            "recurso, su tipo, si vimos al navegador pedirlo de verdad y si es suyo o de un "
            "tercero."
        ),
        "recommendation": (
            "Apunte cada uno a su dirección segura: la mayoría de proveedores la sirven "
            "desde hace años y el cambio suele ser de un carácter. Si un recurso ajeno no "
            "tiene dirección segura alguna, sustituya o elimine la dependencia: ese "
            "proveedor no puede usarse en una página segura."
        ),
        "consequence": (
            "Parte de la página pide algo que el navegador no traerá por una conexión "
            "desprotegida. Lo que dependiera de ello — un formulario, un widget, una "
            "medición — puede dejar de funcionar sin aviso para todos los visitantes."
        ),
    },
    "tech.mixed_content.upgradeable": {
        "title": "{count} imágenes o medios en {pages} páginas seguras se piden de forma insegura",
        "description": (
            "Los navegadores modernos reescriben estas peticiones a la dirección segura por "
            "su cuenta, así que el visitante no suele notar nada. Eso no equivale a estar "
            "bien configurado: la reescritura solo funciona mientras exista la versión "
            "segura del archivo, y en la página sigue escrita la dirección desprotegida. La "
            "evidencia anota qué vimos hacer al navegador y dice con claridad dónde no "
            "miramos."
        ),
        "recommendation": (
            "Escriba la dirección segura en la página en lugar de confiar en que el "
            "navegador lo corrija. Si los recursos vienen de una plantilla o de la "
            "biblioteca de medios, suele bastar una búsqueda y sustitución sobre el "
            "contenido guardado."
        ),
        "consequence": (
            "La página funciona ahora porque los navegadores corrigen esas direcciones en "
            "silencio. El día que uno de esos archivos no esté en la dirección corregida, "
            "la imagen o el vídeo desaparece sin aviso."
        ),
    },
    "tech.mixed_content.download": {
        "title": "{count} descargas en {pages} páginas seguras se ofrecen por un enlace inseguro",
        "description": (
            "Un archivo ofrecido para descarga desde una página segura se trae por una "
            "conexión desprotegida. Los navegadores tratan este caso aparte y pueden "
            "bloquear la descarga o avisar antes de empezar. La evidencia recoge cada "
            "archivo."
        ),
        "recommendation": (
            "Sirva estos archivos desde la dirección segura del mismo sitio. Si están en "
            "otro host sin dirección segura, muévalos o alójelos usted."
        ),
        "consequence": (
            "Quien pulse en estos archivos puede recibir un aviso o nada en absoluto, en "
            "una página que por lo demás parece totalmente fiable."
        ),
    },
    "tech.mixed_content.runtime": {
        "title": "{count} peticiones inseguras en {pages} páginas las hace un script, no el código",
        "description": (
            "Abrimos estas páginas en un navegador y vimos peticiones a direcciones "
            "desprotegidas que no aparecen en ninguna parte del código. Algo que se ejecuta "
            "en la página construye esas direcciones sobre la marcha, normalmente un script "
            "de medición o de widget. La evidencia trae las direcciones que registramos."
        ),
        "recommendation": (
            "Localice el script que construye cada dirección — el host de la evidencia "
            "suele nombrar al proveedor — y cambie su configuración o sustitúyalo. Buscar "
            "esas direcciones en el código no servirá: se arman durante la ejecución."
        ),
        "consequence": (
            "La página sale al exterior por una conexión desprotegida mientras se presenta "
            "como segura. En el código no se ve, así que sobrevive a cualquier revisión que "
            "solo lea el código."
        ),
    },
    # ── Однаковий вміст під різними адресами ───────────────────────────────
    "seo.duplicate_content.unconsolidated": {
        "title": "{count} grupos de direcciones devuelven el mismo contenido ({pages} páginas)",
        "description": (
            "Cada grupo de abajo reúne direcciones cuyo contenido coincide una vez apartado "
            "el texto de navegación y pie. En ningún sitio se indica cuál es la principal: "
            "ni redirección entre ellas, ni canonical apuntando a un solo miembro. El "
            "contenido duplicado es habitual y no infringe ninguna norma; los buscadores "
            "agrupan esas páginas por su cuenta y eligen una, y cuál eligen no podemos "
            "decírselo. La evidencia recoge cada grupo con sus miembros y lo que declara "
            "cada uno."
        ),
        "recommendation": (
            "Decida qué deben ser estas direcciones. Si son una sola página, conserve una "
            "dirección y envíe las demás a ella, o haga que todos los miembros declaren el "
            "mismo canonical. Si deben ser páginas distintas, déles contenido realmente "
            "distinto. Después apunte los enlaces internos y el sitemap a la versión "
            "elegida."
        ),
        "consequence": (
            "La misma página existe en varias direcciones y nada indica cuál cuenta. Las "
            "visitas, los enlaces y cualquier medición se reparten entre ellas, y usted no "
            "ve a cuál llegó la gente en realidad."
        ),
    },
    "seo.duplicate_content.conflicting": {
        "title": (
            "{count} grupos de páginas idénticas discrepan sobre "
            "cuál dirección es la principal"
        ),
        "description": (
            "Estas direcciones devuelven el mismo contenido, y las propias páginas señalan "
            "direcciones principales distintas, o una que ni siquiera está en el grupo. Es "
            "una contradicción dentro del sitio, no una infracción: los buscadores la "
            "resolverán a su criterio, y su elección puede no coincidir con la suya. La "
            "evidencia muestra lo que declara cada miembro."
        ),
        "recommendation": (
            "Elija una dirección para el grupo y haga que todos los miembros la nombren. Si "
            "un miembro apunta fuera del grupo, compruebe si esa dirección es realmente la "
            "prevista: suele quedar de una estructura anterior."
        ),
        "consequence": (
            "Sus páginas dan respuestas contradictorias sobre cuál versión es la real, así "
            "que la decisión se toma por usted en lugar de tomarla usted."
        ),
    },
    # ── Транспорт: стиснення й протокол ────────────────────────────────────
    "tech.transport.uncompressed": {
        "title": "{count} respuestas de texto llegaron sin comprimir (la mayor {size} KB)",
        "description": (
            "Pedimos contenido comprimido y estas respuestas volvieron sin codificar. La "
            "evidencia recoge cada una: su tipo, lo que pedimos y los dos tamaños que "
            "pudimos establecer. Fíjese en lo que se dice y en lo que no: describe las "
            "respuestas recibidas, no las capacidades del servidor. Solo anunciamos gzip y "
            "deflate, así que un servidor que únicamente ofrezca Brotli nos respondería "
            "igual. Cuántos bytes ahorraría la compresión no lo decimos: haría falta "
            "comprimirlas nosotros, y no lo hicimos."
        ),
        "recommendation": (
            "Compruebe si la compresión está activada para estos tipos de contenido en el "
            "servidor o el CDN. gzip es del todo suficiente: no hace falta pasar a Brotli "
            "ni Zstandard para resolverlo, y sería una decisión aparte con sus propios "
            "matices."
        ),
        "consequence": (
            "Texto que podría viajar comprimido viaja entero, así que cada visitante espera "
            "más bytes de los que la página necesita enviar. Se nota sobre todo en "
            "conexiones móviles lentas."
        ),
    },
    "tech.transport.http1": {
        "title": "{count} respuestas se sirvieron por HTTP/1.1",
        "description": (
            "Nuestro cliente ofrece HTTP/2 y lo negocia con éxito con la mayoría de los "
            "sitios; en estas respuestas la conexión se quedó en el protocolo antiguo. Es "
            "una observación sobre estos intercambios, no una afirmación de que su servidor "
            "carezca de HTTP/2: la versión negociada depende del servidor, de cualquier CDN "
            "en el camino y del cliente. HTTP/2 aprovecha mejor una conexión — varios "
            "intercambios a la vez y cabeceras comprimidas —, aunque que una página "
            "concreta cargue antes depende de la página. HTTP/3 no lo probamos en absoluto, "
            "así que aquí no se dice nada de él."
        ),
        "recommendation": (
            "Revise el ajuste de HTTP/2 en el servidor o en el CDN que tenga delante. En la "
            "mayoría de paneles de alojamiento y CDN es un único interruptor, y en "
            "configuraciones antiguas suele estar apagado."
        ),
        "consequence": (
            "Las peticiones a su sitio usan una forma más antigua y menos eficiente de "
            "compartir una conexión. En páginas que cargan muchos archivos a la vez, eso se "
            "traduce en más espera."
        ),
    },
}


# Avisos de una línea del dominio: por qué parte de la auditoría no corrió y
# por qué un lanzamiento se reintentó o no. Separados de MESSAGES a "
# propósito — el razonamiento está en el catálogo ucraniano.
NOTICES: dict[str, str] = {
    "notice.breadcrumb.hierarchy_unknown": (
        "se leyó demasiado poco del sitio para saber si sus páginas dependen unas de otras, así "
        "que si aquí hacen falta migas de pan sigue sin decidirse"
    ),
    "notice.about_page.candidate_unread": (
        "la página Sobre nosotros a la que apunta el sitio ({anchor}: {url}) no se leyó, "
        "así que sigue sin decidirse si el sitio dice quién está detrás"
    ),
    "notice.about_page.candidate_unreadable": (
        "la página Sobre nosotros en {url} no pudo evaluarse: {reasons} (respuesta {status})"
    ),
    "coverage.reason.about_page_failed_read": "la página no devolvió un documento legible",
    "coverage.reason.about_page_content_shell": (
        "la respuesta era un armazón de aplicación vacío: marcado sin texto principal"
    ),
    "coverage.reason.about_page_login_wall": (
        "el contenido principal era un formulario de acceso y no había un título Sobre nosotros"
    ),
    "coverage.reason.about_page_redirect_placeholder": (
        "el documento solo reenviaba al lector a otro sitio"
    ),
    # degradations
    "notice.accessibility.no_category": (
        "no corrió ninguna comprobación de accesibilidad: el proveedor no devolvió esa "
        "categoría"
    ),
    "notice.accessibility.not_measured": (
        "la accesibilidad no se midió: la medición de velocidad se excluyó de esta auditoría"
    ),
    "notice.crawl.blind": (
        "el sitio no devolvió ninguna página con contenido (estados de respuesta: {statuses})"
    ),
    "notice.coverage.withheld": (
        "Páginas analizadas: {pages}. La puntuación global del sitio se retiene: hay "
        "contenido vivo visible que no se inspeccionó ({reasons}). Una puntuación de lo leído "
        "no puede presentarse como puntuación del sitio."
    ),
    "notice.coverage.limited": (
        "Páginas analizadas: {pages}. Limitación de cobertura: {reasons}."
    ),
    "coverage.reason.robots_restricted": (
        "el rastreo está restringido por las reglas robots.txt del sitio"
    ),
    "coverage.reason.access_failures": (
        "algunas URL accesibles no respondieron — {access} de {attempted}"
    ),
    "coverage.reason.untried_live_candidates": (
        "se descubrieron páginas del sitio que no se abrieron — {untried}"
    ),
    "coverage.reason.no_evidence_of_additional_live_content": (
        "no se encontraron indicios de más contenido vivo"
    ),
    "notice.crawl.failures": (
        "{failed} de {attempted} direcciones no respondieron: lo leído no representa el sitio"
    ),
    "notice.crawl.empty": (
        "{words} palabras en todo el sitio incluso después de ejecutar los scripts; páginas "
        "leídas: {pages}. No hay nada que evaluar"
    ),
    "notice.crawl.empty_static": (
        "la respuesta del servidor contiene {words} palabras: el texto aparece solo tras "
        "ejecutar los scripts ({rendered} palabras en {pages} páginas). Los buscadores ven "
        "esa página; la mayoría de los asistentes, no"
    ),
    "notice.crawl.entry_error": (
        "la dirección de entrada devolvió HTTP {status}: la velocidad se midió en una "
        "página de error, no en el sitio"
    ),
    "notice.crawl.entry_error_stand_in": (
        "la dirección de entrada devolvió HTTP {status}: la velocidad se midió en una "
        "página de error, no en el sitio; como portada se usó {stand_in}"
    ),
    "notice.crawl.shallow": (
        "solo se rastreó la portada, aunque enlaza a páginas internas: el resto no "
        "respondió o no devolvió HTML"
    ),
    "notice.module.excluded": "el módulo se desactivó en las opciones de la auditoría",
    "notice.performance.no_vitals": (
        "los Core Web Vitals no se midieron ({detail}). La puntuación se basa solo en el "
        "tiempo de respuesta del servidor y las señales del HTML estático"
    ),
    "notice.performance.no_metrics": "el proveedor no devolvió métricas: {detail}",
    "notice.performance.partial": "los datos de velocidad están incompletos: {detail}",
    "notice.llm.unavailable": "no corrió el análisis semántico: {detail}",
    "notice.llm.disabled": "el análisis semántico se desactivó en las opciones de la auditoría",
    "notice.llm.facts_unavailable": (
        "el análisis semántico no devolvió datos del negocio: no corrió la comprobación que "
        "depende de ellos"
    ),
    "notice.render.failed": "las páginas no se renderizaron: {detail}",
    "notice.render.disabled": "el renderizado se desactivó en las opciones de la auditoría",
    "notice.analytics.unidentified": (
        "se ve tráfico de medición, pero no se pudo identificar ningún proveedor ({detail}): la "
        "conclusión sobre la analítica queda abierta"
    ),
    "notice.analytics.render_incomplete": (
        "el marcado no lleva ningún contador y las páginas que aún podrían mostrarlo tras "
        "ejecutar los scripts no se renderizaron ({detail})"
    ),
    "notice.check.failed": "la comprobación no corrió por un error",
    "notice.layer.failed": "parte de la auditoría no corrió por un error",
    # retries
    "notice.retry.not_attempted": "no se planificó reintento",
    "notice.retry.scheduled": "intento {next_attempt} de {allowed}",
    "notice.retry.exhausted": "intentos agotados ({attempts}/{allowed})",
    "notice.retry.not_retryable": "no reintentamos fallos del tipo «{failure}»",
}


# Catálogo de planes: lo que compra el cliente, en palabras humanas. Separado
# de MESSAGES y NOTICES a propósito — ver el catálogo ucraniano.
CATALOG: dict[str, str] = {
    "plan.limit.audits": "{count} auditorías al mes",
    "plan.limit.audits_unlimited": "Auditorías ilimitadas",
    "plan.limit.pages": "Hasta {count} páginas por auditoría",
    "plan.limit.sites": "{count} sitios",
    "plan.limit.sites_unlimited": "Sitios ilimitados",
    "plan.limit.schedules": "{count} programaciones",
    "plan.limit.team": "{count} miembros de equipo",
    "plan.limit.history": "{count} días de historial",
    "plan.limit.history_unlimited": "Historial completo",
    "plan.feature.semantic": "Análisis semántico",
    "plan.feature.reports": "Informes en Word",
    "plan.feature.public_reports": "Enlaces públicos de informe",
    "plan.feature.api": "Acceso API",
    "plan.feature.white_label": "Informes con tu marca",
    "plan.cta.start_free": "Empezar gratis",
    "plan.cta.subscribe": "Suscribirse",
    "plan.cta.contact": "Hablar con nosotros",
}
