FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app
RUN pip install --no-cache-dir "poetry>=2.0"

COPY pyproject.toml poetry.lock* README.md ./
RUN poetry install --only main --no-root

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN poetry install --only main

EXPOSE 8000
CMD ["uvicorn", "ouroboros.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
