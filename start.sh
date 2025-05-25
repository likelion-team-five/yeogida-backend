#!/bin/bash

echo "Applying Django migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn server..."
exec gunicorn yeogida_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 3