# 📋 Mission Scanner

> Agent Python qui scrape les plateformes freelance françaises chaque matin, demande à Claude de noter les missions selon mon profil, et m'envoie un email avec le top des opportunités à viser.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Powered by Claude](https://img.shields.io/badge/powered%20by-Claude-orange.svg)](https://www.anthropic.com/)
[![GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF.svg)](.github/workflows/daily.yml)

---

## 🎯 Pourquoi

Quand on est freelance, scanner Codeur.com / Freelance.com tous les matins prend 30 min. Cet agent :

1. **Scrape** les missions ouvertes en parallèle (asyncio)
2. **Demande à Claude** de noter chaque mission de 0 à 10 selon mon profil
3. **Filtre** par score min + concurrence max (combien de propositions déjà reçues)
4. **Génère une accroche personnalisée** prête à coller pour postuler
5. **Envoie un email** avec le top des opportunités

→ 30 min/jour économisées + missions fraîches captées en premier.

## 🏗️ Architecture

```
mission-scanner/
├── config.yaml              # Profil utilisateur + filtres
├── src/
│   ├── models.py            # Pydantic : Mission, ScoredMission, Config
│   ├── scorer.py            # Wrapper Claude avec parsing JSON tolérant
│   ├── delivery.py          # Email Resend + affichage console
│   ├── main.py              # Orchestration asynchrone
│   ├── sources/             # Strategy Pattern par plateforme
│   │   ├── base.py
│   │   └── codeur.py        # Scraping Codeur.com (selectolax)
│   └── templates/
│       └── missions.html    # Email HTML responsive
└── .github/workflows/
    └── daily.yml            # Cron quotidien à 6h UTC
```

## 🚀 Installation

```bash
git clone https://github.com/pitttpittt/mission-scanner.git
cd mission-scanner
uv sync
cp .env.example .env  # puis édite avec tes clés Anthropic + Resend
uv run python -m src.main
```

## 🛠️ Stack

Python 3.11 · asyncio · httpx · selectolax · Pydantic v2 · Anthropic SDK · Jinja2 · Resend · GitHub Actions

## 🧠 Choix techniques notables

- **Strategy Pattern** sur les sources : ajouter une plateforme = ~80 lignes
- **Pré-filtrage** des missions trop concurrentielles avant l'appel LLM (économie de tokens)
- **Parsing JSON tolérant** : Claude oublie parfois une virgule ou un champ, on répare
- **Champ `proposal_hook`** : Claude génère une accroche personnalisée pour chaque mission, prête à copier-coller

## 📊 Résultats

Sur ~35 missions Codeur scrapées chaque matin, le scanner en retient typiquement **5 à 10** qui matchent réellement le profil — soit 20-30% du flux. Le reste (graphisme, vidéo, autres langages, etc.) est filtré automatiquement.

## 📄 License

MIT
