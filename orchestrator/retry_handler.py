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
        self.patterns_applied: list = []
        self.reflection_advice: Optional[dict] = None
        self.best_finding_count: Optional[int] = None
        self.best_backup: Optional[str] = None
        self.decision_trace: list = []

    def record_decision(self, decision, agent: Optional[str] = None, reason: Optional[str] = None, action: Optional[str] = None, stage: Optional[str] = None) -> None:
        """Log a structured agent decision or high-level self-healing event to the trace."""
        from datetime import datetime
        if isinstance(decision, dict):
            entry = dict(decision)
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
            self.decision_trace.append(entry)
            print(f"[Decision Trace] [{entry.get('agent', 'System')}] {entry.get('action', entry.get('decision', ''))} (Reason: {entry.get('reason', 'N/A')})")
        elif agent or reason or action:
            entry = {
                "decision": str(decision),
                "agent": agent or "System",
                "stage": stage or "Pipeline",
                "reason": reason or "",
                "action": action or str(decision),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            self.decision_trace.append(entry)
            print(f"[Decision Trace] [{entry['agent']}] {entry['action']} (Reason: {entry['reason']})")
        else:
            entry = {
                "decision": str(decision),
                "agent": "System",
                "stage": "Pipeline",
                "action": str(decision),
                "reason": "",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            self.decision_trace.append(entry)
            print(f"[Decision Trace] Logged: '{decision}'")

    @property
    def has_retries_left(self) -> bool:
        return self.current_round <= self.max_rounds

    def record_errors(self, error_text: str) -> None:
        """Store raw errors and enrich with known-fix advice."""
        self.errors.append(error_text)
        pm = _get_pattern_manager()
        
        # Track specific patterns matched
        hits = pm.match(error_text)
        for h in hits:
            # Store subset of fields to prevent database bloat
            pat_summary = {
                "error_substring": h.get("error_substring"),
                "description": h.get("description"),
                "fix": h.get("fix"),
                "category": h.get("category"),
                "severity": h.get("severity")
            }
            if pat_summary not in self.patterns_applied:
                self.patterns_applied.append(pat_summary)
                
        # Format matching advice, giving priority to trusted advice over candidate advice
        trusted_hits = pm.match_trusted(error_text)
        candidate_hits = pm.match_candidates(error_text)
        display_hits = trusted_hits if trusted_hits else candidate_hits
        
        if display_hits:
            lines = ["📚 **Known Failure Pattern(s) Detected:**\n"]
            for p in display_hits:
                status_label = f"TRUSTED:{p.get('severity')}" if p.get('status') == 'trusted' else f"CANDIDATE:{p.get('severity')}"
                lines.append(
                    f"  ⚠️  [{status_label}] {p['description']}\n"
                    f"  🔧  FIX: {p['fix']}\n"
                )
            self.advice = "\n".join(lines)
            print(f"\n📚 Pattern Manager matched known fixes:\n{self.advice}")
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
