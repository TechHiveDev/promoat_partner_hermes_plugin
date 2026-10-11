"""Promoat Hermes plugin — registers partner tools and the operating skill."""

from pathlib import Path

try:
    from .schemas import SCHEMAS
    from .tools import HANDLERS
except ImportError:
    from schemas import SCHEMAS
    from tools import HANDLERS


def register(ctx):
    for name, handler in HANDLERS.items():
        ctx.register_tool(
            name=name,
            toolset="promoat",
            schema=SCHEMAS[name],
            handler=handler,
        )
    skill = Path(__file__).resolve().parent / "skills" / "promoat-partner-api" / "SKILL.md"
    if skill.is_file():
        ctx.register_skill("promoat-partner-api", skill)
