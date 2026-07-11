# Scheduler do TinyAI Box — build multi-stage para ARMv7
# Build: docker buildx build --platform linux/arm/v7 -t tinyai/scheduler .

# --- estágio 1: instalar dependências em um venv -----------------------------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

# --- estágio 2: imagem final enxuta ------------------------------------------
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /venv /venv
COPY scheduler/ ./scheduler/
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/saude').raise_for_status()"

CMD ["uvicorn", "scheduler.api:app", "--host", "0.0.0.0", "--port", "8000"]
