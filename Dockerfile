FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests
COPY pyproject.toml uv.lock ./
COPY larisin_pkg/pyproject.toml ./larisin_pkg/pyproject.toml

# Install all dependencies
RUN uv sync --frozen --no-dev

# Copy application source
COPY main.py ./
COPY larisin_pkg/ ./larisin_pkg/

# Expose the FastAPI port
EXPOSE 8000

# Run the app using the uv-managed venv
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
