"""Interface commune à toutes les sources de missions."""

from abc import ABC, abstractmethod

import httpx

from src.models import Mission


class Source(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[Mission]:
        ...
