FROM python:3.14-slim
LABEL authors="darcin-bigabiro"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer uv (gestionnaire de packages)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the dependency manifest
COPY pyproject.toml .

# Install the dependencies with uv in /app/.venv
RUN uv sync --no-dev

# Copy the source code
COPY . .

EXPOSE 8100

# Launch via uv run to use the venv managed by uv
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--reload"]