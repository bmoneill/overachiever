FROM python:3.14-slim AS base

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env .
COPY scripts/ ./scripts/
COPY start.sh .

RUN mkdir -p /app/data && chown app:app /app/data

USER app

EXPOSE 5000

ENV FLASK_APP=/app/__main__.py
ENV DATABASE=/app/data/overachiever.db

CMD ["bash", "start.sh"]
