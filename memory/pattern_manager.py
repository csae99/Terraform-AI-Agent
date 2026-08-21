"""
Pattern Manager - Failure Pattern Knowledge Base.

Loads known Terraform error patterns from the seed catalog and provides
lookup functionality for agents during self-healing loops.
"""

import os
import json
from typing import List, Dict, Optional
from tools.project.tracker import SessionLocal, PatternMemoryModel
from memory.vector_knowledge import VectorKnowledgeEngine


_PATTERNS_FILE = os.path.join(os.path.dirname(__file__), "failure_patterns.json")


class PatternManager:
    """Manages a knowledge base of known Terraform failure patterns and fixes with DB & Vector backing."""

    def __init__(self, patterns_file: str = _PATTERNS_FILE):
        self.patterns_file = patterns_file
        self._patterns: List[Dict] = []
        VectorKnowledgeEngine.ensure_seeded()
        self._load(self.patterns_file)

    def _load(self, path: str) -> None:
        """Load patterns from the Database (with JSON catalog fallback)."""
        session = SessionLocal()
        try:
            db_patterns = session.query(PatternMemoryModel).all()
            if db_patterns:
                self._patterns = [
                    {
                        "id": p.id,
                        "signature": p.signature or p.error_substring,
                        "error_substring": p.error_substring,
                        "category": p.category,
                        "severity": p.severity,
                        "description": p.description,
                        "fix": p.fix,
                        "success_count": p.success_count,
                        "failure_count": p.failure_count,
                        "confidence": p.confidence,
                        "status": p.status,
                        "last_used": p.last_used.isoformat() + "Z" if p.last_used else ""
                    }
                    for p in db_patterns
                ]
                print(f"[PatternManager] Loaded {len(self._patterns)} failure patterns from database.")
                return
        except Exception as e:
            print(f"[PatternManager] DB load note: {e}")
        finally:
            session.close()

        # Fallback to JSON file if DB query failed
        if not os.path.exists(path):
            print(f"[PatternManager] Warning: patterns file not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._patterns = data.get("patterns", [])
        for p in self._patterns:
            if "status" not in p:
                if p.get("success_count", 0) >= 1 or p.get("confidence", 0.0) >= 1.0:
                    p["status"] = "trusted"
                else:
                    p["status"] = "candidate"
        print(f"[PatternManager] Loaded {len(self._patterns)} failure patterns from JSON fallback.")

    # ── Lookup ───────────────────────────────────────────────────────

    def match(self, error_text: str) -> List[Dict]:
        """Return all patterns whose error_substring appears in *error_text* or matches semantically.

        Args:
            error_text: The raw error output from Terraform CLI or cloud API.

        Returns:
            A list of matching pattern dicts, sorted by exact match first then similarity.
        """
        if not error_text:
            return []

        # 1. Exact substring matches
        exact_matches = [
            p for p in self._patterns
            if p["error_substring"].lower() in error_text.lower()
        ]

        # 2. Semantic vector matches via VectorKnowledgeEngine
        semantic_matches = VectorKnowledgeEngine.search_similar_patterns(error_text, top_k=3, min_similarity=0.20)
        
        # Merge results, avoiding duplicates
        seen = set(p["error_substring"].lower() for p in exact_matches)
        combined = list(exact_matches)
        for sm in semantic_matches:
            if sm["error_substring"].lower() not in seen:
                combined.append(sm)
                seen.add(sm["error_substring"].lower())

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        combined.sort(key=lambda p: severity_order.get(p.get("severity", "LOW"), 4))
        return combined

    def semantic_match(self, error_text: str, top_k: int = 3) -> List[Dict]:
        """Direct vector semantic search for failure patterns."""
        return VectorKnowledgeEngine.search_similar_patterns(error_text, top_k=top_k)

    def match_first(self, error_text: str) -> Optional[Dict]:
        """Return the highest-severity matching pattern, or None."""
        hits = self.match(error_text)
        return hits[0] if hits else None

    def match_trusted(self, error_text: str) -> List[Dict]:
        """Return only trusted patterns matching the error text."""
        matches = self.match(error_text)
        return [m for m in matches if m.get("status") == "trusted"]

    def match_candidates(self, error_text: str) -> List[Dict]:
        """Return only candidate patterns matching the error text."""
        matches = self.match(error_text)
        return [m for m in matches if m.get("status") == "candidate"]

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
                    confidence: float = 0.8, last_used: Optional[str] = None,
                    status: str = "candidate") -> None:
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
            if "status" not in existing:
                existing["status"] = status
                
            # Promotion logic
            if existing.get("success_count", 0) >= 3:
                existing["status"] = "trusted"
                
            existing["last_used"] = last_used
            print(f"[PatternManager] Updated existing pattern: {error_substring} (status: {existing['status']})")
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
                "status": status,
                "last_used": last_used
            }
            self._patterns.append(pattern)
            print(f"[PatternManager] Added new pattern: {error_substring} (status: {status})")
            
        self._persist()

    def record_success(self, error_substring: str) -> None:
        """Reinforce pattern confidence on successful fix."""
        from datetime import datetime
        existing = next(
            (p for p in self._patterns if p["error_substring"].lower() == error_substring.lower()),
            None
        )
        if existing:
            existing["success_count"] = existing.get("success_count", 0) + 1
            current_conf = existing.get("confidence", 0.8)
            existing["confidence"] = round(min(1.0, current_conf + 0.05), 2)
            existing["last_used"] = datetime.utcnow().isoformat() + "Z"
            if existing["success_count"] >= 3:
                existing["status"] = "trusted"
            self._persist()
            print(f"[PatternManager] Reinforced pattern '{error_substring}' confidence={existing['confidence']} (success_count={existing['success_count']})")

    def record_failure(self, error_substring: str) -> None:
        """Alias for decay_pattern."""
        self.decay_pattern(error_substring)

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
            
            # Demote status to candidate if confidence is low (<= 0.3)
            if existing["confidence"] <= 0.3:
                existing["status"] = "candidate"
                
            print(f"[PatternManager] Decayed pattern '{error_substring}' confidence to {existing['confidence']} (status: {existing.get('status')})")
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

CRITICAL: Do NOT hallucinate parameters or arguments. The "error_substring", "description", and "fix" MUST reference the EXACT parameters, arguments, or error messages present in the ERROR LOG and the FIX APPLIED. Do not invent or substitute other parameters (for example, do not confuse "enable_auto_scaling" with "enable_node_public_ip").

ERROR LOG:
\"\"\"{error_logs}\"\"\"

FIX APPLIED:
\"\"\"{fix_applied}\"\"\"

Your task is to extract:
1. Error Substring: A unique, exact, case-insensitive substring from the error log that reliably identifies this specific error. Keep it concise (e.g. "enable_auto_scaling" or "BucketAlreadyExists"). Do NOT include dynamic/unique identifiers like bucket names, IP addresses, or resource IDs.
2. Description: A short, clear description of the problem.
3. Fix Advice: General, actionable developer advice on how to fix this issue (e.g., "Rename enable_auto_scaling to auto_scaling_enabled").
4. Category: A category label (e.g. "aws_s3", "terraform_syntax", "iam_permissions", "network_configs").
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
                    
                    # Promotion logic
                    if existing["success_count"] >= 3:
                        existing["status"] = "trusted"
                        
                    self._persist()
                    print(f"[PatternManager] Successfully reinforced pattern '{sub}': success_count={existing['success_count']}, confidence={existing['confidence']} (status: {existing.get('status')})")
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
        """Write the current patterns back to disk and database."""
        # 1. Update JSON file
        data = {"patterns": self._patterns}
        with open(_PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # 2. Synchronize to database
        session = SessionLocal()
        try:
            for p in self._patterns:
                sub = p.get("error_substring")
                if not sub:
                    continue
                db_item = session.query(PatternMemoryModel).filter(PatternMemoryModel.error_substring == sub).first()
                emb = VectorKnowledgeEngine.get_embedding(f"{sub} {p.get('description', '')}")
                if db_item:
                    db_item.success_count = p.get("success_count", db_item.success_count)
                    db_item.failure_count = p.get("failure_count", db_item.failure_count)
                    db_item.confidence = p.get("confidence", db_item.confidence)
                    db_item.status = p.get("status", db_item.status)
                    db_item.description = p.get("description", db_item.description)
                    db_item.fix = p.get("fix", db_item.fix)
                    db_item.embedding = json.dumps(emb)
                    db_item.last_used = datetime.utcnow()
                else:
                    new_item = PatternMemoryModel(
                        signature=p.get("signature") or sub,
                        error_substring=sub,
                        category=p.get("category", "general"),
                        severity=p.get("severity", "MEDIUM"),
                        description=p.get("description", ""),
                        fix=p.get("fix", ""),
                        success_count=p.get("success_count", 1),
                        failure_count=p.get("failure_count", 0),
                        confidence=p.get("confidence", 0.8),
                        status=p.get("status", "candidate"),
                        embedding=json.dumps(emb),
                        last_used=datetime.utcnow()
                    )
                    session.add(new_item)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[PatternManager] DB sync note: {e}")
        finally:
            session.close()

    # ── Stats ────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._patterns)

    def __repr__(self) -> str:
        return f"<PatternManager patterns={self.count}>"
