FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
	gcc \
	postgresql-client \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.2

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
	&& poetry install --no-interaction --no-ansi --only main

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
	postgresql-client \
	&& rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
