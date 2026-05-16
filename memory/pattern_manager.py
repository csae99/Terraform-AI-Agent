"""
Pattern Manager - Failure Pattern Knowledge Base.

Loads known Terraform error patterns from the seed catalog and provides
lookup functionality for agents during self-healing loops.
"""

import os
import json
from typing import List, Dict, Optional


_PATTERNS_FILE = os.path.join(os.path.dirname(__file__), "failure_patterns.json")


class PatternManager:
    """Manages a knowledge base of known Terraform failure patterns and fixes."""

    def __init__(self, patterns_file: str = _PATTERNS_FILE):
        self._patterns: List[Dict] = []
        self._load(patterns_file)

    def _load(self, path: str) -> None:
        """Load patterns from the JSON catalog."""
        if not os.path.exists(path):
            print(f"[PatternManager] Warning: patterns file not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._patterns = data.get("patterns", [])
        print(f"[PatternManager] Loaded {len(self._patterns)} failure patterns.")

    # ── Lookup ───────────────────────────────────────────────────────

    def match(self, error_text: str) -> List[Dict]:
        """Return all patterns whose error_substring appears in *error_text*.

        Args:
            error_text: The raw error output from Terraform CLI or cloud API.

        Returns:
            A list of matching pattern dicts, sorted by severity (CRITICAL first).
        """
        if not error_text:
            return []

        matches = [
            p for p in self._patterns
            if p["error_substring"].lower() in error_text.lower()
        ]

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        matches.sort(key=lambda p: severity_order.get(p.get("severity", "LOW"), 4))
        return matches

    def match_first(self, error_text: str) -> Optional[Dict]:
        """Return the highest-severity matching pattern, or None."""
        hits = self.match(error_text)
        return hits[0] if hits else None

    # ── Formatting ───────────────────────────────────────────────────

    def format_advice(self, error_text: str) -> str:
        """Return a human-readable advice block suitable for injection into
        an agent prompt.

        Example output:
            ⚠️ KNOWN ISSUE: S3 bucket names must be globally unique …
            🔧 SUGGESTED FIX: Append a random suffix …
        """
        hits = self.match(error_text)
        if not hits:
            return ""

        lines = ["📚 **Known Failure Pattern(s) Detected:**\n"]
        for p in hits:
            lines.append(
                f"  ⚠️  [{p['severity']}] {p['description']}\n"
                f"  🔧  FIX: {p['fix']}\n"
            )
        return "\n".join(lines)

    # ── Persistence (future) ─────────────────────────────────────────

    def add_pattern(self, error_substring: str, description: str, fix: str,
                    category: str = "user_reported", severity: str = "MEDIUM") -> None:
        """Add a new pattern to the in-memory store (and persist to disk)."""
        pattern = {
            "error_substring": error_substring,
            "category": category,
            "severity": severity,
            "description": description,
            "fix": fix,
        }
        self._patterns.append(pattern)
        self._persist()

    def _persist(self) -> None:
        """Write the current patterns back to disk."""
        data = {"patterns": self._patterns}
        with open(_PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ── Stats ────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._patterns)

    def __repr__(self) -> str:
        return f"<PatternManager patterns={self.count}>"
