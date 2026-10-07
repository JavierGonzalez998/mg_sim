#!/bin/sh
# Arranque del contenedor web: aplica migraciones, crea el superusuario si se pidió y lanza el servidor.
set -e

python manage.py migrate --noinput

# createsuperuser --noinput lee DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL y DJANGO_SUPERUSER_PASSWORD.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --noinput 2>/dev/null || echo "El superusuario $DJANGO_SUPERUSER_USERNAME ya existe."
fi

exec "$@"
