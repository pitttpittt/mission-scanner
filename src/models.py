"""Modèles de données pour Mission Scanner."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Mission(BaseModel):
    """Une mission scrapée depuis une plateforme freelance."""

    source: str  # "codeur", "freelance_com", etc.
    title: str
    url: HttpUrl
    description: str = ""
    budget_text: str = ""  # "500€ à 1000€" ou "Non précisé"
    posted_text: str = ""  # "Il y a 25 minutes"
    offers_count: int = 0  # nombre de propositions déjà reçues
    views_count: int = 0
    tags: list[str] = Field(default_factory=list)
    status: str = ""  # "Ouvert", etc.


class ScoredMission(BaseModel):
    """Une mission évaluée par Claude."""

    mission: Mission
    score: int  # 0-10
    reason: str  # justification courte
    proposal_hook: str = ""  # phrase d'accroche personnalisée pour postuler


class ScannerConfig(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["codeur"])
    profile_summary: str  # ce que tu sais faire, pour que Claude score bien
    keywords_must_match: list[str] = Field(default_factory=list)
    min_score: int = 6  # ne montrer que les missions notées >= min_score
    max_offers_already: int = 20  # ignorer les missions trop concurrentielles
    top_n: int = 10  # max missions à montrer dans l'email


class LLMConfig(BaseModel):
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 2048


class DeliveryConfig(BaseModel):
    enabled: bool = True
    subject_prefix: str = "Missions du jour —"


class Config(BaseModel):
    scanner: ScannerConfig
    llm: LLMConfig
    delivery: DeliveryConfig

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
