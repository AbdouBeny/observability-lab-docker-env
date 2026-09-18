import os
import time
import httpx
import logging

from fastapi import FastAPI, Response, HTTPException

from prometheus_client import Counter, Histogram, REGISTRY
from prometheus_client.openmetrics.exposition import (
    generate_latest,
    CONTENT_TYPE_LATEST,
)

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter



# LOGGING
#logging.basicConfig(level=logging.INFO)



LoggingInstrumentor().instrument(
    set_logging_format=True,
    logging_format=(
        "%(asctime)s %(levelname)s "
        "[service=%(otelServiceName)s] "
        "[trace_id=%(otelTraceID)s "
        "span_id=%(otelSpanID)s] "
        "- %(message)s"
    ),
)

logger = logging.getLogger("api-gateway")


# OPENTELEMETRY
resource = Resource.create({
    "service.name": "api-gateway"
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
app = FastAPI(title="API Gateway")

FastAPIInstrumentor.instrument_app(app)

HTTPXClientInstrumentor().instrument()



# CONFIGURATION
ORDER_API_URL = os.getenv(
    "ORDER_API_URL",
    "http://order-api:8000"
)



# PROMETHEUS METRICS
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    [
        "method",
        "endpoint",
        "status",
    ],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency",
    [
        "method",
        "endpoint",
    ],
)



# PROMETHEUS MIDDLEWARE
@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()

    tracer = trace.get_tracer("api-gateway")

    with tracer.start_as_current_span("http-request-metrics") as span:
        response = await call_next(request)

        duration = time.time() - start_time

        if request.url.path != "/metrics":
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=str(response.status_code),
            ).inc()

            span_context = span.get_span_context()

            if span_context.is_valid:
                trace_id = format(span_context.trace_id, "032x")

                logger.info(
                    f"Adding Prometheus exemplar traceID={trace_id}"
                )

                REQUEST_LATENCY.labels(
                    method=request.method,
                    endpoint=request.url.path,
                ).observe(
                    duration,
                    exemplar={"traceID": trace_id},
                )
            else:
                logger.warning(
                    "No valid OpenTelemetry span found for Prometheus exemplar"
                )

        return response


# HEALTH
@app.get("/health")
def health():

    logger.info(
        "Health check endpoint called"
    )

    return {
        "status": "healthy",
        "service": "api-gateway",
    }



# CHECKOUT
@app.post("/checkout")
async def checkout():

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "gateway-checkout-process"
    ):

        logger.info(
            "Starting checkout process from gateway"
        )

        async with httpx.AsyncClient() as client:

            try:

            
                response = await client.post(
                    f"{ORDER_API_URL}/orders",
                    timeout=5.0,
                )

                if response.status_code >= 400:

                    logger.error(
                        "Order API returned error status: "
                        f"{response.status_code}"
                    )

                    raise HTTPException(
                        status_code=response.status_code,
                        detail=response.json(),
                    )

                return {
                    "gateway": "success",
                    "order_service": response.json(),
                }

            except httpx.RequestError as e:

                logger.error(
                    f"Order service unavailable: {str(e)}"
                )

                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Order service unavailable: "
                        f"{str(e)}"
                    ),
                )



# PROMETHEUS /metrics
@app.get("/metrics")
def metrics():

    return Response(
        generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
