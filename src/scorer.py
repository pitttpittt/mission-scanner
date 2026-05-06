"""Score chaque mission de 0 à 10 selon le profil utilisateur."""

import json
import re
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

from src.models import LLMConfig, Mission, ScannerConfig, ScoredMission


class _LLMScoredItem(BaseModel):
    index: int
    score: int
    reason: str
    proposal_hook: str = ""  # optionnel : Claude oublie parfois


class _LLMResponse(BaseModel):
    items: list[_LLMScoredItem]


class MissionScorer:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = Anthropic()

    def score(
        self,
        missions: list[Mission],
        scanner_config: ScannerConfig,
    ) -> list[ScoredMission]:
        if not missions:
            return []

        filtered = [
            m for m in missions
            if m.offers_count <= scanner_config.max_offers_already
        ]
        if not filtered:
            return []

        items_text = self._format_for_prompt(filtered)

        user_prompt = f"""Tu vas évaluer des missions freelance pour un développeur dont voici le profil :

{scanner_config.profile_summary}

Voici les {len(filtered)} missions à évaluer :

{items_text}

Pour chaque mission, donne un score de 0 (hors-cible) à 10 (parfait), une raison courte (1 phrase), et UNIQUEMENT pour les missions à score >= 5, une accroche personnalisée pour postuler.

CRITÈRES DE SCORE :
- 9-10 : matche pile (Python, automatisation, IA, scraping, bots)
- 7-8 : matche partiellement, vaut le coup
- 5-6 : périphérique mais possible
- 0-4 : hors-cible (laisse proposal_hook vide)

⚠️ CRITIQUE : ton JSON doit être strictement valide. Mets bien les virgules entre TOUS les champs. Inclus toujours le champ "proposal_hook" (chaîne vide pour les scores < 5).

Réponds UNIQUEMENT avec ce JSON, sans texte avant ou après, sans fences markdown :

{{
  "items": [
    {{
      "index": 0,
      "score": 7,
      "reason": "1 phrase",
      "proposal_hook": "1 phrase d'accroche ou chaîne vide"
    }}
  ]
}}"""

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        parsed = self._parse(raw)

        scored: list[ScoredMission] = []
        for item in parsed.items:
            if 0 <= item.index < len(filtered):
                scored.append(
                    ScoredMission(
                        mission=filtered[item.index],
                        score=item.score,
                        reason=item.reason,
                        proposal_hook=item.proposal_hook,
                    )
                )

        scored = [s for s in scored if s.score >= scanner_config.min_score]
        scored.sort(key=lambda s: (-s.score, s.mission.offers_count))
        return scored[: scanner_config.top_n]

    @staticmethod
    def _format_for_prompt(missions: list[Mission]) -> str:
        lines = []
        for i, m in enumerate(missions):
            tags_str = ", ".join(m.tags) if m.tags else "—"
            desc = (m.description[:200] + "...") if len(m.description) > 200 else m.description
            lines.append(
                f"[{i}] ({m.source}) {m.title}\n"
                f"    Budget: {m.budget_text or '?'} | "
                f"Offres déjà reçues: {m.offers_count} | "
                f"Tags: {tags_str}\n"
                f"    Description: {desc}"
            )
        return "\n\n".join(lines)

    def _parse(self, raw: str) -> _LLMResponse:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        # Tentative 1 : JSON pur
        try:
            data: dict[str, Any] = json.loads(text)
            return _LLMResponse(**data)
        except (json.JSONDecodeError, ValidationError):
            pass

        # Tentative 2 : on tente de réparer les virgules manquantes
        # Pattern fréquent : "value"<newline+indent>"key" → "value",<newline+indent>"key"
        repaired = re.sub(r'("\s*\n\s*)"', r'",\n      "', text)
        try:
            data = json.loads(repaired)
            print("⚠️  JSON réparé (virgules manquantes corrigées)")
            return _LLMResponse(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Réponse Claude invalide: {e}\n\nRaw:\n{raw}") from e
