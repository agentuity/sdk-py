from typing import Optional, Dict, Sequence
from opentelemetry.context import Context
from opentelemetry.trace import get_current_span, set_span_in_context
from opentelemetry.trace.span import TraceFlags
from opentelemetry.propagators.textmap import TextMapPropagator
from opentelemetry.trace.span import NonRecordingSpan
from opentelemetry.trace import SpanContext
from opentelemetry import trace


class AgentuityPropagator(TextMapPropagator):
    """Custom propagator for Agentuity trace context."""

    AGENTUITY_TRACE_ID = "x-agentuity-trace-id"
    AGENTUITY_PARENT_ID = "x-agentuity-parent-id"

    def extract(
        self,
        carrier: Dict[str, str],
        context: Optional[Context] = None,
        getter: Optional[callable] = None,
    ) -> Context:
        """Extract trace context from the carrier."""
        if context is None:
            context = Context()

        if getter is None:
            getter = dict.get

        trace_id = getter(carrier, self.AGENTUITY_TRACE_ID)
        parent_id = getter(carrier, self.AGENTUITY_PARENT_ID)

        if not trace_id:
            return context

        if trace_id.startswith("run_"):
            trace_id = trace_id[4:]

        if parent_id and parent_id.startswith("run_"):
            parent_id = parent_id[4:]

        # Convert trace_id to hex format if it's not already
        if len(trace_id) < 32:
            trace_id = trace_id.zfill(32)  # Pad with zeros if needed

        # Create a span context with the extracted trace information
        span_context = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(parent_id, 16) if parent_id else trace.generate_span_id(),
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )

        # Create a non-recording span with the context
        span = NonRecordingSpan(span_context)
        return set_span_in_context(span, context)

    def inject(
        self,
        carrier: Dict[str, str],
        context: Optional[Context] = None,
        setter: Optional[callable] = None,
    ) -> None:
        """Inject trace context into the carrier."""
        if setter is None:
            setter = carrier.__setitem__

        span = get_current_span(context)
        if span is None:
            return

        span_context = span.get_span_context()
        if span_context is None or not span_context.is_valid:
            return

        setter(carrier, self.AGENTUITY_TRACE_ID, format(span_context.trace_id, "032x"))
        setter(carrier, self.AGENTUITY_PARENT_ID, format(span_context.span_id, "016x"))

    def fields(self) -> Sequence[str]:
        """Return the fields used by the propagator."""
        return [self.AGENTUITY_TRACE_ID, self.AGENTUITY_PARENT_ID]
