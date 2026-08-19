import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

class MetricsCollector:
    """
    In-memory metrics collector tracking counters, gauges, and histograms.
    Provides Prometheus-compatible text output and JSON summaries.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsCollector, cls).__new__(cls)
            cls._instance._counters = defaultdict(float)
            cls._instance._gauges = defaultdict(float)
            cls._instance._histograms = defaultdict(list)
            cls._instance._run_history = []
        return cls._instance

    def increment(self, metric_name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(metric_name, labels)
        self._counters[key] += value

    def gauge(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(metric_name, labels)
        self._gauges[key] = value

    def record_duration(self, metric_name: str, duration_seconds: float, labels: Optional[Dict[str, str]] = None):
        key = self._format_key(metric_name, labels)
        self._histograms[key].append(duration_seconds)
        # Keep last 200 data points per metric
        if len(self._histograms[key]) > 200:
            self._histograms[key] = self._histograms[key][-200:]

    def record_run(self, slug: str, status: str, engine: str, duration: float, cost: float,
                   tokens: int = 0, healing_rounds: int = 0, security_issues: int = 0, user_id: Any = None, org_id: Any = None):
        record = {
            "slug": slug,
            "status": status,
            "engine": engine,
            "duration": round(duration, 2),
            "cost": round(cost, 2),
            "tokens": tokens,
            "healing_rounds": healing_rounds,
            "security_issues": security_issues,
            "user_id": user_id,
            "org_id": org_id,
            "timestamp": time.time()
        }
        self._run_history.append(record)
        if len(self._run_history) > 1000:
            self._run_history = self._run_history[-1000:]

        # Increment standard counters
        labels = {"engine": engine, "status": status}
        self.increment("terraform_agent_runs_total", 1, labels)
        self.increment("terraform_agent_tokens_total", tokens, {"engine": engine})
        self.increment("terraform_agent_healing_rounds_total", healing_rounds, {"engine": engine})
        self.record_duration("terraform_agent_run_duration_seconds", duration, {"engine": engine})

    def _format_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_summary(self) -> Dict[str, Any]:
        """Returns JSON metrics summary."""
        total_runs = len(self._run_history)
        success_runs = sum(1 for r in self._run_history if r.get("status") in ("deployed", "generated", "pr_opened", "success"))
        failed_runs = total_runs - success_runs
        success_rate = round((success_runs / total_runs * 100), 1) if total_runs > 0 else 100.0

        avg_duration = 0.0
        if self._run_history:
            avg_duration = round(sum(r.get("duration", 0) for r in self._run_history) / total_runs, 2)

        total_tokens = sum(r.get("tokens", 0) for r in self._run_history)
        total_infra_cost = round(sum(r.get("cost", 0) for r in self._run_history), 2)
        total_healing_rounds = sum(r.get("healing_rounds", 0) for r in self._run_history)

        return {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "success_rate_percent": success_rate,
            "avg_duration_seconds": avg_duration,
            "total_tokens_consumed": total_tokens,
            "total_infra_cost_projected": total_infra_cost,
            "total_healing_rounds": total_healing_rounds,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "recent_runs": self._run_history[-20:]
        }

    def to_prometheus_format(self) -> str:
        """Exports metrics in Prometheus exposition format."""
        lines = []
        lines.append("# HELP terraform_agent_runs_total Total number of agent runs executed")
        lines.append("# TYPE terraform_agent_runs_total counter")
        for key, val in self._counters.items():
            lines.append(f"{key} {val}")
        for key, val in self._gauges.items():
            lines.append(f"{key} {val}")
        return "\n".join(lines) + "\n"

# Singleton
metrics = MetricsCollector()
