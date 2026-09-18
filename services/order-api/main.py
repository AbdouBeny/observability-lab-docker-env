import os
import httpx

from fastapi import FastAPI, HTTPException

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter



# OPENTELEMETRY
resource = Resource.create({
    "service.name": "order-api"
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

app = FastAPI(title="Order API")

FastAPIInstrumentor.instrument_app(app)

HTTPXClientInstrumentor().instrument()



# CONFIGURATION

PAYMENT_API_URL = os.getenv(
    "PAYMENT_API_URL",
    "http://payment-api:8000"
)



# HEALTH

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "order-api"
    }



# CREATE ORDER

@app.post("/orders")
async def create_order():

    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        "create-order-db-save"
    ):
        pass

    async with httpx.AsyncClient() as client:

        try:

            response = await client.post(
                f"{PAYMENT_API_URL}/pay",
                timeout=5.0
            )


            # Sans cette ligne, un HTTP 500 de payment-api
            # n'est PAS considéré comme une exception par httpx.
            #
            # Donc order-api aurait continué et aurait retourné
            # HTTP 200.

            response.raise_for_status()

            return {
                "order_status": "created",
                "payment": response.json()
            }

        except httpx.HTTPStatusError as e:

            raise HTTPException(
                status_code=e.response.status_code,
                detail="Payment failed"
            )

        except httpx.RequestError as e:

            raise HTTPException(
                status_code=503,
                detail=f"Payment service unavailable: {str(e)}"
            )
