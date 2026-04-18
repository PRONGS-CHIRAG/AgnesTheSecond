# Minimal backend image. Relies on the host-mounted workspace for source + data.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./

RUN uv pip install --system --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "sse-starlette>=2.1" \
    "pydantic>=2" \
    "pydantic-settings>=2" \
    "sqlalchemy>=2.0" \
    "pandas>=2" \
    "python-dotenv>=1" \
    "openai>=1.50" \
    "httpx>=0.27" \
    "aiohttp>=3.12" \
    "structlog>=24"

EXPOSE 8000

CMD ["uvicorn", "agnes.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
