FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY kaskade kaskade
COPY api api
COPY demo demo
COPY config config
COPY migrations migrations
COPY workflows workflows
RUN pip install --no-cache-dir -e .
EXPOSE 8080
