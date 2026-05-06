"""Scraper Codeur.com.

Scrape la page publique /projects qui liste les missions ouvertes.
On respecte un User-Agent honnête et on ne fait qu'une requête par run.
"""

import re

import httpx
from selectolax.parser import HTMLParser

from src.models import Mission
from src.sources.base import Source

BASE_URL = "https://www.codeur.com"
LIST_URL = f"{BASE_URL}/projects"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class CodeurSource(Source):
    name = "codeur"

    async def fetch(self, client: httpx.AsyncClient) -> list[Mission]:
        try:
            resp = await client.get(LIST_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"❌ Codeur: erreur HTTP {e}")
            return []

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[Mission]:
        tree = HTMLParser(html)
        container = tree.css_first("#projects-list")
        if container is None:
            return []

        missions: list[Mission] = []
        for card in container.css('a[href*="/projects/"]'):
            href = card.attributes.get("href", "").strip()
            if not href:
                continue

            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            # Titre dans <h3>
            title_node = card.css_first("h3")
            title = title_node.text(strip=True) if title_node else "(sans titre)"

            # Description dans le div line-clamp-3
            desc_node = card.css_first("div.line-clamp-3")
            description = desc_node.text(strip=True) if desc_node else ""

            # Status (Ouvert / Ferme / etc.)
            status = ""
            for span in card.css("span"):
                txt = span.text(strip=True)
                if txt in ("Ouvert", "Fermé", "Termine"):
                    status = txt
                    break

            # Budget : span avec title="Budget"
            budget_node = card.css_first('span[title="Budget"]')
            budget_text = budget_node.text(strip=True).replace("\xa0", " ") if budget_node else ""

            # Date : span avec "Il y a X..."
            posted_text = ""
            for span in card.css("span"):
                txt = span.text(strip=True)
                if txt.startswith("Il y a "):
                    posted_text = txt
                    break

            # Offres + vues : span avec title="Offres" et title="Vues"
            offers_count = self._extract_int(card, 'span[title="Offres"]')
            views_count = self._extract_int(card, 'span[title="Vues"]')

            # Tags (compétences) : span avec class bg-gray-50
            tags = []
            for tag_node in card.css("span.bg-gray-50"):
                tag = tag_node.text(strip=True)
                if tag and tag not in tags:
                    tags.append(tag)

            missions.append(
                Mission(
                    source=self.name,
                    title=title,
                    url=url,
                    description=description,
                    budget_text=budget_text,
                    posted_text=posted_text,
                    offers_count=offers_count,
                    views_count=views_count,
                    tags=tags,
                    status=status,
                )
            )

        return missions

    @staticmethod
    def _extract_int(parent, selector: str) -> int:
        node = parent.css_first(selector)
        if node is None:
            return 0
        text = node.text(strip=True)
        match = re.search(r"\d+", text)
        return int(match.group()) if match else 0
