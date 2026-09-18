# Observability Lab (Grafana, Prometheus, OpenTelemetry, Loki, Tempo, Alertmanager, Promtail) in Docker

A containerized microservices architecture (Python FastAPI: API Gateway ➔ Order API ➔ Payment API) implementing a complete observability stack using Grafana, Prometheus, OpenTelemetry, Loki, Tempo, Alertmanager, and Promtail, featuring cross-signal correlation via Prometheus Exemplars and trace ID log injection.

## How to Run

```bash
docker compose up --build -d
```
## How to Use

1.Generate Traffic

```bash
# Using the provided script
bash req.bash

# Or manually via curl
curl -X POST http://localhost:8080/checkout
```

2. Access UIs & Dashboards

- Grafana: http://localhost:3000 (User: admin, Password: admin)

- Prometheus: http://localhost:9090

- API Gateway Health: http://localhost:8080/health

