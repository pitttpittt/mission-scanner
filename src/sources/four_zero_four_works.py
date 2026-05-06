"""Scraper 404Works.com.

Scrape la liste publique des missions FR. Note : 404Works publie
beaucoup de missions commerciales/vidéo en plus des missions tech ;
le filtrage par score Claude se charge du tri.
"""

import httpx
from selectolax.parser import HTMLParser

from src.models import Mission
from src.sources.base import Source

BASE_URL = "https://www.404works.com"
LIST_URL = f"{BASE_URL}/fr/projects"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


class FourZeroFourWorksSource(Source):
    name = "404works"

    async def fetch(self, client: httpx.AsyncClient) -> list[Mission]:
        try:
            resp = await client.get(LIST_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"❌ 404Works: erreur HTTP {e}")
            return []

        return self._parse(resp.text)

    def _parse(self, html: str) -> list[Mission]:
        tree = HTMLParser(html)
        missions: list[Mission] = []

        # Chaque mission est une div.row.bloc contenant un h5 > a
        for row in tree.css("div.row.bloc"):
            link = row.css_first('h5 a[href*="/fr/project/"]')
            if link is None:
                continue

            href = link.attributes.get("href", "").strip()
            if not href:
                continue

            url = f"{BASE_URL}{href}" if href.startswith("/") else href
            title = link.text(strip=True) or "(sans titre)"

            # Description courte (peut être absente)
            desc_node = row.css_first("p.grey")
            description = desc_node.text(strip=True) if desc_node else ""

            # Budget dans li.cash
            budget_node = row.css_first("li.cash")
            budget_text = budget_node.text(strip=True) if budget_node else ""

            # Date dans li.time
            time_node = row.css_first("li.time")
            posted_text = time_node.text(strip=True) if time_node else ""

            # Status (ouverte / fermée)
            status_node = row.css_first("span.labelled")
            status = status_node.text(strip=True) if status_node else ""

            # Tags
            tags = [
                tag.text(strip=True)
                for tag in row.css("span.tag")
                if tag.text(strip=True)
            ]

            missions.append(
                Mission(
                    source=self.name,
                    title=title,
                    url=url,
                    description=description,
                    budget_text=budget_text,
                    posted_text=posted_text,
                    offers_count=0,  # 404Works ne montre pas le nombre d'offres en liste
                    views_count=0,
                    tags=tags,
                    status=status,
                )
            )

        return missions
