FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY app ./app
RUN uv sync --no-dev

RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin mock \
    && chown -R mock:mock /app
USER mock

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
