FROM python:3.14-slim
LABEL authors="darcin-biganiro"

WORKDIR /app

# libffi-dev required by argon2-cffi
#libpq-dev required by asyncpg/psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

EXPOSE 8002

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]