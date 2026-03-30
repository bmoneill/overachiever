FROM python:3.14-slim AS base

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/
COPY helpers/ helpers/
COPY static/ static/

RUN mkdir -p /app/data && chown app:app /app/data

USER app

EXPOSE 5000

ENV FLASK_APP=app.py
ENV DATABASE=/app/data/overachiever.db

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]
