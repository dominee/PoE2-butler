FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1

RUN pip install --no-cache-dir "uv>=0.4"

WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --system .

COPY app ./admin/app

EXPOSE 8001
CMD ["uvicorn", "admin.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
