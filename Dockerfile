# SIH26153 — AI-Based Network Attack Forecasting (Counterfactual Cyber World Model)
# Multi-stage Dockerfile: dev + production
# ============================================================

# ── Base stage (shared) ─────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Development stage ───────────────────────────────────────
FROM base AS development

RUN pip install --no-cache-dir ruff mypy gunicorn

COPY . .
RUN mkdir -p /app/data

EXPOSE 5000
CMD ["python", "run.py", "--no-pipeline"]

# ── Production stage ────────────────────────────────────────
FROM base AS production

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

COPY netwatch/ /app/netwatch/
COPY data/ /app/data/
COPY run.py /app/
COPY requirements.txt /app/
COPY docs/ /app/docs/

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/dashboard')" || exit 1

CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "netwatch.dashboard.app:app"]
