"""English wording of the findings. Written for the client, not translated word for word."""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    # ── SEO ─────────────────────────────────────────────────────────────────
    "seo.title.missing": {
        "title": "Missing <title>",
        "description": "The page has no title tag — critical for both search and LLMs.",
        "recommendation": "Add a unique 30–60 character title containing the main query.",
        "consequence": (
            "The page has no title of its own. Search engines may build the heading for the "
            "result themselves, out of the page text."
        ),
    },
    "seo.title.too_short": {
        "title": "Title explains nothing ({length} chars)",
        "description": (
            "A title shorter than {min} characters cannot say what the page is about."
        ),
        "recommendation": (
            "Add what people actually search for: the service, the location, the benefit."
        ),
        "consequence": (
            "Next to competitors in the results, such a headline gives no reason to click you."
        ),
    },
    "seo.title.too_long": {
        "title": "Only the first {visible} characters of {length} are shown",
        "description": "Search truncates the tail of the title.",
        "recommendation": (
            "Move the important part to the front — anything past {visible} characters is not "
            "shown."
        ),
        "consequence": (
            "Nobody sees the end of the headline — if the point was there, it does not land."
        ),
    },
    "seo.title.duplicate": {
        "title": "Title repeated across {count} pages",
        "description": "Identical titles make pages indistinguishable in the index.",
        "recommendation": "Give every page its own title.",
        "consequence": (
            "Pages look identical to both search engines and people: it is hard to tell which "
            "one you need."
        ),
    },
    "seo.meta_description.missing": {
        "title": "Missing meta description",
        "description": "Without one, search assembles a snippet from a random chunk of text.",
        "recommendation": "Add a description that fits the visible ~{visible} characters.",
        "consequence": (
            "No meta description was detected for this page. Search engines may build the "
            "snippet from the page text."
        ),
    },
    "seo.h1.missing": {
        "title": "No h1 in the analysed view",
        "description": (
            "The analysed view of the page has no HTML h1 heading. If lower-level headings are "
            "present, the first of them is shown in the evidence. A clear h1 is a recommended "
            "document-structure practice; for understanding and labelling a page it is one "
            "possible input among several signals, alongside the title and others."
        ),
        "recommendation": (
            "Consider one clear h1 carrying the page topic — often promoting the existing first "
            "heading is enough."
        ),
        "consequence": (
            "The page's main heading is not marked as the top-level one in the code. Programs "
            "that read structure rely on other clues — the tab title and the subheadings."
        ),
    },
    "seo.h1.no_headings": {
        "title": "No HTML headings (h1–h6) found",
        "description": (
            "The analysed view of the page contains no non-empty HTML h1–h6 headings. Headings "
            "organise content for readers and assistive technologies; this statement covers HTML "
            "headings specifically — other markup mechanisms were not assessed."
        ),
        "recommendation": (
            "Add a clear heading structure appropriate to this page: one main heading and section "
            "subheadings."
        ),
        "consequence": (
            "The page has no marked section structure. Readers and screen readers have nothing to "
            "hold on to except continuous text."
        ),
    },
    "seo.h1.multiple": {
        "title": "Multiple h1 elements ({count}); visibility not assessed",
        "description": (
            "The analysed view contains {count} non-empty h1 elements. Their CSS visibility was "
            "not assessed: some may be template duplicates for different layouts. A single clear "
            "primary h1 is a common best practice, but multiple h1 elements are permitted HTML, "
            "and this observation alone does not establish a Search problem."
        ),
        "recommendation": (
            "If the duplicates are unintentional, keep one primary h1 and demote the rest to "
            "subheadings."
        ),
        "consequence": (
            "The main heading is marked more than once. This is an observation about the page's "
            "code, not detected harm."
        ),
    },
    "seo.heading_hierarchy": {
        "title": "Heading jump H{previous} → H{level}",
        "description": "Skipping a level makes the structure harder to parse machine-side.",
        "recommendation": "Do not skip heading levels.",
        "consequence": (
            "The page structure looks illogical to the software reading it, making the text "
            "harder to split into meaningful blocks."
        ),
    },
    "seo.canonical.missing": {
        "title": "No rel=canonical",
        "description": "",
        "recommendation": "Add a self-referencing canonical to every indexable page.",
        "consequence": (
            "If the same page is reachable at several addresses, search may treat them as "
            "different pages and split the ranking weight."
        ),
    },
    "seo.canonical.mismatch": {
        "title": "Canonical points to a different page",
        "description": "This removes the page from the index — make sure that is intended.",
        "recommendation": "Check that the canonical does not point to the homepage by mistake.",
        "consequence": (
            "The page tells search engines it is not the primary version, so it may disappear "
            "from results entirely."
        ),
    },
    "seo.noindex": {
        "title": "The page is closed to search",
        "description": (
            "The markup tells search engines not to show this page. Often that is "
            "deliberate — paid landing pages, event archives, pages meant for "
            "internal traffic. We can see the instruction but not the intent, so "
            "check whether it belongs here."
        ),
        "recommendation": (
            "If the page is meant to bring people in from search, remove the "
            "instruction. If it is closed on purpose, leave it as it is."
        ),
        "consequence": (
            "While the instruction stands, this page brings no visitors from search. "
            "If that is intended, all is well; if not, the work put into it does "
            "nothing."
        ),
    },
    "seo.render_delta.indexing": {
        "title": "Indexing signals differ after JavaScript runs: {fields}",
        "description": (
            "The server response and the page after JavaScript execution disagree on signals that "
            "decide which URL gets indexed. The evidence holds both values. Google does render "
            "JavaScript, but its documentation says the page waits in a render queue that \"can "
            "take longer\" than seconds, and that \"not all bots can run JavaScript\" — so a "
            "crawler may act on the response version."
        ),
        "recommendation": (
            "Check which of the two values is the one you intend, and serve that one in the HTML "
            "response rather than setting it from a script."
        ),
        "consequence": (
            "Two different instructions exist for the same page, and which one is followed "
            "depends on whether the visiting system runs scripts."
        ),
    },
    "seo.render_delta.identity": {
        "title": "How the page introduces itself changes after JavaScript: {fields}",
        "description": (
            "The heading or the text shown in search results is not the same before and after "
            "scripts run. The evidence holds both values. A system that does not execute "
            "JavaScript sees only the response version."
        ),
        "recommendation": (
            "Put the final heading and description in the HTML the server sends, and let scripts "
            "adjust the page rather than define what it is."
        ),
        "consequence": (
            "Some systems describe your page one way and some another, so the name people see is "
            "not always the one you wrote."
        ),
    },
    "seo.render_delta.markup": {
        "title": "Structured data differs after JavaScript runs",
        "description": (
            "The machine-readable markup on the page is not the same before and after scripts "
            "run: types or identifiers appear, disappear or change. The evidence lists both sets."
        ),
        "recommendation": (
            "Emit the markup in the server response. Anything that only appears after scripts is "
            "read only by systems that run them."
        ),
        "consequence": (
            "The facts you publish about your business are readable to some systems and invisible "
            "to others."
        ),
    },
    "seo.render_delta.links": {
        "title": "{count} internal links exist only after JavaScript runs",
        "description": (
            "These links are absent from the server response and appear only in the rendered "
            "page. The evidence lists them. Google follows links it finds after rendering, but "
            "its own documentation notes that not all bots run JavaScript."
        ),
        "recommendation": (
            "Serve these links as ordinary anchors in the HTML response. Scripts may still "
            "enhance the navigation on top of that."
        ),
        "consequence": (
            "Parts of the site are reachable only for systems that run scripts; for the rest "
            "those pages are not linked from here at all."
        ),
    },
    "seo.robots_txt.missing": {
        "title": "robots.txt is missing",
        "description": "Crawlers get no instructions and no pointer to your sitemap.",
        "recommendation": "Add /robots.txt with a Sitemap directive.",
        "consequence": (
            "Search engines arrive without instructions and do not know where to find your "
            "sitemap."
        ),
    },
    "seo.robots_txt.disallow_all": {
        "title": "robots.txt blocks the entire site",
        "description": "`Disallow: /` for `User-agent: *` blocks all crawling.",
        "recommendation": "Remove Disallow: / if the site is meant to be in search.",
        "consequence": (
            "robots.txt forbids crawling the whole site. Search engines will not read the "
            "pages; an address may still show up in results, but with no description and no "
            "content behind it."
        ),
    },
    "seo.robots_txt.no_sitemap": {
        "title": "robots.txt has no Sitemap directive",
        "description": "",
        "recommendation": "Add a `Sitemap: https://.../sitemap.xml` line.",
        "consequence": (
            "Search engines get no hint about where your page list lives, so they discover "
            "pages more slowly."
        ),
    },
    "seo.sitemap.missing": {
        "title": "sitemap.xml not found",
        "description": "",
        "recommendation": "Generate an XML sitemap and reference it from robots.txt.",
        "consequence": (
            "No sitemap was found: it is absent from the standard locations, and the site did not "
            "specify another address."
        ),
    },
    "seo.sitemap.invalid": {
        "title": "sitemap.xml does not parse",
        "description": "",
        "recommendation": "Fix the XML — crawlers ignore an invalid sitemap.",
        "consequence": (
            "The sitemap exists but cannot be read: the file is not valid XML. It will be of no "
            "use until the format is fixed."
        ),
    },
    "seo.sitemap.empty": {
        "title": "sitemap.xml is empty",
        "description": "",
        "recommendation": "Add your page URLs to the sitemap.",
        "consequence": "The sitemap contains no addresses, so it is not doing its job.",
    },
    "seo.sitemap.coverage": {
        "title": "{count} crawled pages are absent from the sitemap",
        "description": "",
        "recommendation": "Keep sitemap generation in sync with the real site structure.",
        "consequence": (
            "Some pages are missing from the sitemap, so search learns about them later or not "
            "at all."
        ),
    },
    "seo.broken_links": {
        "title": "{count} internal URLs return an error",
        "description": (
            "We followed these links ourselves and the server answered with an error. The "
            "evidence lists each broken destination together with the pages that link to it, "
            "the anchor text of each link, and whether the link was in the server's response or "
            "appeared only after scripts ran. A destination shown with no source pages was not "
            "linked from anywhere we read — it came from the sitemap."
        ),
        "recommendation": (
            "Work from the evidence: for each destination it names the pages that point at it. "
            "Update those links to an address that works, or remove them. Where several pages "
            "link to the same dead address, the link usually sits in a shared template."
        ),
        "consequence": "Visitors land on broken pages — lost visits and a poor impression.",
    },
    "seo.https.missing": {
        "title": "Site is not on HTTPS",
        "description": "HTTP sites are flagged as insecure and rank worse.",
        "recommendation": "Enable TLS and 301-redirect HTTP to HTTPS.",
        "consequence": (
            "Browsers mark the site as insecure and show a warning before the content. What a "
            "visitor does with that warning we do not measure."
        ),
    },
    "seo.https.invalid_cert": {
        "title": "The HTTPS certificate is not valid",
        "description": (
            "The site loads only when certificate verification is switched off. The usual "
            "causes are an incomplete intermediate chain, a self-signed certificate, or an "
            "expired one. Search crawlers skip sites in this state."
        ),
        "recommendation": (
            "Reissue the certificate and serve the full intermediate chain with it. Confirm "
            "the result on ssllabs.com/ssltest — the grade should be A."
        ),
        "consequence": (
            "Instead of your site, visitors get a red warning page with a «Back to safety» "
            "button. Almost everyone takes it."
        ),
    },
    "seo.https.no_hsts": {
        "title": "No HSTS header",
        "description": "",
        "recommendation": "Add `Strict-Transport-Security: max-age=31536000`.",
        "consequence": (
            "The first visit may travel over an unprotected connection — a small but real "
            "security gap."
        ),
    },
    "seo.image_alt": {
        "title": "{without_alt} of {total} images have no alt",
        "description": "Alt text is both accessibility and a textual signal for models.",
        "recommendation": "Describe the image content; keep alt=\"\" for decorative ones.",
        "consequence": (
            "Blind visitors hear nothing about the image: a screen reader takes the description "
            "from that attribute. Text that exists only inside a picture is not part of the "
            "page content."
        ),
    },
    "seo.thin_content": {
        "title": "Only {word_count} words on the page",
        "description": (
            "Little text is a weak signal for both search and LLM citation. It may also mean "
            "the content is rendered client-side."
        ),
        "recommendation": "Grow the main copy to {threshold}+ words, or verify SSR.",
        "consequence": (
            "There is too little text for the page to be considered useful: it ranks weakly and "
            "there is almost nothing to quote."
        ),
    },
    "seo.click_depth": {
        "title": "Few links from this page onward: {internal_links}",
        "description": (
            "This page links to {internal_links} other pages on the site. Counted on the "
            "links found on this page, so it says nothing about how many pages link TO it "
            "— a page the whole menu points at can still lead nowhere itself."
        ),
        "recommendation": (
            "Add links from this page to the pages a reader would naturally want next: "
            "related services, the relevant category, the case study behind the claim."
        ),
        "consequence": (
            "Someone who lands here has almost nowhere to go next, so they leave instead "
            "of looking further into what you offer."
        ),
    },
    "cro.no_action": {
        "title": "Nothing on this page to act on",
        "description": (
            "A page that offers something has no form, no clickable phone or email, "
            "and no link to ordering, a cart or contacts. Someone the page has "
            "convinced has nothing to use."
        ),
        "recommendation": (
            "Give the page one obvious next step and repeat it after the main text: "
            "an order button, an enquiry form, or the phone number as a link. One "
            "clear step works better than three."
        ),
        "consequence": (
            "This page offers no action outside the menu and the footer: no form, no button, no "
            "contact in the text itself. Someone who finished reading and wants to get in touch "
            "has to go looking."
        ),
    },
    "cro.phone_not_tappable": {
        "title": "The phone number is printed but cannot be dialled",
        "description": (
            "The number appears on the site but is never marked up as a dial link. "
            "On a phone the visitor has to memorise it, leave the site and type it "
            "by hand. Pages where we saw this: {count}."
        ),
        "recommendation": (
            "Mark the number up as a tel:+… link everywhere it is shown — header, "
            "footer and the contact page. Half an hour of work."
        ),
        "consequence": (
            "Most visitors arrive on a phone. Instead of tapping to call, they have "
            "to copy the number down — and some of them simply will not."
        ),
    },
    "seo.topic_islands": {
        "title": "{count} pages on one subject never link to each other",
        "description": (
            "We read {count} pages covering the same ground and none mentions another. "
            "The only way from one to the next is the menu or an index page — the "
            "connections by meaning, the ones that show the subject was worked "
            "through, are missing."
        ),
        "recommendation": (
            "Add contextual links BETWEEN GENUINELY RELATED pages where they actually help the "
            "reader: from one case study to an adjacent one, from an article to the piece that "
            "continues it. There is no need to link every page in the section to every other — a "
            "link added to satisfy a rule helps neither a person nor a search engine."
        ),
        "consequence": (
            "The pages do not reinforce each other. Someone reading one of them is "
            "never shown the next one they need, and the site reads as a pile of "
            "separate sheets rather than proof the company knows its field."
        ),
    },
    "seo.orphan_pages": {
        "title": "{count} pages in the sitemap have no links pointing to them",
        "description": (
            "The sitemap declares these pages, but nothing on the site leads to them. "
            "Search engines can find them; a visitor never will, and their standing "
            "rests on the sitemap alone — the weakest signal a site can send."
        ),
        "recommendation": (
            "Link to these pages from where they belong: the menu, their parent "
            "category, or the body text of related pages. If a page is not meant for "
            "visitors, take it out of the sitemap instead."
        ),
        "consequence": (
            "These pages exist, but there is no way to reach them from the site "
            "itself. Visitors never see them, and the work that went into them is "
            "wasted."
        ),
    },
    "seo.links_to_noindex": {
        "title": "{count} pages are linked to but hidden from search",
        "description": (
            "The site puts a page in its navigation and at the same time forbids "
            "search engines to show it. One of the two is wrong: either the page "
            "matters to people and should be visible, or it is internal and does not "
            "belong in the menu."
        ),
        "recommendation": (
            "Decide which of the two each page is. If it matters, remove the "
            "indexing ban; if it is internal, remove the link from navigation."
        ),
        "consequence": (
            "A visitor follows a link to a page that search engines are told to hide. "
            "The site contradicts itself, and part of the path to a purchase leads "
            "nowhere."
        ),
    },
    "seo.viewport": {
        "title": "No meta viewport",
        "description": "Without a viewport the page does not adapt to mobile screens.",
        "recommendation": (
            "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."
        ),
        "consequence": (
            "On a phone the page shows up as a shrunken desktop layout — uncomfortable to read, "
            "and Google takes that into account."
        ),
    },
    "seo.sitemap.lastmod": {
        "title": "Sitemap has no modification dates",
        "description": "",
        "recommendation": "Add lastmod to every URL and update it when the page changes.",
        "consequence": (
            "After you update the site, the map carries no sign of what changed — there is "
            "nothing in it to tell a new page from an old one."
        ),
    },
    "seo.clean_url.uppercase": {
        "title": "Uppercase letters in the page URL",
        "description": (
            "URLs are case-sensitive: /Services and /services are technically different pages."
        ),
        "recommendation": "Lowercase the path and add a 301 redirect from the old variant.",
        "consequence": (
            "Search may treat spelling variants as different pages and split their authority."
        ),
    },
    "seo.clean_url.underscore": {
        "title": "Underscores in the page URL",
        "description": "",
        "recommendation": "Replace underscores with hyphens and add a 301 redirect.",
        "consequence": (
            "Words in the address run together, so search understands the page topic less well."
        ),
    },
    "seo.clean_url.query": {
        "title": "Query parameters in the page URL",
        "description": (
            "The same content reachable with different parameters looks like several pages."
        ),
        "recommendation": "Move to clean paths, or consolidate parameters with a canonical.",
        "consequence": (
            "The same content is reachable at several addresses. Search engines may treat them "
            "as different pages and split the signals between them."
        ),
    },
    # ── AI-ready / LLMO ─────────────────────────────────────────────────────
    "ai.llms_txt.missing": {
        "title": "No llms.txt (optional opportunity)",
        "description": (
            "llms.txt is a markdown file at the site root that briefly describes the site for AI "
            "agents: what it is, key sections, links to the main pages. It is an emerging "
            "convention with growing adoption, but still a proposal rather than a standard: the "
            "file is optional and experimental, and its absence is neither a known Search ranking "
            "problem nor a requirement for visibility in language models. Its absence does not "
            "prevent AI systems from accessing or citing the website."
        ),
        "recommendation": (
            "Worth considering primarily when the site has documentation, reference or other "
            "structured content. Create /llms.txt: an H1 with the product name, a short "
            "description, and `##` sections listing links to key pages. It guarantees nothing — "
            "not crawling, not citation, not rankings."
        ),
        "consequence": (
            "Services such as ChatGPT or Perplexity form their picture of a site from whatever "
            "they find themselves. The file may make that easier — but its absence takes away "
            "neither access nor citations."
        ),
    },
    "ai.llms_txt.no_h1": {
        "title": "llms.txt has no H1",
        "description": "",
        "recommendation": (
            "The first line should be `# Project name`. The file itself remains an experimental "
            "option, not a requirement."
        ),
        "consequence": (
            "The llms.txt file starts without a name, although the specification asks for one "
            "on the first line. Whoever reads the file will not see which product it belongs "
            "to."
        ),
    },
    "ai.llms_txt.thin": {
        "title": "llms.txt is too sparse",
        "description": "The file exists but gives the model no map of the site.",
        "recommendation": (
            "Add `##` sections and 5+ links to key pages. The file itself remains an experimental "
            "option, not a requirement."
        ),
        "consequence": (
            "The summary file exists but does not show the model what the site consists of, so "
            "it adds little."
        ),
    },
    "ai.jsonld.missing": {
        "title": "No structured data detected in the server responses",
        "description": (
            "No JSON-LD or Microdata was detected in the analysed server responses; RDFa was not "
            "assessed. Schema.org markup is optional: it gives machines explicit clues about page "
            "meaning and makes pages eligible for rich results, but it guarantees neither and is "
            "not a requirement for visibility in AI services."
        ),
        "recommendation": (
            "If you decide to add markup, start with JSON-LD on the home page: Google recommends "
            "that format as the easiest to maintain."
        ),
        "consequence": (
            "Machines build their picture of a page from plain text alone. Explicit markup clues "
            "could make that easier — but their absence costs the site neither search presence "
            "nor mentions."
        ),
    },
    "ai.jsonld.invalid": {
        "title": "Invalid JSON-LD",
        "description": "The ld+json block does not parse — the markup is ignored entirely.",
        "recommendation": "Fix the JSON syntax inside the application/ld+json script.",
        "consequence": (
            "The machine-readable description of the page cannot be read, so the effort spent "
            "adding it was wasted."
        ),
    },
    "ai.jsonld.no_type": {
        "title": "JSON-LD without @type",
        "description": "",
        "recommendation": "Every entity needs an @type from schema.org.",
        "consequence": (
            "The data on the page is unlabelled — software sees a set of values but does not "
            "know what they mean."
        ),
    },
    "ai.schema.organization": {
        "title": "No organization or person identity entity in the markup",
        "description": (
            "Structured data was detected, but no identity entity — Organization or any of its "
            "subtypes, Person, or WebSite — was observed on the home page or About pages in the "
            "analysed sample. Such an entity is optional and has no required properties."
        ),
        "recommendation": (
            "For a business, institution or personal brand, consider adding the applicable "
            "Organization subtype or Person/WebSite markup on the home or About page. Add only "
            "the properties that apply to you."
        ),
        "consequence": (
            "There is no explicit machine-readable card saying who is behind the site — machines "
            "infer it from text. This is an improvement opportunity, not a fault."
        ),
    },
    "ai.entity.sameas": {
        "title": "No sameAs (entity signals)",
        "description": (
            "sameAs links your brand to external knowledge bases (Wikidata, LinkedIn, GitHub, "
            "Crunchbase) — the primary identity signal."
        ),
        "recommendation": "Add sameAs with links to the brand's official profiles.",
        "consequence": (
            "There is no confirmation that this is the same brand as on Wikipedia or LinkedIn, "
            "so models are less confident about your data."
        ),
    },
    "ai.schema.breadcrumb": {
        "title": "No BreadcrumbList",
        "description": "Breadcrumbs show the model where a page sits in the site hierarchy.",
        "recommendation": "Add BreadcrumbList to inner pages.",
        "consequence": (
            "It is unclear which section of the site the page belongs to, so context is lost."
        ),
    },
    "ai.schema.faq": {
        "title": "{count} questions on the page with no FAQPage markup",
        "description": (
            "Headings are phrased as questions, yet there is no FAQPage or QAPage markup. "
            "Question–answer pairs are the format language models handle best: marked up, "
            "they can be lifted and quoted whole."
        ),
        "recommendation": (
            "Wrap the existing question–answer pairs in FAQPage markup. No rewriting "
            "needed — the content is already there, only the markup is missing."
        ),
        "consequence": (
            "The answers are already written on the page, but presented in a way nothing "
            "can recognise — so models quote a competitor who marked the same thing up."
        ),
    },
    "ai.schema.content_type": {
        "title": "Content page without Article/Product markup",
        "description": "",
        "recommendation": (
            "Add Article (headline, author, datePublished, dateModified) or Product, depending "
            "on the page type."
        ),
        "consequence": (
            "A substantial page is not labelled as an article or a product, so it does not "
            "appear in rich search results."
        ),
    },
    "ai.opengraph": {
        "title": "Missing OG tags: {missing}",
        "description": "",
        "recommendation": "Fill in OpenGraph — both social networks and LLM crawlers read it.",
        "consequence": (
            "Links to your site shared in messengers and social networks will have no proper "
            "image or description."
        ),
    },
    "ai.lang": {
        "title": "Page language not declared",
        "description": "The lang attribute helps interpret and index the text correctly.",
        "recommendation": "Add <html lang=\"en\"> (or the matching language code).",
        "consequence": (
            "The page language is not declared, so it may be shown to the wrong audience or "
            "offered for translation."
        ),
    },
    "ai.opengraph.no_image": {
        "title": "No og:image",
        "description": "",
        "recommendation": "Add a 1200×630 image in the og:image meta tag.",
        "consequence": (
            "Links to your site in messengers and social networks show as an empty rectangle, "
            "so fewer people click them."
        ),
    },
    "ai.schema.contact.missing": {
        "title": "No LocalBusiness / ContactPoint markup",
        "description": (
            "For a local business this is the main way to hand a machine your address, phone "
            "and opening hours."
        ),
        "recommendation": (
            "Add JSON-LD LocalBusiness with address, telephone, openingHoursSpecification and "
            "geo."
        ),
        "consequence": (
            "Contact details appear on the site but are not marked up as structured "
            "business data."
        ),
    },
    "ai.schema.contact.incomplete": {
        "title": "LocalBusiness missing fields: {missing}",
        "description": "",
        "recommendation": "Complete the markup — these fields feed search cards and AI answers.",
        "consequence": (
            "Your business card in search will be incomplete: some data simply has nowhere to "
            "come from."
        ),
    },
    "ai.schema.graph": {
        "title": "JSON-LD blocks are not linked to each other",
        "description": "Several separate blocks without @id read as unrelated entities.",
        "recommendation": (
            "Give each block an @id and reference them across blocks to form one graph."
        ),
        "consequence": (
            "A machine sees scattered fragments of data instead of one coherent picture of the "
            "company."
        ),
    },
    "ai.twitter_card": {
        "title": "No Twitter/X card",
        "description": "",
        "recommendation": (
            "Add <meta name=\"twitter:card\" content=\"summary_large_image\"> plus "
            "twitter:title/description/image."
        ),
        "consequence": (
            "On X and several messengers your link appears without an image or description."
        ),
    },
    # ── Fitness to be quoted ────────────────────────────────────────────────
    "llm.direct_answer": {
        "title": "Legacy check: opening content structure",
        "description": (
            "An earlier Crawldy version flagged the structure of text near the beginning of the "
            "page. This heuristic has since been retired because it could confuse navigation, "
            "punctuation and page layout with content quality. It is no longer used in new audits "
            "or scoring."
        ),
        "recommendation": (
            "No action is required based on this legacy finding alone. Review the page for "
            "clarity for visitors using the current findings and evidence in the report."
        ),
        "consequence": (
            "This entry remains from an earlier audit version and does not affect new results."
        ),
    },
    "llm.structure": {
        "title": "Long copy ({word_count} words) with no subheadings",
        "description": "A solid wall of text is harder to segment into quotable chunks.",
        "recommendation": "Split the content into H2/H3 sections; add lists and tables.",
        "consequence": (
            "A solid wall of text: hard for a person to read, and hard for a model to pull a "
            "short fragment out of."
        ),
    },
    "llm.about_page": {
        "title": "No About page",
        "description": (
            "The About page is the main source a model uses to form its view of the "
            "organisation and its authority."
        ),
        "recommendation": "Create /about describing the company, its history and team.",
        "consequence": (
            "Among the pages we read, none has an address, title or link text that looks like "
            "an About page."
        ),
    },
    "llm.contact_page": {
        "title": "No Contact page",
        "description": (
            "Contact details are a baseline trust signal (E-E-A-T) for search and models."
        ),
        "recommendation": "Add /contact with an address, email and ContactPoint markup.",
        "consequence": (
            "Without visible contact details the site looks less trustworthy to both visitors "
            "and search engines."
        ),
    },
    "llm.brand_consistency": {
        "title": "Brand name is inconsistent",
        "description": (
            "The name in JSON-LD does not appear in the homepage title — a model may fail to "
            "connect the site to the brand."
        ),
        "recommendation": "Use identical brand spelling in title, H1 and schema.org.",
        "consequence": (
            "The brand name is spelled differently in different places, making it harder to "
            "associate with you."
        ),
    },
    "llm.stale_content": {
        "title": "Nothing on the site has been updated for {years} years",
        "description": (
            "Not one of the dated pages we read has been touched in {years} years. "
            "The question is not about any single page — a guide can stay accurate "
            "for years — but about the site as a whole."
        ),
        "recommendation": (
            "Go through the main pages and refresh what has aged: prices, what the "
            "service includes, recent work. Put the update date in the page markup, "
            "or nobody will know anything changed."
        ),
        "consequence": (
            "The newest date we found on the site is years old. A reader has no way to tell "
            "whether the information still holds."
        ),
    },
    "llm.stale_content.sparse": {
        "title": "The newest dated material is {years} years old",
        "description": (
            "Dates appear on only {dated} of the {read} pages we read, so this is a statement "
            "about the dates we found, not about the whole site. A page without a date is not an "
            "old page: many sites simply do not publish them."
        ),
        "recommendation": (
            "If the material has been updated, record the update date in the page markup — "
            "without it there is nothing to read the date from. If it has not, start with the "
            "pages people read most."
        ),
        "consequence": (
            "When the only visible dates are years old, a reader assumes the site is no longer "
            "looked after, even when that is not true."
        ),
    },
    "llm.authorship": {
        "title": "Content page without author/datePublished",
        "description": "Authorship and dates are freshness and credibility signals.",
        "recommendation": "Add author, datePublished and dateModified to the Article markup.",
        "consequence": (
            "It is not visible who wrote this and when, so the material reads as less reliable."
        ),
    },
    "llm.crawler_blocked.search": {
        "title": "{count} AI search crawlers are blocked: {crawlers}",
        "description": (
            "These crawlers index pages so an assistant can find and cite them. robots.txt "
            "currently prevents them from reaching the pages listed in the evidence. This is "
            "about access, not about whether any assistant mentions you — that we do not measure."
        ),
        "recommendation": (
            "If the block was not intended, allow these user-agents in robots.txt. Keep them "
            "separate from training crawlers: you can permit search access while still refusing "
            "training."
        ),
        "consequence": (
            "The assistants people ask cannot open these pages, which may reduce your chances of "
            "being shown as a source when someone asks about what you do."
        ),
    },
    "llm.crawler_blocked.grounding": {
        "title": "{count} AI grounding crawlers are blocked: {crawlers}",
        "description": (
            "These tokens control whether content the vendor crawls from your site may be used "
            "for grounding — supplied to the model at prompt time — inside that vendor's own AI "
            "products. Google-Extended covers Gemini Apps and Vertex AI. robots.txt prevents them "
            "from reaching the pages listed in the evidence. Google states this token does not "
            "affect inclusion or ranking in Google Search, so this is not a Search problem."
        ),
        "recommendation": (
            "If the block was not intended, allow these user-agents. Note that the same token "
            "also governs model training, so allowing it permits both; there is no way to "
            "separate them in robots.txt today."
        ),
        "consequence": (
            "Content collected from these pages may not be used as a source when Gemini answers a "
            "question. This says nothing about other assistants, and your position in ordinary "
            "Google results is unaffected."
        ),
    },
    "llm.crawler_blocked.user": {
        "title": "{count} assistant fetchers are blocked: {crawlers}",
        "description": (
            "These agents fetch a page when a person explicitly asks an assistant about it. "
            "robots.txt prevents them from reaching the pages listed in the evidence."
        ),
        "recommendation": (
            "If this was not intended, allow these user-agents. They act on a direct request from "
            "a person, so blocking them mainly affects someone who already wanted to read your "
            "page."
        ),
        "consequence": (
            "Your site forbids this agent, so when a visitor asks the assistant to look at your "
            "page, it is not allowed to fetch it. What the assistant answers instead we do not "
            "observe."
        ),
    },
    "llm.crawler_blocked.training": {
        "title": "{count} AI training crawlers are blocked: {crawlers}",
        "description": (
            "These crawlers collect material for training models. Only training crawlers are "
            "blocked here — search and assistant access are unaffected. Refusing training is a "
            "legitimate choice about your own content, and this entry is recorded so it stays a "
            "decision rather than an accident."
        ),
        "recommendation": (
            "Nothing needs fixing if this was deliberate. If it was not, allow these user-agents; "
            "they control training access only."
        ),
        "consequence": (
            "Your texts are kept out of model training. This is a choice about your content, not "
            "a fault on the site."
        ),
    },
    "llm.client_rendered": {
        "title": "Content appears to be client-rendered",
        "description": (
            "The static HTML holds almost no text despite a large amount of markup. Most LLM "
            "crawlers do not execute JavaScript and will see an empty page."
        ),
        "recommendation": "Enable SSR/SSG or prerendering for key pages.",
        "consequence": (
            "In the server's own answer the page is almost empty: the text appears only after "
            "scripts run. A reader that does not run them sees the empty version."
        ),
    },
    # ── Speed ───────────────────────────────────────────────────────────────
    "perf.core_web_vitals.lcp": {
        "title": "LCP = {value}{unit} ({strategy})",
        "description": (
            "Largest Contentful Paint — time to render the main element. The «good» threshold "
            "is {threshold}{unit}."
        ),
        "recommendation": (
            "Optimise the hero image (preload, modern format) and remove render-blocking "
            "CSS/JS."
        ),
        "consequence": (
            "The main content loads too slowly. Visitors have to wait longer and may leave "
            "before it finishes loading."
        ),
    },
    "perf.core_web_vitals.inp": {
        "title": "INP = {value}{unit} ({strategy})",
        "description": (
            "Interaction to Next Paint — response delay to a user action. The «good» threshold "
            "is {threshold}{unit}."
        ),
        "recommendation": "Break up long JS tasks and reduce the amount of hydration.",
        "consequence": (
            "The page noticeably stalls in response to clicks — it feels sluggish."
        ),
    },
    "perf.core_web_vitals.cls": {
        "title": "CLS = {value}{unit} ({strategy})",
        "description": (
            "Cumulative Layout Shift — visual instability during load. The «good» threshold is "
            "{threshold}{unit}."
        ),
        "recommendation": "Set width/height on images and reserve space for banners and fonts.",
        "consequence": (
            "While images and fonts load, the text moves under the reader’s eyes, which makes "
            "the page awkward to read."
        ),
    },
    "perf.core_web_vitals.ttfb": {
        "title": "TTFB = {value}{unit} ({strategy})",
        "description": (
            "Time To First Byte — server response time. The «good» threshold is "
            "{threshold}{unit}."
        ),
        "recommendation": "Enable caching/CDN and optimise database queries.",
        "consequence": (
            "The server responds too slowly, delaying the rest of the page."
        ),
    },
    "perf.core_web_vitals.tbt": {
        "title": "TBT = {value}{unit} ({strategy})",
        "description": (
            "Total Blocking Time — main thread blocking. The «good» threshold is "
            "{threshold}{unit}."
        ),
        "recommendation": "Reduce the amount and weight of JavaScript.",
        "consequence": (
            "The page looks loaded but does not yet respond to input — the most irritating "
            "state for a visitor."
        ),
    },
    "perf.mobile_gap": {
        "title": "On a phone the site is twice as slow as on a computer",
        "description": (
            "We measured the site twice: as a computer sees it and as a phone does. On a "
            "computer it scores {desktop} out of 100, on a phone {mobile}. Google ranks "
            "sites by the mobile version, and most people arrive on a phone too."
        ),
        "recommendation": (
            "Compare the evidence below: it lists the metrics more than twice as bad on "
            "mobile. The usual culprits are heavy images and the amount of JavaScript, "
            "which a phone takes far longer to process than a desktop."
        ),
        "consequence": (
            "You look at your site on a computer and everything seems fine. Your customers "
            "look at it on a phone and see something else — and some of them will not wait."
        ),
    },
    "perf.server_response.slow": {
        "title": "Server responds slowly ({median} ms)",
        "description": (
            "Median time to first byte across the crawled pages. The «good» threshold is "
            "{threshold} ms. This is delay before the browser can paint anything."
        ),
        "recommendation": (
            "Enable server-side or CDN caching and look for slow database queries."
        ),
        "consequence": "Every visitor waits on a blank screen before anything appears.",
    },
    "perf.server_response.very_slow": {
        "title": "Server responds very slowly ({median} ms)",
        "description": (
            "Median time to first byte across the crawled pages, against a «good» threshold of "
            "{threshold} ms. At this latency every other metric suffers: the browser is simply "
            "waiting."
        ),
        "recommendation": (
            "This is the first bottleneck to fix. Profile page generation on the server, then "
            "add caching and a CDN."
        ),
        "consequence": (
            "The server responds too slowly, delaying the rest of the page."
        ),
    },
    "perf.lighthouse_score": {
        "title": "Lighthouse performance {score} ({strategy})",
        "description": "A score below 90 means noticeable speed problems.",
        "recommendation": "Start with the top items in the opportunities block.",
        "consequence": (
            "The overall speed score is low — on a slow connection the site will be hard to "
            "use."
        ),
    },
    "perf.unavailable": {
        "title": "Speed data not collected",
        "description": "The provider returned no metrics — the speed module was not scored.",
        "recommendation": "Check PSI_API_KEY or the availability of the Lighthouse sidecar.",
        "consequence": (
            "Speed was not measured this time, so the score is incomplete. This is not a "
            "problem with the site."
        ),
    },
    "perf.render_blocking": {
        "title": "{count} render-blocking resources in <head>",
        "description": "Synchronous scripts and CSS delay the first render.",
        "recommendation": "Add async/defer to scripts and inline the critical CSS.",
        "consequence": (
            "Your visitor stares at a blank screen for several seconds before anything appears."
        ),
    },
    "perf.images.legacy_format": {
        "title": "{count} images could be served in a lighter format",
        "description": (
            "JPG and PNG are not outdated and work everywhere — but for the same images "
            "WebP or AVIF usually weighs noticeably less. The gain depends on the file."
        ),
        "recommendation": (
            "Serve WebP/AVIF through <picture> with a fallback to the current format."
        ),
        "consequence": (
            "The page loads more slowly than it could — most noticeably on a phone and on "
            "a slow connection."
        ),
    },
    "perf.images.no_dimensions": {
        "title": "{count} images without width/height",
        "description": (
            "Without dimensions the browser reserves no space — a direct CLS cost."
        ),
        "recommendation": "Set width and height (or aspect-ratio) on every <img>.",
        "consequence": (
            "While images load, the text jumps around and becomes awkward to read."
        ),
    },
    "perf.images.no_lazy": {
        "title": "No lazy loading despite many images",
        "description": "",
        "recommendation": "Add loading=\"lazy\" to images below the fold.",
        "consequence": (
            "The browser downloads every image at once, including ones the visitor may never "
            "scroll to."
        ),
    },
    "perf.external_fonts": {
        "title": "Fonts load from third-party hosts: {hosts}",
        "description": (
            "An external font host adds a connection to the critical rendering path."
        ),
        "recommendation": (
            "Self-host the fonts and load them via @font-face with font-display: swap."
        ),
        "consequence": (
            "The browser waits for someone else's server before showing text — the page stays "
            "blank longer."
        ),
    },
    "perf.third_party": {
        "title": "{count} third-party hosts on the homepage",
        "description": (
            "Every external host means a separate connection, a DNS lookup and someone else's "
            "code."
        ),
        "recommendation": (
            "Remove what does not serve conversion: extra widgets, trackers, chat tools."
        ),
        "consequence": (
            "The site depends on the speed and availability of other people's servers, any of "
            "which can slow it down."
        ),
    },
    "perf.third_party.weight": {
        "title": "Third-party code is {share} of the page ({kb} KB)",
        "description": (
            "We opened the page in a real browser and weighed everything it loaded. "
            "{share} of the total comes from other people's domains — widgets, chats, "
            "trackers, ads. Every one of them has to arrive before the page is fully usable."
        ),
        "recommendation": (
            "Work through the heaviest domains listed in the evidence. Load anything not "
            "needed above the fold afterwards, and drop what nobody uses."
        ),
        "consequence": (
            "Your site's speed depends on other companies' servers. If they are having a "
            "slow day, so are your visitors — and there is nothing you can do about it."
        ),
    },
    "perf.page_weight": {
        "title": "The page weighs {megabytes} MB before any images",
        "description": (
            "That is the markup alone, with no images or scripts: {words} words in a "
            "single document. An ordinary page is tens or hundreds of kilobytes. The "
            "usual causes are comment spam, a catalogue dumped into the page, or "
            "traces of a break-in."
        ),
        "recommendation": (
            "Look at what takes up the space: open the page and search for text you "
            "never added. If it is comments, turn them off or moderate them; if it is "
            "unfamiliar links and gibberish, check the site for a compromise and "
            "change the passwords."
        ),
        "consequence": (
            "A page this heavy takes a long time to load even on a good connection, and on a "
            "phone it may not open at all."
        ),
    },
    "perf.page_weight.truncated": {
        "title": "The page is too large to read in full: at least {megabytes} MB",
        "description": (
            "The markup went past the limit we read up to, so {words} words is not "
            "even the whole of it. A document this size is never accidental: usually "
            "comment spam, a dumped catalogue, or the aftermath of a break-in. "
            "Everything else we say about this page covers the part we read."
        ),
        "recommendation": (
            "Check the page by hand: open it and see where the bulk comes from. "
            "Unfamiliar links or text you did not write mean a likely compromise — "
            "change the passwords and have the site checked. Remove spam comments "
            "from the database, not just from view."
        ),
        "consequence": (
            "Someone on a phone will most likely give up before it loads. Search "
            "engines also read it only in part — and what they read may turn out to "
            "be someone else's text instead of yours."
        ),
    },
    "perf.responsive_images": {
        "title": "{count} images without responsive sizes",
        "description": "",
        "recommendation": "Add srcset and sizes so phones download a smaller version.",
        "consequence": (
            "Phones download the same size photos as desktops: the page opens slower and it eats "
            "the visitor's mobile data."
        ),
    },
    # ── Protection and analytics ────────────────────────────────────────────
    "tech.security_headers.none": {
        "title": "No browser security headers detected on the tested response",
        "description": (
            "None of the checked browser protection headers ({headers}) are present on the "
            "response. These are additional protection mechanisms; their absence by itself does "
            "not indicate a security incident, but it usually means the configuration has not "
            "been addressed yet."
        ),
        "recommendation": (
            "Discuss with the developer which of these mechanisms suit your application. "
            "X-Content-Type-Options: nosniff is the usual starting point — it is the safest for "
            "compatibility."
        ),
        "consequence": (
            "Browser-side protections for visitors are not configured at all. The site is not "
            "broken because of it — but it lacks the headroom these mechanisms provide for free."
        ),
    },
    "tech.security_headers.missing": {
        "title": "{count} optional browser protections not detected",
        "description": (
            "Not detected on the tested response: {headers}. These are additional browser-side "
            "protections for visitors. Their absence by itself does not indicate a security "
            "incident and is not a direct requirement for search or AI visibility."
        ),
        "recommendation": (
            "Review the configuration with the site's developer: which headers are appropriate "
            "depends on the application, and enabling them blindly can break working pages."
        ),
        "consequence": (
            "Some standard browser protections for visitors are not enabled. That is missing "
            "headroom, not a breach: the site is not compromised by it and loses no readers."
        ),
    },
    "tech.crawler_blocked": {
        "title": "The site answers robots with status {status} instead of a page",
        "description": (
            "Our agent received {status} and saw no page with content. Bot protection often "
            "treats GPTBot, ClaudeBot and PerplexityBot the same way: their requests also "
            "arrive from an unknown browser. Google may still be let through — it is recognised "
            "separately. We tested one agent, our own; how this site answers the others we did "
            "not check."
        ),
        "recommendation": (
            "In your protection settings (Cloudflare, WAF, fail2ban) allow search and AI "
            "crawlers by their user-agent strings and IP ranges. Verify the result with URL "
            "Inspection in Search Console."
        ),
        "consequence": (
            "The site did not let our program in: not a single page could be read. The same "
            "settings often stop the bots of AI services too, but whether this site blocks them "
            "we did not test — the rest of the report rests only on what could be seen from "
            "outside."
        ),
    },
    "tech.analytics.missing": {
        "title": "No analytics system was detected on the site",
        "description": (
            "We opened the page in a real browser and ran all of its JavaScript. No "
            "counter appeared — no Google Analytics or GTM, no Plausible, Matomo, Segment "
            "or PostHog, and no first-party measurement script either."
        ),
        "recommendation": (
            "Install Google Analytics 4 and verify the site in Search Console. Both are "
            "free and take about an hour to set up."
        ),
        "consequence": (
            "No analytics script was detected on the pages we read."
        ),
    },
    "tech.analytics.unconfirmed": {
        "title": "No analytics tag found in the page source",
        "description": (
            "The HTML carries no Google Analytics or GTM and no alternative. We looked "
            "without running JavaScript, though, and some tags are injected by it after "
            "the page loads — one of those we would not have seen."
        ),
        "recommendation": (
            "Confirm whether a tag is actually installed, for example in the analytics "
            "tool's own reports. If it is not, add Google Analytics 4."
        ),
        "consequence": (
            "If nothing is measuring visits, you do not know how many people come or what "
            "they do — there is nothing to base improvements on."
        ),
    },
    "tech.form_protection.unprotected": {
        "title": "Legacy check: no visible protection marker was found in the form",
        "description": (
            "A record from an earlier audit: no client-visible anti-abuse marker was detected "
            "inside the form. That check did not assess server-side or invisible controls, so "
            "this record by itself is not proof that the form was unprotected."
        ),
        "recommendation": (
            "No separate action is needed on the basis of this legacy record alone. Judge the "
            "state of the forms by the current findings of the report."
        ),
        "consequence": (
            "This record remains from an older audit version and does not affect new results."
        ),
    },
    "tech.form_protection.no_visible_marker": {
        "title": (
            "No visible anti-bot protection was detected in the form."
        ),
        "description": (
            "No visible protection was found in the initial HTML or the rendered form. "
            "Server-side protection may still exist and cannot be confirmed by this passive "
            "check."
        ),
        "recommendation": (
            "If unwanted automated submissions are an actual problem or a material risk, ask "
            "the site developer or provider which server-side anti-abuse controls are enforced. "
            "Choose controls proportionate to the form and user risk, and consider friction and "
            "accessibility; CAPTCHA is not mandatory, and any client-side widget must be backed "
            "by server-side validation."
        ),
        "consequence": (
            "The form itself shows no visible sign of checking that a human is submitting it. "
            "This is an observation about the page's code, not a proven defect: the check may "
            "run on the server, where we cannot see it."
        ),
    },
    "tech.form_protection.get_method": {
        "title": (
            "{count} forms submit data via GET"
        ),
        "title.one": "{count} form submits data via GET",
        "description": (
            "A GET form places the submitted field values in the request URL. Such URLs may be "
            "retained in browser history and may appear in server or proxy logs and in copied "
            "links. Use POST for forms collecting personal or non-public information; POST by "
            "itself is not encryption or a complete security control — HTTPS is required "
            "separately."
        ),
        "recommendation": (
            "Change the method to post — form data should not end up in the address bar."
        ),
        "consequence": (
            "What a person types into the form ends up in the page address and may be kept in "
            "browser history and logs."
        ),
    },
    "tech.email_exposed": {
        "title": "{count} email addresses exposed in the page source",
        "description": (
            "mailto: links with a plain address are harvested by automated scrapers."
        ),
        "recommendation": "Replace them with a contact form or assemble the address in script.",
        "consequence": (
            "Spam bots will gradually harvest the address and junk will start arriving. "
            "That is a nuisance rather than a threat: the mailbox itself is not at risk."
        ),
    },
    "tech.caching": {
        "title": "Pages are served without caching rules",
        "description": "No Cache-Control, ETag or Last-Modified on {count} checked pages.",
        "recommendation": "Configure Cache-Control and ETag at the server or CDN level.",
        "consequence": (
            "The browser re-downloads the page every time, even when nothing on it has changed."
        ),
    },
    "tech.soft_404": {
        "title": "A non-existent page returns status {status}",
        "description": (
            "The server answers with success for an address that does not exist. 404 is "
            "expected."
        ),
        "recommendation": "Configure the server to return 404 for non-existent addresses.",
        "consequence": (
            "The page answers “everything is fine” while showing an error. Anything that goes "
            "by the answer code — a browser, a search engine, our own program — takes it for a "
            "real page."
        ),
    },
    "tech.host_canonical": {
        "title": "The site also opens at {host}",
        "description": (
            "Both host versions serve content and do not redirect to a single one."
        ),
        "recommendation": (
            "Set up a permanent 301 redirect from the secondary host to the main one."
        ),
        "consequence": (
            "The same site exists at two addresses, and search splits its authority between "
            "them instead of counting it in full."
        ),
    },
    "tech.nap.phone_mismatch": {
        "title": "The site shows {count} different phone numbers",
        "description": "Different pages display different contact numbers.",
        "recommendation": "Keep one number, or state explicitly which number is for what.",
        "consequence": (
            "Several phone numbers were found, but no primary contact number was "
            "identified."
        ),
    },
    "tech.nap.phone_not_e164": {
        "title": "{count} numbers are not in international format",
        "description": (
            "A tel: link should carry a plus, the country code and the number — no spaces, "
            "brackets or dashes. Right now, for example: {example}."
        ),
        "recommendation": (
            "Normalise every tel: to international form: a plus, the country code, then the "
            "digits with no separators. The visible text can stay readable."
        ),
        "consequence": (
            "On a phone, such a number cannot always be dialled with a single tap."
        ),
    },
    "tech.nap.schema_mismatch": {
        "title": "The phone in markup does not match the phone on the pages",
        "description": (
            "JSON-LD hands machines one number while the site shows people another."
        ),
        "recommendation": "Sync telephone in structured data with the number in your contacts.",
        "consequence": (
            "Your business card in search may show the wrong number — calls will go to the "
            "wrong place."
        ),
    },
    "seo.meta_description.too_long": {
        "title": "Only the first {visible} characters of {length} are shown",
        "description": (
            "Search truncates the rest. A longer description is not an error — AI crawlers read "
            "all of it — but in the results people see only the opening."
        ),
        "recommendation": (
            "Make sure the point and the call to action fit within the first {visible} "
            "characters."
        ),
        "consequence": (
            "If the main message sits at the end of the description, nobody reads it in search."
        ),
    },
    "seo.meta_description.too_short": {
        "title": "Description is too thin ({length} chars)",
        "description": "Shorter than {min} characters, it can neither explain nor persuade.",
        "recommendation": "Say what the service is, who it is for, and what to do next.",
        "consequence": (
            "There is almost nothing under your search result — people pick the competitor who "
            "wrote something."
        ),
    },
    "llm.unstated_facts.offering": {
        "title": (
            "The pages we read never say what the company sells"
        ),
        "description": (
            "After reading the whole site, no concrete product or service can be named. "
            "Phrases like “solutions for your business” do not answer the question a "
            "buyer arrives with."
        ),
        "recommendation": (
            "State on the home page, in one sentence, what you sell — not "
            "“end-to-end solutions” but “we install CCTV systems”."
        ),
        "consequence": (
            "The pages we read never say what you sell. Neither a person nor a search or AI "
            "service has anywhere to take that from."
        ),
    },
    "llm.unstated_facts.location": {
        "title": "The site never says where you operate",
        "description": (
            "No city, no region, no country anywhere on the site. For a business that "
            "serves a specific area this is the first filter a buyer applies: they are "
            "looking for someone near them."
        ),
        "recommendation": (
            "Put the city and street address in the footer of every page and on the "
            "contact page. If you cover a wider area, list the towns you serve."
        ),
        "consequence": (
            "Asked “who does this in my city”, the site has nothing to answer with: it "
            "never says where you are. That makes you less likely to be suggested to "
            "exactly the buyers who would find it convenient to come to you."
        ),
    },
    "llm.unstated_facts.pricing": {
        "title": "The site never says what it costs",
        "description": (
            "No prices, no price list, and no clear offer to prepare a quote. Price is "
            "the first thing a buyer asks about, and the site does not answer."
        ),
        "recommendation": (
            "Publish prices, or at least a “from–to” range. If every job is priced "
            "individually, say so plainly and give a form to request a quote."
        ),
        "consequence": (
            "The buyer compares you against competitors and drops you first: their "
            "price is visible, yours is not. Saying nothing about price reads as "
            "“expensive”."
        ),
    },
    "ai.jsonld.partial": {
        "title": "Legacy observation: markup was not on every page",
        "description": (
            "An earlier Crawldy version flagged partial markup coverage as a defect. That "
            "observation has since been retired: markup does not have to be on every page, and "
            "newer audits do not treat partial coverage as a problem."
        ),
        "recommendation": (
            "No action is required based on this legacy entry alone."
        ),
        "consequence": (
            "This entry remains from an earlier audit version and does not affect new results."
        ),
    },
    "tech.demo_content": {
        "title": "Template demo content is still on the site",
        "description": (
            "Found {count} signs that part of the site is demo data from a theme "
            "that was never replaced: invented people in the team section, a "
            "placeholder phone number, an email on the theme vendor’s domain, "
            "or page-builder template parts left publicly reachable."
        ),
        "recommendation": (
            "Remove or replace the demo pages and contacts. Keep page-builder "
            "template parts out of the index."
        ),
        "consequence": (
            "Visitors see people who do not work for you and contacts you do not have. "
            "That damages trust harder than technical faults do — and search engines "
            "and assistants read these pages as the truth about your company."
        ),
    },
    "a11y.blocking": {
        "title": "{count} barriers that stop people using the site",
        "description": (
            "This is not about styling. Blocked zoom, a button or link with no "
            "name, a field with no label — a person simply cannot do what they "
            "came for: read it on a phone, tap it, fill the form in."
        ),
        "recommendation": (
            "Remove user-scalable=no from the viewport, give buttons and links "
            "text or an aria-label, label form fields."
        ),
        "consequence": (
            "Some visitors may be unable to use parts of the page. Accessibility problems "
            "affect buttons, links or form fields."
        ),
    },
    "a11y.failures": {
        "title": "{count} accessibility remarks",
        "description": (
            "An automated Lighthouse pass found places where content is harder to "
            "read or to reach with a keyboard. Nobody verifies full standard "
            "compliance automatically — that needs manual testing."
        ),
        "recommendation": (
            "Work through the list in the evidence. Most of these are fixed with "
            "markup attributes, without redesigning anything."
        ),
        "consequence": (
            "People with poor eyesight, on older phones, or using a keyboard "
            "instead of a mouse find the site harder to use than it needs to be."
        ),
    },
    # ── Мовні версії ───────────────────────────────────────────────────────
    "seo.hreflang_invalid": {
        "title": "{count} declared versions use a value Google will not accept: {values}",
        "description": (
            "Google accepts a narrow grammar here: a language from ISO 639-1, an optional "
            "script from ISO 15924, an optional country from ISO 3166-1 Alpha 2 — in that order "
            "— plus the reserved x-default. So zh-Hant and zh-Hans-US are fine, while en_US, "
            "en-UK and en-US-Latn are not. The evidence names what is wrong with each value; "
            "the most common mistake is a country code where a language belongs."
        ),
        "recommendation": (
            "Correct each value listed in the evidence: a hyphen rather than an underscore, "
            "en-GB rather than uk or en-UK, and the language first when a country follows. The "
            "evidence also records where each value was found, so you know which file to open."
            "One case has no valid form: a language with no ISO 639-1 code at all "
            "(Asturian, Kashubian and others; marked not_a_language in the evidence). It "
            "cannot be represented by any valid hreflang language code, because Google's "
            "grammar has none for it. Do not substitute another language's code — an "
            "Asturian page declared as Spanish misleads both search engines and readers. "
            "Remove the value and leave that version without hreflang."
            "If the same value also appears in the reciprocal sets on other language versions, "
            "remove it there as well — otherwise half the site keeps pointing at an invalid code."
        ),
        "consequence": (
            "The language-version markers are written in a form search engines do not accept, "
            "so they have no effect. Pages meant for other countries stay undeclared."
        ),
    },
    "seo.hreflang_reciprocity.self": {
        "title": "The page declares {count} versions but never names itself",
        "description": (
            "A set of declared versions has to include the page it sits on, pointing at its own "
            "address. Google treats a set without that self-reference as incomplete and may "
            "disregard it. An x-default entry pointing here does not count: it means \"come here "
            "when nothing matched\", not \"this page is that version\"."
        ),
        "recommendation": (
            "Add an entry for this page's own language pointing at this exact address, next to "
            "the others. Whichever of the three places you already use is fine — the page "
            "itself, the HTTP header, or the site map."
        ),
        "consequence": (
            "The page says which other versions exist but never says which one it is, so the "
            "whole group can be discarded and people may be sent to the wrong page."
        ),
    },
    "seo.hreflang_reciprocity.return": {
        "title": "{count} of the {checked} versions we opened do not point back",
        "description": (
            "The declaration only works when both sides make it: if this page names another as "
            "its version, that page has to name this one in return. We opened {checked} of the "
            "{declared} addresses declared here and found no return entry on the ones listed in "
            "the evidence. About the addresses we did not open we make no claim."
        ),
        "recommendation": (
            "On each page named in the evidence, add the entry that points back to this "
            "address. If those pages are generated from the same template, the fix is usually "
            "one change rather than several."
        ),
        "consequence": (
            "The link between the two pages is claimed on one side only, so search engines may "
            "treat them as unrelated pages competing with each other rather than as the same "
            "page for two audiences."
        ),
    },
    "seo.hreflang_conflict.duplicate": {
        "title": "{value} is declared for {count} different addresses",
        "description": (
            "One value may name exactly one address. When it names several, Google cannot tell "
            "which was meant and may drop every declaration on the page, not only the "
            "contradictory one. The evidence lists the competing addresses and where each was "
            "declared — often one comes from the page and another from the site map."
        ),
        "recommendation": (
            "Keep a single address per value. Compare the sources in the evidence first: if two "
            "of the three places disagree, the older one is usually left over from a previous "
            "setup and can be removed."
        ),
        "consequence": (
            "The page gives two different answers to the same question, and search engines may "
            "throw out the whole setting rather than guess which one you meant."
        ),
    },
    "seo.hreflang_conflict.x_default": {
        "title": "{value} names {count} different addresses",
        "description": (
            "x-default marks the page to show when none of the declared versions matches the "
            "visitor. Declaring more than one leaves that undefined, and the fallback is the "
            "one case where the choice is made for everyone you did not plan for."
        ),
        "recommendation": (
            "Pick one address as the fallback and remove the others. A page that chooses by "
            "itself — a language picker or a country selector — is the usual choice."
        ),
        "consequence": (
            "People whose country you did not plan for can be sent to either of two pages, and "
            "which one they get is not decided by you."
        ),
    },
    "seo.hreflang_conflict.canonical": {
        "title": "The page declares its versions while pointing search at {canonical}",
        "description": (
            "A page taking part in a set of declared versions has to be its own canonical. Here "
            "the canonical names a different address, so the declarations describe a page that "
            "the site itself asks search engines not to show. The two instructions contradict "
            "each other, and Google resolves the contradiction on its own terms."
        ),
        "recommendation": (
            "Decide which page is the real one. Either make the canonical point at this "
            "address, or move the version declarations to the page the canonical names."
        ),
        "consequence": (
            "The page says two opposite things at once: that it has versions for other "
            "countries, and that it is not the page worth showing. Search engines settle that "
            "themselves, and usually not the way you would."
        ),
    },
    "seo.hreflang_broken.unreachable": {
        "title": "{count} declared versions did not return a working page",
        "description": (
            "We opened these addresses ourselves and the server did not answer with a "
            "successful response. The evidence carries each address and the status code it "
            "returned, so this is measured rather than assumed. Addresses we did not open are "
            "not counted here."
        ),
        "recommendation": (
            "For each address in the evidence, either correct it to the page that exists now or "
            "remove it from the set. An address left over from a rebuilt site is the common "
            "cause."
        ),
        "consequence": (
            "Some of the addresses offered to people in other countries lead nowhere. Anyone "
            "sent there sees an error page instead of yours."
        ),
    },
    "seo.hreflang_broken.noindex": {
        "title": "{count} declared versions are closed to search",
        "description": (
            "The address is declared as a version worth showing and at the same time carries a "
            "noindex instruction telling search engines not to show it. The two cancel out. We "
            "read the instruction on the page itself — the evidence quotes it."
        ),
        "recommendation": (
            "Decide which was intended: remove the noindex from those pages, or drop them from "
            "the set of declared versions."
        ),
        "consequence": (
            "A page is offered as the one for another country while also being marked as one "
            "that should not appear in search. People from that country will not be sent there."
        ),
    },
    "seo.hreflang_missing": {
        "title": "Pages are served in {count} languages ({languages}) with no versions declared",
        "description": (
            "The pages we read declare different languages of their own, and nothing states "
            "that they are versions of one another — not in the pages, not in an HTTP header, "
            "not in the site map. Whether they are translations of the same content or separate "
            "sections we cannot tell from outside, which is why this is worth checking rather "
            "than certain. The evidence lists the addresses by language."
        ),
        "recommendation": (
            "If these pages are versions of the same content, declare them so. Any one of the "
            "three places is enough — Google treats them as equivalent — and the site map is "
            "usually the cheapest when the pages are generated."
        ),
        "consequence": (
            "Someone searching in one of your languages may be shown the page written in "
            "another one, because nothing tells search engines that these pages belong "
            "together."
        ),
    },
    # ── Перенаправлення ────────────────────────────────────────────────────
    "seo.redirect_chain": {
        "title": "The address goes through {count} redirects before the page opens",
        "description": (
            "The browser asked for one address and was sent onward more than once before "
            "anything was served. The evidence carries every hop with its status code and the "
            "address it pointed to. One redirect is ordinary — http to https, or an old address "
            "to its replacement; a chain usually means two rules stacked up over time, each "
            "written without knowing about the other."
        ),
        "recommendation": (
            "Point the first rule straight at the final address so the chain collapses to a "
            "single step. Where the evidence lists pages that link to the starting address, "
            "change those links to the final address as well — that removes the redirect from "
            "the path entirely rather than shortening it."
        ),
        "consequence": (
            "Every extra hop is another round trip to the server before anything appears, so "
            "the page starts loading later than it needs to — most noticeably on a phone."
        ),
    },
    "seo.redirect_loop.repeated": {
        "title": "The redirect path returns to an address it already visited",
        "description": (
            "One address appears more than once on the way to the page: the path doubled back "
            "on itself before finishing. The evidence lists the full sequence and the repeated "
            "addresses. This one completed, so the page was reachable — but the rules describe "
            "a circle, and a small change to either of them can close it."
        ),
        "recommendation": (
            "Compare the rules that produced the repeated address in the evidence. Usually two "
            "of them send traffic to each other, and only the order in which the server "
            "evaluates them keeps the circle open."
        ),
        "consequence": (
            "The address sends visitors back to a point they had already passed. It works "
            "today, but a small change to either rule is enough to make the page stop opening "
            "at all."
        ),
    },
    "seo.redirect_loop.limit": {
        "title": "{url} kept redirecting and never delivered a page",
        "description": (
            "We followed {followed} redirects from this address and stopped, having received no "
            "page. What we can state is only that: the sequence did not end within that many "
            "steps. We cannot say where it was circling, or whether it was circling at all, "
            "because no page was ever returned to inspect."
        ),
        "recommendation": (
            "Open this address in a browser and watch the address bar. If it settles, the chain "
            "is merely long and the first rule should point at the final address; if it keeps "
            "changing, two rules are sending traffic to each other."
        ),
        "consequence": (
            "This address never opens. Anyone who follows a link to it — a visitor, or a search "
            "engine trying to read the page — gets nothing back."
        ),
    },
    "seo.redirect_target": {
        "title": "The redirect ends on an address that answered {status}",
        "description": (
            "The rule works and sends the browser onward, but the destination does not return a "
            "page. We read the status code ourselves; the evidence carries the full path. The "
            "usual cause is not the redirect but the destination: the page was removed later "
            "than the rule that points at it."
        ),
        "recommendation": (
            "Point the rule at an address that exists now, or remove it. If the evidence lists "
            "pages linking to the starting address, update those links too."
        ),
        "consequence": (
            "The address leads visitors to an error page. Because the redirect itself works, "
            "the site looks like it is handling the address correctly right up to the moment "
            "someone sees the failure."
        ),
    },
    # ── Узгодженість карти сайту ───────────────────────────────────────────
    "seo.sitemap_consistency.error": {
        "title": "{count} addresses in the sitemap returned an error when we opened them",
        "description": (
            "The sitemap asks search engines to find these addresses, and the server did not "
            "return a page at them. We opened each one ourselves; the evidence carries the "
            "address and the status code it answered with. Of the {declared} addresses "
            "declared, we checked {checked}; the rest we did not open, and they are not "
            "counted here either way."
        ),
        "recommendation": (
            "Remove these addresses from the sitemap, or restore the pages behind them. A "
            "sitemap generated from the database usually keeps listing pages that were deleted "
            "through the interface."
        ),
        "consequence": (
            "You are pointing search engines at pages that do not open. The effort spent "
            "fetching them is wasted, and anyone who finds one of these addresses another way "
            "sees an error."
        ),
    },
    "seo.sitemap_consistency.redirects": {
        "title": "{count} addresses in the sitemap redirect somewhere else",
        "description": (
            "A sitemap should normally list the address a page finally lives at, not one that "
            "forwards to it. Each of these hands the browser onward; the evidence carries the "
            "destination and the number of hops. Of {declared} declared addresses we checked "
            "{checked}."
        ),
        "recommendation": (
            "Replace each sitemap entry with the address it ends at — the evidence lists both. "
            "If the sitemap is generated, the generator is probably reading a stored address "
            "from before the last move."
        ),
        "consequence": (
            "The list of addresses you publish is not the list people actually land on. Every "
            "one of them costs an extra step before the page appears."
        ),
    },
    "seo.sitemap_consistency.noindex": {
        "title": "{count} addresses in the sitemap are closed to search",
        "description": (
            "These pages carry a noindex instruction and are also listed in the sitemap. The "
            "two say opposite things: one asks search engines to find the page, the other asks "
            "them not to show it. We read the instruction on the page itself; the evidence "
            "records whether it was in the server's response or appeared after scripts ran. "
            "Checked {checked} of {declared} declared addresses."
        ),
        "recommendation": (
            "Decide which was intended. If the page should not appear in search, drop it from "
            "the sitemap; if it should, remove the noindex."
        ),
        "consequence": (
            "Your site asks for these pages to be found and, on the same pages, asks for them "
            "not to be shown. Whichever wins, one of the two settings is not doing what you "
            "meant."
        ),
    },
    "seo.sitemap_consistency.canonical": {
        "title": "{count} addresses in the sitemap name a different address as the main one",
        "description": (
            "Each of these pages declares a canonical address other than the one listed in the "
            "sitemap. The sitemap should normally carry the address the page itself considers "
            "primary. The evidence shows both, and whether the canonical address was also found "
            "in the sitemap. We do not claim to know which address a search engine will "
            "ultimately choose. Checked {checked} of {declared}."
        ),
        "recommendation": (
            "List the canonical address in the sitemap instead. Where the evidence shows the "
            "canonical is missing from the sitemap entirely, adding it is usually the fix."
        ),
        "consequence": (
            "The sitemap and the pages disagree about which address is the real one. You are "
            "asking for one version to be found while the page itself points at another."
        ),
    },
    "seo.sitemap_consistency.not_for_search": {
        "title": "{count} service pages are listed in the sitemap",
        "description": (
            "Sign-in pages, baskets and archives are not what a sitemap is for: it lists the "
            "pages worth finding. The evidence names each address and how it was classified. "
            "Checked {checked} of {declared} declared addresses."
        ),
        "recommendation": (
            "Exclude these sections from the sitemap. Most generators have a setting for "
            "exactly this, and it is usually off by default."
        ),
        "consequence": (
            "The list of pages you present as worth finding includes pages nobody searches for, "
            "which makes the list less useful without helping the pages that matter."
        ),
    },
    # ── Текст посилань ─────────────────────────────────────────────────────
    "seo.anchor_text": {
        "title": "{count} link texts point to several different pages each ({links} links)",
        "description": (
            "The same wording is used for links that lead to different places. The evidence "
            "lists each phrase, how many links carry it and how many distinct destinations they "
            "reach. Navigation and footer links are excluded — a repeated \"Pricing\" in the "
            "header is a landmark, not a defect — and so are pages whose language we could not "
            "establish. Google's own guidance gives \"click here\", \"read more\", \"website\" and "
            "\"article\" as examples of text that tells the reader little."
        ),
        "recommendation": (
            "Give each link text that names its destination: \"See the 2026 price list\" rather "
            "than \"Learn more\". Where the phrase appears in a template — article cards are the "
            "usual case — the fix is one change to the template that pulls the destination "
            "title into the link. Do not stuff terms in; write what a person would say."
        ),
        "consequence": (
            "Readers cannot tell where a link goes before clicking it, so they either guess or "
            "skip it. On a page of identical labels, the labels stop being a way to choose."
        ),
    },
    # ── Змішаний вміст ─────────────────────────────────────────────────────
    "tech.mixed_content.blockable": {
        "title": "{count} insecure resources on {pages} secure pages may not load at all",
        "description": (
            "These pages are served over a secure connection but ask for scripts, "
            "stylesheets or embedded frames over an insecure one. Browsers do not quietly "
            "fix this class: they refuse the request rather than fetch it, so whatever the "
            "resource does may simply not happen. The evidence lists each resource, its "
            "type, whether we saw the browser actually request it, and whether it belongs "
            "to you or to a third party."
        ),
        "recommendation": (
            "Point each of these at its secure address — most providers have served one for "
            "years, and the change is usually one character. Where a third-party resource "
            "has no secure address at all, replace or remove the dependency: that provider "
            "cannot be used on a secure page."
        ),
        "consequence": (
            "Part of the page asks for something the browser will not fetch over an "
            "unprotected connection. Whatever depended on it — a form, a widget, a tracker "
            "— may quietly stop working for every visitor."
        ),
    },
    "tech.mixed_content.upgradeable": {
        "title": "{count} images or media on {pages} secure pages are requested insecurely",
        "description": (
            "Modern browsers rewrite these requests to the secure address by themselves, so "
            "visitors usually see nothing wrong. That is not the same as the setup being "
            "correct: the rewrite works only while the secure version of the file exists, "
            "and the address written in the page still points at the unprotected one. The "
            "evidence records what we saw the browser do, and says plainly where we did not "
            "look."
        ),
        "recommendation": (
            "Write the secure address in the page instead of relying on the browser to "
            "correct it. If the resources come from a template or a media library, the fix "
            "is usually one search and replace across stored content."
        ),
        "consequence": (
            "The page currently works because browsers quietly correct these addresses. The "
            "day one of those files is not available at its corrected address, the image or "
            "video disappears with no warning."
        ),
    },
    "tech.mixed_content.download": {
        "title": "{count} downloads on {pages} secure pages are offered over an insecure link",
        "description": (
            "A file offered for download from a secure page is fetched over an unprotected "
            "connection. Browsers treat this separately from other resources and may block "
            "the download or warn the person before it starts. The evidence lists each "
            "file."
        ),
        "recommendation": (
            "Serve these files over the secure address of the same site. If they sit on "
            "another host that has no secure address, move them or host them yourself."
        ),
        "consequence": (
            "People who click these files may get a warning or nothing at all, on a page "
            "that otherwise looks entirely trustworthy."
        ),
    },
    "tech.mixed_content.runtime": {
        "title": "{count} insecure requests on {pages} pages come from scripts, not the markup",
        "description": (
            "We opened these pages in a browser and watched it make requests to unprotected "
            "addresses that appear nowhere in the page source. Something running on the "
            "page builds these addresses as it goes — usually an analytics or widget "
            "script. The evidence carries the addresses we recorded."
        ),
        "recommendation": (
            "Find the script that builds each address — the host in the evidence usually "
            "names the provider — and update its configuration, or replace it. Searching "
            "the page source for these addresses will not find them; they are assembled at "
            "run time."
        ),
        "consequence": (
            "The page reaches out over an unprotected connection while presenting itself as "
            "secure. Nothing in the page source shows it, so it survives every review that "
            "only reads the code."
        ),
    },
    # ── Однаковий вміст під різними адресами ───────────────────────────────
    "seo.duplicate_content.unconsolidated": {
        "title": "{count} groups of addresses return the same content ({pages} pages)",
        "description": (
            "Each group below holds addresses whose page content is identical after "
            "navigation and footer text is set aside. Nothing on the site says which of "
            "them is the main one — no redirect between them, and no canonical pointing at "
            "a single member. Duplicate content is ordinary and is not a rule violation; "
            "search engines group such pages and pick one themselves, and which one they "
            "pick we cannot tell you. The evidence lists each group with its members and "
            "what each declares."
        ),
        "recommendation": (
            "Decide what these addresses are meant to be. If they are one page, keep a "
            "single address and send the others to it, or have every member name the same "
            "canonical. If they are meant to be different pages, give them genuinely "
            "different content. Then make internal links and the sitemap point at whichever "
            "version you chose."
        ),
        "consequence": (
            "The same page exists at several addresses and nothing says which one counts. "
            "Visits, links and any measurement you do get split between them, and you "
            "cannot tell which address people actually arrived at."
        ),
    },
    "seo.duplicate_content.conflicting": {
        "title": "{count} groups of identical pages disagree about which address is primary",
        "description": (
            "These addresses return the same content, and the pages themselves name "
            "different main addresses — or name one that is not in the group at all. That "
            "is a contradiction inside the site rather than a rule violation: search "
            "engines will resolve it on their own terms, and their choice may differ from "
            "yours. The evidence shows what each member declares."
        ),
        "recommendation": (
            "Pick one address for the group and have every member name it. Where a member "
            "points outside the group, check whether that address is really the intended "
            "one — usually it is left over from an earlier structure."
        ),
        "consequence": (
            "Your pages give conflicting answers about which version is the real one, so "
            "the decision is made for you rather than by you."
        ),
    },
    # ── Транспорт: стиснення й протокол ────────────────────────────────────
    "tech.transport.uncompressed": {
        "title": "{count} text responses arrived without compression (largest {size} KB)",
        "description": (
            "We asked for compressed content and these responses came back uncoded. The "
            "evidence lists each one with its type, what we requested and both sizes we "
            "could establish. Note what this does and does not say: it describes the "
            "responses we received, not the server's capabilities. We advertise gzip and "
            "deflate only, so a server offering Brotli alone would answer us exactly this "
            "way. How many bytes compression would save we do not state — that would "
            "require compressing them ourselves, which we did not do."
        ),
        "recommendation": (
            "Check whether compression is enabled for these content types on the server or "
            "CDN. gzip is entirely adequate; there is no need to move to Brotli or "
            "Zstandard to fix this, and doing so is a separate decision with its own "
            "trade-offs."
        ),
        "consequence": (
            "Text that could travel compressed is travelling whole, so every visitor waits "
            "for more bytes than the page needs to send — most noticeably on a slow mobile "
            "connection."
        ),
    },
    "tech.transport.http1": {
        "title": "{count} responses were served over HTTP/1.1",
        "description": (
            "Our client offers HTTP/2 and negotiates it successfully with most sites, so "
            "for these responses the older protocol was what the connection settled on. "
            "That is an observation about these exchanges, not a statement that your server "
            "lacks HTTP/2: the negotiated version depends on the server, on any CDN in the "
            "path and on the client. HTTP/2 can use one connection more efficiently, "
            "handling several exchanges at once and compressing headers, though whether a "
            "given page loads faster depends on the page. We do not test HTTP/3 at all, so "
            "nothing here says anything about it."
        ),
        "recommendation": (
            "Check the HTTP/2 setting on the server or CDN in front of it. Most hosting "
            "panels and CDNs expose it as a single switch, and it is often off on older "
            "configurations."
        ),
        "consequence": (
            "Requests to your site use an older, less efficient way of sharing one "
            "connection. On pages that load many files at once, that shows up as extra "
            "waiting."
        ),
    },
}


# Single-line domain notices: why part of the audit did not run, and why a
# run was or was not retried. Separate from MESSAGES on purpose — see the
# Ukrainian catalogue for the reasoning.
NOTICES: dict[str, str] = {
    "notice.breadcrumb.hierarchy_unknown": (
        "too little of the site was read to tell whether its pages sit under one another, so "
        "whether breadcrumbs belong here stays undecided"
    ),
    "notice.about_page.candidate_unread": (
        "the About page the site points to ({anchor}: {url}) was not read, so whether "
        "the site says who is behind it stays undecided"
    ),
    "notice.about_page.candidate_unreadable": (
        "the About page at {url} could not be judged: {reasons} (response {status})"
    ),
    "coverage.reason.about_page_failed_read": "the page did not answer with a readable document",
    "coverage.reason.about_page_content_shell": (
        "the answer was an empty application shell: markup, no main text"
    ),
    "coverage.reason.about_page_login_wall": (
        "the main content was a sign-in form and the page carried no About-page heading"
    ),
    "coverage.reason.about_page_redirect_placeholder": (
        "the document only forwarded the reader somewhere else"
    ),
    # degradations
    "notice.accessibility.no_category": (
        "no accessibility checks ran: the provider did not return that category"
    ),
    "notice.accessibility.not_measured": (
        "accessibility was not measured: speed measurement was excluded from this audit"
    ),
    "notice.crawl.blind": (
        "the site returned no page with content (response statuses: {statuses})"
    ),
    "notice.coverage.withheld": (
        "Pages analysed: {pages}. The site-level score is withheld: visible live content was "
        "not inspected ({reasons}). A score for what was read cannot stand in for a score of "
        "the site."
    ),
    "notice.coverage.limited": "Pages analysed: {pages}. Coverage limitation: {reasons}.",
    "coverage.reason.robots_restricted": (
        "crawling is restricted by the site's robots.txt rules"
    ),
    "coverage.reason.access_failures": (
        "some reachable URLs did not respond — {access} of {attempted}"
    ),
    "coverage.reason.untried_live_candidates": (
        "discovered pages of the site were not opened — {untried}"
    ),
    "coverage.reason.no_evidence_of_additional_live_content": (
        "no evidence of additional live content was found"
    ),
    "notice.crawl.failures": (
        "{failed} of {attempted} addresses did not answer: what we read does not "
        "represent the site"
    ),
    "notice.crawl.empty": (
        "{words} words across the whole site even after scripts run; pages read: {pages}. "
        "There is nothing to assess"
    ),
    "notice.crawl.empty_static": (
        "the server response carries {words} words: the text appears only after scripts run "
        "({rendered} words across {pages} pages). Search engines see such a page, most "
        "assistants do not"
    ),
    "notice.crawl.entry_error": (
        "the entry address returned HTTP {status}: speed was measured on an error "
        "page, not on the site"
    ),
    "notice.crawl.entry_error_stand_in": (
        "the entry address returned HTTP {status}: speed was measured on an error "
        "page, not on the site; {stand_in} was used as the home page instead"
    ),
    "notice.crawl.shallow": (
        "only the home page was crawled, although it links to internal pages: the "
        "rest did not answer or did not return HTML"
    ),
    "notice.module.excluded": "the module was switched off in the audit options",
    "notice.performance.no_vitals": (
        "Core Web Vitals were not measured ({detail}). The score is based only on "
        "server response time and static HTML signals"
    ),
    "notice.performance.no_metrics": "the provider returned no metrics: {detail}",
    "notice.performance.partial": "speed data is incomplete: {detail}",
    "notice.llm.unavailable": "no semantic analysis ran: {detail}",
    "notice.llm.disabled": "semantic analysis was switched off in the audit options",
    "notice.llm.facts_unavailable": (
        "semantic analysis returned no business facts: the check that depends on them "
        "did not run"
    ),
    "notice.analytics.unidentified": (
        "measurement traffic is visible but no vendor could be identified ({detail}): the "
        "analytics conclusion stays open"
    ),
    "notice.analytics.render_incomplete": (
        "no analytics tag is present in the markup, and the pages that could still reveal one "
        "after scripts run were not rendered ({detail})"
    ),
    "notice.render.failed": "pages were not rendered: {detail}",
    "notice.render.disabled": "rendering was switched off in the audit options",
    "notice.check.failed": "the check did not run because of an error",
    "notice.layer.failed": "part of the audit did not run because of an error",
    # retries
    "notice.retry.not_attempted": "no retry was planned",
    "notice.retry.scheduled": "attempt {next_attempt} of {allowed}",
    "notice.retry.exhausted": "attempts exhausted ({attempts}/{allowed})",
    "notice.retry.not_retryable": "we do not retry failures of type \u00ab{failure}\u00bb",
}


# Plan catalogue: what the customer buys, in human words. Separate from
# MESSAGES and NOTICES on purpose — see the Ukrainian catalogue.
CATALOG: dict[str, str] = {
    "plan.limit.audits": "{count} audits per month",
    "plan.limit.audits_unlimited": "Unlimited audits",
    "plan.limit.pages": "Up to {count} pages per audit",
    "plan.limit.sites": "{count} sites",
    "plan.limit.sites_unlimited": "Unlimited sites",
    "plan.limit.schedules": "{count} schedules",
    "plan.limit.team": "{count} team members",
    "plan.limit.history": "{count} days of history",
    "plan.limit.history_unlimited": "Full history",
    "plan.feature.semantic": "Semantic analysis",
    "plan.feature.reports": "Word reports",
    "plan.feature.public_reports": "Public report links",
    "plan.feature.api": "API access",
    "plan.feature.white_label": "Your brand on reports",
    "plan.cta.start_free": "Start free",
    "plan.cta.subscribe": "Subscribe",
    "plan.cta.contact": "Talk to us",
}
