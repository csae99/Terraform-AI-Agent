"""
Retry Handler – self-healing loop logic.

Provides configurable retry behaviour with pattern-aware feedback
injection for the Development → Validation sub-loop.
"""

from typing import Callable, Dict, Optional
from memory.pattern_manager import PatternManager


# Singleton pattern manager shared across retry attempts
_pattern_mgr: Optional[PatternManager] = None


def _get_pattern_manager() -> PatternManager:
    """Lazy-load the PatternManager singleton."""
    global _pattern_mgr
    if _pattern_mgr is None:
        _pattern_mgr = PatternManager()
    return _pattern_mgr


class RetryContext:
    """Accumulates errors and known-fix advice across retry iterations."""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.current_round = 1
        self.errors: list = []
        self.advice: str = ""
        self.best_finding_count: Optional[int] = None
        self.best_backup: Optional[str] = None

    @property
    def has_retries_left(self) -> bool:
        return self.current_round <= self.max_rounds

    def record_errors(self, error_text: str) -> None:
        """Store raw errors and enrich with known-fix advice."""
        self.errors.append(error_text)
        pm = _get_pattern_manager()
        advice = pm.format_advice(error_text)
        if advice:
            self.advice = advice
            print(f"\n📚 Pattern Manager matched known fixes:\n{advice}")
        else:
            self.advice = ""

    def advance(self) -> None:
        self.current_round += 1


def should_retry(error_text: str) -> bool:
    """Quick heuristic: should the pipeline retry based on the error?

    Returns False for hard-stop errors (credentials, budget), True
    for fixable issues (syntax, parameter values, naming).
    """
    hard_stops = [
        "No valid credential sources found",
        "budget exceeded",
        "OVER BUDGET",
    ]
    for stop in hard_stops:
        if stop.lower() in error_text.lower():
            return False
    return True
