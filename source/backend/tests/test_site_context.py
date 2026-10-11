from app.audit.site_context import _parse_robots, _parse_sitemap
from app.audit.types import RobotsInfo

ROBOTS = """
# comment
User-agent: *
Disallow: /admin
Crawl-delay: 2

User-agent: GPTBot
User-agent: ClaudeBot
Disallow: /

Sitemap: https://example.com/sitemap.xml
"""


def test_parse_robots_extracts_sitemaps_and_ai_blocks():
    info = RobotsInfo(content=ROBOTS)
    _parse_robots(info)
    assert info.sitemaps == ["https://example.com/sitemap.xml"]
    assert set(info.blocked_ai_agents) == {"gptbot", "claudebot"}
    assert info.disallows_all is False
    assert info.crawl_delay == 2.0


def test_parse_robots_detects_full_block():
    info = RobotsInfo(content="User-agent: *\nDisallow: /\n")
    _parse_robots(info)
    assert info.disallows_all is True


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
</urlset>"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
</sitemapindex>"""


def test_parse_sitemap_urlset():
    parsed = _parse_sitemap(SITEMAP)
    assert parsed.pages == ["https://example.com/", "https://example.com/about"]
    assert parsed.is_index is False
    assert parsed.children == []


def test_parse_sitemap_index():
    parsed = _parse_sitemap(INDEX)
    assert parsed.is_index is True
    assert parsed.children == ["https://example.com/sitemap-1.xml"]
    # Індекс не містить сторінок сам по собі — вони в дітях.
    assert parsed.pages == []
