"""Scraper Free-Work.com via leur API JSON publique.

Free-Work expose une API Hydra/JSON-LD non authentifiée :
  GET /api/job_postings?contracts=contractor&itemsPerPage=20

Ça nous évite de scraper du HTML — réponse structurée, stable, propre.
"""

from html.parser import HTMLParser as _HTMLParser
from typing import Any

import httpx

from src.models import Mission
from src.sources.base import Source

BASE_URL = "https://www.free-work.com"
API_URL = f"{BASE_URL}/api/job_postings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/ld+json",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


class _TextExtractor(_HTMLParser):
    """Extrait le texte d'un fragment HTML (pour les descriptions)."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


def _strip_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text


class FreeWorkSource(Source):
    name = "free_work"

    # Mots-clés ciblés sur le profil. Une requête API par mot-clé.
    DEFAULT_KEYWORDS: tuple[str, ...] = (
        "python",
        "automatisation",
        "scraping",
        "IA",
    )

    def __init__(
        self,
        items_per_keyword: int = 8,
        keywords: tuple[str, ...] | None = None,
    ):
        self.items_per_keyword = items_per_keyword
        self.keywords = keywords or self.DEFAULT_KEYWORDS

    async def fetch(self, client: httpx.AsyncClient) -> list[Mission]:
        seen_ids: set[int] = set()
        missions: list[Mission] = []

        for keyword in self.keywords:
            try:
                items = await self._fetch_keyword(client, keyword)
            except Exception as e:
                print(f"⚠️  Free-Work [{keyword}]: {e}")
                continue

            for item in items:
                item_id = item.get("id")
                if item_id is None or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                mission = self._to_mission(item)
                if mission:
                    missions.append(mission)

        return missions

    async def _fetch_keyword(
        self, client: httpx.AsyncClient, keyword: str
    ) -> list[dict[str, Any]]:
        params = {
            "contracts": "contractor",
            "searchKeywords": keyword,
            "itemsPerPage": str(self.items_per_keyword),
            "page": "1",
        }
        resp = await client.get(API_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        members = data.get("hydra:member", [])
        return [m for m in members if isinstance(m, dict)]

    def _to_mission(self, item: dict[str, Any]) -> Mission | None:
        title = (item.get("title") or "").strip()
        slug = (item.get("slug") or "").strip()
        if not title or not slug:
            return None

        # Description : HTML brut → texte
        raw_desc = item.get("description") or ""
        description = _strip_html(raw_desc)[:400]

        # Budget : mapper minDailySalary / maxDailySalary si présents
        min_salary = item.get("minDailySalary")
        max_salary = item.get("maxDailySalary")
        currency = item.get("currency", "EUR") or "EUR"
        budget_text = self._format_budget(min_salary, max_salary, currency)

        # Date : publishedAt
        posted_text = self._format_date(item.get("publishedAt"))

        # Tags : skills + experienceLevel + remoteMode
        tags: list[str] = []
        skills = item.get("skills") or []
        for s in skills[:8]:
            if isinstance(s, dict) and s.get("name"):
                tags.append(s["name"])
            elif isinstance(s, str):
                tags.append(s)
        if exp := item.get("experienceLevel"):
            tags.append(f"XP: {exp}")
        if rm := item.get("remoteMode"):
            tags.append(f"Remote: {rm}")

        # URL : on construit depuis le slug + la catégorie/job si dispo
        job_data = item.get("job") or {}
        category = ""
        if isinstance(job_data, dict):
            category = job_data.get("slug", "") or ""

        if category:
            url = f"{BASE_URL}/fr/tech-it/{category}/job-mission/{slug}"
        else:
            url = f"{BASE_URL}/fr/tech-it/jobs/{slug}"

        return Mission(
            source=self.name,
            title=title,
            url=url,
            description=description,
            budget_text=budget_text,
            posted_text=posted_text,
            offers_count=0,  # Free-Work ne fournit pas le compteur
            views_count=0,
            tags=tags,
            status=item.get("status", "published") or "",
        )

    @staticmethod
    def _format_budget(
        min_salary: int | None, max_salary: int | None, currency: str
    ) -> str:
        if not min_salary and not max_salary:
            return ""
        sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency.upper(), currency)
        if min_salary and max_salary and min_salary != max_salary:
            return f"{min_salary}-{max_salary} {sym}/j"
        if max_salary:
            return f"{max_salary} {sym}/j"
        return f"{min_salary} {sym}/j"

    @staticmethod
    def _format_date(date_str: Any) -> str:
        if not date_str or not isinstance(date_str, str):
            return ""
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            seconds = delta.total_seconds()
            if seconds < 3600:
                return f"Il y a {int(seconds // 60)} minutes"
            if seconds < 86400:
                return f"Il y a {int(seconds // 3600)} heures"
            return f"Il y a {int(seconds // 86400)} jours"
        except (ValueError, TypeError):
            return date_str[:10]
