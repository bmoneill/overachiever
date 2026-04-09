#!/bin/bash

GUNICORN_WORKERS=2
GUNICORN_THREADS=4
export COMPRESSOR_WORKERS=4

python scripts/image_compressor.py &
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 --worker-class gthread src:app
