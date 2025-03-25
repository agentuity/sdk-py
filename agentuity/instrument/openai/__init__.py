def instrument():
    from agents import (
        TracingProcessor,
        add_trace_processor,
        set_trace_processors,
        Trace,
        Span,
    )
    import os
    from abc import ABC
    from typing import Any
    from opentelemetry import trace
    import logging

    logger = logging.getLogger(__name__)

    class OpenTelemetryTracingProcessor(TracingProcessor, ABC):
        def __init__(self):
            super().__init__()
            self.tracer = trace.get_tracer(__name__)
            self.state = {}
            logger.debug("OpenTelemetryTracingProcessor initialized")

        def on_trace_start(self, t: Trace) -> None:
            logger.debug("OpenTelemetryTracingProcessor on_trace_start")
            # Create a new trace and store the span in state
            attributes = {k: v for k, v in t.export().items() if v is not None}
            if t.metadata is not None:
                attributes.update(
                    {k: v for k, v in t.metadata.items() if v is not None}
                )
            attributes["@agentuity/provider"] = "openai"
            if t.group_id is not None:
                attributes["group_id"] = t.group_id
            current_span = trace.get_current_span()
            span = self.tracer.start_span(
                name=t.name,
                attributes=attributes,
                context=trace.set_span_in_context(current_span),
            )
            self.state[t.trace_id] = span

        def on_trace_end(self, t: Trace) -> None:
            logger.debug("OpenTelemetryTracingProcessor on_trace_end")
            # End the current trace and clean up state
            if t.trace_id in self.state:
                thespan = self.state[t.trace_id]
                thespan.set_status(trace.StatusCode.OK)
                thespan.end()
                del self.state[t.trace_id]

        def on_span_start(self, span: Span[Any]) -> None:
            logger.debug("OpenTelemetryTracingProcessor on_span_start")
            name = f"openai.agents.{span.span_data.type}"
            parent_id = span.parent_id
            if parent_id is None:
                parent_id = span.trace_id
            if parent_id in self.state:
                current_span = self.state[parent_id]
                attributes = {
                    k: v for k, v in span.span_data.export().items() if v is not None
                }
                # Add attributes from __slots__ since some of the
                # attributes are not in the export() method
                if hasattr(span.span_data, "__slots__"):
                    for slot in span.span_data.__slots__:
                        if hasattr(span.span_data, slot) and slot not in attributes:
                            value = getattr(span.span_data, slot)
                            if value is not None:
                                attributes[slot] = str(value)
                attributes["@agentuity/provider"] = "openai"
                child_span = self.tracer.start_span(
                    name=name,
                    context=trace.set_span_in_context(current_span),
                    attributes=attributes,
                )
                self.state[span.span_id] = child_span
            else:
                print(f"No parent span found for {span.span_id}")

        def on_span_end(self, span: Span[Any]) -> None:
            logger.debug("OpenTelemetryTracingProcessor on_span_end")
            if span.span_id in self.state:
                thespan = self.state[span.span_id]
                thespan.set_status(trace.StatusCode.OK)
                thespan.end()
                del self.state[span.span_id]

        def shutdown(self) -> None:
            logger.debug("OpenTelemetryTracingProcessor shutdown")

        def force_flush(self) -> None:
            logger.debug("OpenTelemetryTracingProcessor force_flush")

    if os.getenv("OPENAI_API_KEY", "") == os.getenv("AGENTUITY_API_KEY", ""):
        set_trace_processors([OpenTelemetryTracingProcessor()])
        logger.info("Configured OpenAI Agents to use Agentuity")
    else:
        add_trace_processor(OpenTelemetryTracingProcessor())
        logger.info("Configured OpenAI Agents to add Agentuity")
