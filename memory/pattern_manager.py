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
                    category: str = "user_reported", severity: str = "MEDIUM",
                    success_count: int = 1, failure_count: int = 0,
                    confidence: float = 0.8, last_used: Optional[str] = None) -> None:
        """Add a new pattern to the in-memory store (and persist to disk), or update if exists."""
        from datetime import datetime
        if not last_used:
            last_used = datetime.utcnow().isoformat() + "Z"

        # Check for deduplication
        existing = next(
            (p for p in self._patterns if p["error_substring"].lower() == error_substring.lower()),
            None
        )

        if existing:
            # Update existing pattern
            existing["description"] = description
            existing["fix"] = fix
            existing["category"] = category
            existing["severity"] = severity
            # Don't overwrite stats, let other methods manage confidence/success counts
            if "success_count" not in existing:
                existing["success_count"] = success_count
            if "failure_count" not in existing:
                existing["failure_count"] = failure_count
            if "confidence" not in existing:
                existing["confidence"] = confidence
            existing["last_used"] = last_used
            print(f"[PatternManager] Updated existing pattern: {error_substring}")
        else:
            pattern = {
                "error_substring": error_substring,
                "category": category,
                "severity": severity,
                "description": description,
                "fix": fix,
                "success_count": success_count,
                "failure_count": failure_count,
                "confidence": confidence,
                "last_used": last_used
            }
            self._patterns.append(pattern)
            print(f"[PatternManager] Added new pattern: {error_substring}")
            
        self._persist()

    def decay_pattern(self, error_substring: str) -> None:
        """Decay the confidence of a pattern because it failed to resolve the issue."""
        from datetime import datetime
        existing = next(
            (p for p in self._patterns if p["error_substring"].lower() == error_substring.lower()),
            None
        )
        if existing:
            existing["failure_count"] = existing.get("failure_count", 0) + 1
            current_conf = existing.get("confidence", 0.8)
            # Decay confidence by 0.1 down to a minimum of 0.1
            existing["confidence"] = round(max(0.1, current_conf - 0.1), 2)
            existing["last_used"] = datetime.utcnow().isoformat() + "Z"
            print(f"[PatternManager] Decayed pattern '{error_substring}' confidence to {existing['confidence']}")
            self._persist()

    def learn_from_run(self, error_logs: str, fix_applied: str) -> None:
        """Call LLM to extract a reusable failure pattern and persist it."""
        import litellm
        from datetime import datetime
        
        # Check if we have an API key configured for LiteLLM calls
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("[PatternManager] Skip dynamic learning: No API key found.")
            return

        model = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
        
        prompt = f"""
You are an expert DevOps engineer and AI teacher.
We had a Terraform execution failure that we successfully fixed in a self-healing loop.
Please analyze the error log and the fix that was applied to create a new, reusable "Failure Pattern" that can be used to prevent this issue in the future.

ERROR LOG:
\"\"\"{error_logs}\"\"\"

FIX APPLIED:
\"\"\"{fix_applied}\"\"\"

Your task is to extract:
1. Error Substring: A unique, exact, case-insensitive substring from the error log that reliably identifies this specific error. Keep it concise (e.g. "BucketAlreadyExists" or "Unsupported attribute"). Do NOT include dynamic/unique identifiers like bucket names, IP addresses, or resource IDs.
2. Description: A short, clear description of the problem.
3. Fix Advice: General, actionable developer advice on how to fix this issue (e.g., "Append a random suffix to the bucket name to ensure uniqueness").
4. Category: A category label (e.g. "aws_s3", "syntax_error", "iam_permissions", "network_configs").
5. Severity: One of: "CRITICAL", "HIGH", "MEDIUM", "LOW".

Return the output strictly in the following JSON format:
{{
  "error_substring": "...",
  "description": "...",
  "fix": "...",
  "category": "...",
  "severity": "..."
}}
"""
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            sub = parsed.get("error_substring")
            desc = parsed.get("description")
            fix = parsed.get("fix")
            cat = parsed.get("category", "auto_learned")
            sev = parsed.get("severity", "MEDIUM")
            
            if sub and fix:
                # Check if it already exists to increment success/confidence
                existing = next(
                    (p for p in self._patterns if p["error_substring"].lower() == sub.lower()),
                    None
                )
                if existing:
                    existing["success_count"] = existing.get("success_count", 1) + 1
                    current_conf = existing.get("confidence", 0.8)
                    existing["confidence"] = round(min(1.0, current_conf + 0.05), 2)
                    existing["last_used"] = datetime.utcnow().isoformat() + "Z"
                    self._persist()
                    print(f"[PatternManager] Successfully reinforced pattern '{sub}': success_count={existing['success_count']}, confidence={existing['confidence']}")
                else:
                    self.add_pattern(
                        error_substring=sub,
                        description=desc or f"Auto-learned pattern for error: {sub}",
                        fix=fix,
                        category=cat,
                        severity=sev,
                        success_count=1,
                        failure_count=0,
                        confidence=0.8,
                        last_used=datetime.utcnow().isoformat() + "Z"
                    )
                    print(f"[PatternManager] Successfully auto-learned failure pattern: {sub}")
            else:
                print(f"[PatternManager] Failed to auto-learn: JSON missing required fields.")
        except Exception as e:
            print(f"[PatternManager] Warning: failed to learn from run: {e}")

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
