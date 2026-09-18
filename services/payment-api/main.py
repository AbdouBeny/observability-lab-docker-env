import os
import time
import random
import logging

from fastapi import FastAPI, HTTPException

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


# LOGGING

LoggingInstrumentor().instrument(
    set_logging_format=True,
    logging_format=(
        "%(asctime)s %(levelname)s %(name)s "
        "[service=%(otelServiceName)s] "
        "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] "
        "- %(message)s"
    ),
)

logger = logging.getLogger("payment-api")


# OPENTELEMETRY

resource = Resource.create({
    "service.name": "payment-api"
})

provider = TracerProvider(resource=resource)

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://otel-collector:4317"
    ),
    insecure=True,
)

provider.add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

trace.set_tracer_provider(provider)


# FASTAPI

app = FastAPI(title="Payment API")

FastAPIInstrumentor.instrument_app(app)


# HEALTH

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "payment-api"
    }


# PAYMENT

@app.post("/pay")
async def process_payment():

    tracer = trace.get_tracer(__name__)


    delay = random.choice([
        0.1,
        0.2,
        2.5,
        3.0
    ])

    if delay > 2.0:
        logger.warning(
            f"Artificial delay detected: {delay}s"
        )

        time.sleep(delay)

    with tracer.start_as_current_span(
        "database-payment-query"
    ) as span:

        # Environ 1 requête sur 3 provoque une erreur
        if random.randint(1, 3) == 1:

            error_msg = (
                "Database timeout while processing payment"
            )

            logger.error(error_msg)

            exception = Exception(error_msg)

            span.record_exception(exception)

            span.set_status(
                trace.StatusCode.ERROR,
                "Database timeout"
            )

            raise HTTPException(
                status_code=500,
                detail="Database timeout / Connection lost"
            )

    logger.info(
        f"Payment approved in {delay}s"
    )

    return {
        "payment_status": "approved",
        "processed_in_seconds": delay
    }
