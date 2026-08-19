import time
import uuid
import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Span:
    """Represents an OpenTelemetry-compatible tracing span."""
    def __init__(self, name: str, parent_id: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.trace_id = str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())[:16]
        self.parent_id = parent_id
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: float = 0.0
        self.status = "UNSET"  # OK, ERROR, UNSET
        self.attributes: Dict[str, Any] = attributes or {}
        self.events = []

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_status(self, status: str, description: Optional[str] = None):
        self.status = status
        if description:
            self.attributes["status_description"] = description

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })

    def finish(self):
        self.end_time = time.time()
        self.duration = round(self.end_time - self.start_time, 4)
        if self.status == "UNSET":
            self.status = "OK"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration * 1000, 2),
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events
        }


class OpenTelemetryTracer:
    """
    Lightweight OpenTelemetry Tracer for Multi-Agent Workflows.
    Stores spans in-memory with optional forwarders to OTLP collector / Prometheus.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenTelemetryTracer, cls).__new__(cls)
            cls._instance._spans = []
            cls._instance._active_span = None
        return cls._instance

    @contextmanager
    def start_as_current_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        parent_id = self._active_span.span_id if self._active_span else None
        span = Span(name=name, parent_id=parent_id, attributes=attributes)
        prev_span = self._active_span
        self._active_span = span
        try:
            yield span
        except Exception as e:
            span.set_status("ERROR", str(e))
            span.set_attribute("error.message", str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
        finally:
            span.finish()
            self._spans.append(span)
            # Keep rolling window of last 500 spans
            if len(self._spans) > 500:
                self._spans = self._spans[-500:]
            self._active_span = prev_span

    def get_recent_spans(self, limit: int = 50):
        return [s.to_dict() for s in reversed(self._spans[-limit:])]

    def clear(self):
        self._spans = []


# Singleton accessor
tracer = OpenTelemetryTracer()

def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager helper for tracing spans."""
    return tracer.start_as_current_span(name, attributes)
