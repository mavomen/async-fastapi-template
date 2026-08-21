FROM python:3.12-slim

# NB: python:3.12-slim already ships a system group named "operator" (gid 37),
# so the runtime user gets a distinct name.
RUN groupadd --gid 1000 fastapi-op \
    && useradd --uid 1000 --gid fastapi-op --create-home fastapi-op

WORKDIR /operator

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY handlers.py .

USER 1000:1000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:27020/healthz', timeout=4)" || exit 1

CMD ["kopf", "run", "/operator/handlers.py", "--all-namespaces", "--liveness=http://0.0.0.0:27020/healthz"]
