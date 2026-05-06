"""Mission Scanner — point d'entrée.

Pipeline :
1. Charge la config + .env
2. Scrape les sources actives (en parallèle)
3. Demande à Claude de noter chaque mission de 0 à 10 selon le profil
4. Filtre par score min + concurrence max, garde le top N
5. Affiche en console + envoie par email
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

from src.delivery import display_console, send_email
from src.models import Config, Mission
from src.scorer import MissionScorer
from src.sources.base import Source
from src.sources.codeur import CodeurSource
from src.sources.four_zero_four_works import FourZeroFourWorksSource
from src.sources.free_work import FreeWorkSource

load_dotenv()


SOURCE_REGISTRY: dict[str, type[Source]] = {
    "codeur": CodeurSource,
    "404works": FourZeroFourWorksSource,
    "free_work": FreeWorkSource,
}


async def fetch_all(config: Config) -> list[Mission]:
    sources: list[Source] = []
    for src_name in config.scanner.sources:
        cls = SOURCE_REGISTRY.get(src_name)
        if cls is None:
            print(f"⚠️  Source '{src_name}' pas encore implémentée, skip.")
            continue
        sources.append(cls())

    if not sources:
        return []

    print(f"🔍 Scraping {len(sources)} source(s)...")
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        tasks = [s.fetch(client) for s in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_missions: list[Mission] = []
    for src, res in zip(sources, results, strict=False):
        if isinstance(res, Exception):
            print(f"❌ {src.name}: {res}")
            continue
        print(f"✅ {src.name}: {len(res)} missions")
        all_missions.extend(res)

    return all_missions


async def main() -> None:
    config = Config.load()
    generated_at = datetime.now(ZoneInfo("Europe/Paris"))

    missions = await fetch_all(config)
    print(f"\n📦 Total: {len(missions)} missions collectées")

    if not missions:
        print("⚠️  Aucune mission, stop.")
        return

    print(f"\n🤖 Scoring par Claude ({config.llm.model})...")
    scorer = MissionScorer(config.llm)
    scored = scorer.score(missions, config.scanner)
    print(f"✅ {len(scored)} missions retenues (score >= {config.scanner.min_score})")

    display_console(scored)

    if config.delivery.enabled and scored:
        try:
            send_email(scored, config.delivery, generated_at)
        except Exception as e:
            print(f"❌ Email: {e}")


if __name__ == "__main__":
    asyncio.run(main())
