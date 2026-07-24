# Render deploy image. Same discipline as the reference project's 512MB
# survival kit: slim base, no build toolchain (psycopg ships a binary wheel),
# exactly one uvicorn worker.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Alembic ships in the image so you can `render ssh` / one-off job migrate,
# but migrations normally run from your machine (docs/RUNBOOK.md).
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Render injects $PORT. Single worker: stay well under the 512MB ceiling.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
