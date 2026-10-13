FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY . /app
RUN uv sync --locked --no-dev

EXPOSE 8000
CMD ["uvicorn", "shopmate_agent.stream_api:app", "--host", "0.0.0.0", "--port", "8000"]
