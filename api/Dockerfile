# HumanAPI task service
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres --extra chain --extra redis
COPY humanapi_api ./humanapi_api
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --extra postgres --extra chain --extra redis \
 && useradd --system --uid 10001 app && mkdir -p /data && chown -R app /app /data
USER app
ENV HA_HOST=0.0.0.0 HA_PORT=8400
EXPOSE 8400
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/stats' % os.environ.get('PORT', os.environ['HA_PORT']), timeout=4)" || exit 1
# Hosts such as Render pass the port as PORT. Tables are created or upgraded on every start.
CMD ["sh", "-c", "HA_PORT=${PORT:-$HA_PORT} && export HA_PORT && .venv/bin/alembic upgrade head && exec .venv/bin/humanapi-api"]
