"""Envoi du rapport de missions par email via Resend."""

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import DeliveryConfig, ScoredMission

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_jinja = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)


def render_html(scored: list[ScoredMission], generated_at: datetime) -> str:
    template = _jinja.get_template("missions.html")
    return template.render(scored=scored, generated_at=generated_at)


def send_email(
    scored: list[ScoredMission],
    config: DeliveryConfig,
    generated_at: datetime,
) -> None:
    import resend

    api_key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
    recipients_raw = os.environ.get("RESEND_TO", "")

    if not api_key:
        raise RuntimeError("RESEND_API_KEY manquant")
    if not recipients_raw:
        raise RuntimeError("RESEND_TO manquant")

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    date_str = generated_at.strftime("%d/%m/%Y")
    subject = f"{config.subject_prefix} {date_str}  ({len(scored)} missions)"

    html = render_html(scored, generated_at)

    resend.api_key = api_key
    result = resend.Emails.send({
        "from": f"Mission Scanner <{sender}>",
        "to": recipients,
        "subject": subject,
        "html": html,
        "headers": {"X-Mailer": "mission-scanner/0.1"},
    })
    email_id = result.get("id", "?") if isinstance(result, dict) else "?"
    print(f"✉️  Email envoyé à {len(recipients)} destinataire(s) (id={email_id})")


def display_console(scored: list[ScoredMission]) -> None:
    print()
    print("=" * 80)
    print(f"  📋  {len(scored)} missions à viser aujourd'hui")
    print("=" * 80)
    print()
    if not scored:
        print("Aucune mission ne matche tes critères aujourd'hui.")
        return
    for s in scored:
        m = s.mission
        print(f"[{s.score}/10] {m.title}")
        print(f"   💰 {m.budget_text or '?'}  |  📊 {m.offers_count} offres déjà reçues  |  {m.posted_text}")
        print(f"   📌 {s.reason}")
        print(f"   💡 Accroche : {s.proposal_hook}")
        print(f"   🔗 {m.url}")
        print()
