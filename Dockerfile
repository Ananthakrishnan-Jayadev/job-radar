# Job Radar for a home server: the web UI built with Node, then the Python app.
# Your data (database, backups) lives in ./data on the server, mounted at
# /app/data, so rebuilding the image never touches it. See deploy/README.md.

# --- 1. the web UI ------------------------------------------------------------
FROM node:22-slim AS ui
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Vite writes the built UI to ../jobradar/web/static.
RUN mkdir -p ../jobradar/web && npm run build

# --- 2. the app -----------------------------------------------------------------
FROM python:3.14-slim
# tzdata: dates on the Applications page are counted in local time (TZ in compose).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBRADAR_NO_APPLY=1
WORKDIR /app
COPY pyproject.toml config.toml roles.toml ./
COPY seeds ./seeds
COPY jobradar ./jobradar
COPY --from=ui /src/jobradar/web/static ./jobradar/web/static
# Editable install: the code (and the built UI) stays in /app/jobradar.
RUN pip install --no-cache-dir -e .
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/meta', timeout=4)"
CMD ["jobradar", "serve", "--host", "0.0.0.0", "--port", "8000"]
