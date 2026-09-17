"""Public, database-independent analysis boundary."""

from .schemas import validate_requirements


def __getattr__(name):
    # Old evaluations and unfinished historical workflows keep explicit legacy behavior.
    # New semantic assessments do not import the numeric rule engine.
    if name in {"analyze", "embed_text", "propose_requirements"}:
        from . import engine

        return getattr(engine, name)
    raise AttributeError(name)


__all__ = [
    "analyze",
    "embed_text",
    "propose_requirements",
    "validate_requirements",
]
