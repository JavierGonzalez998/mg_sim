# syntax=docker/dockerfile:1

# 1) CSS: compila Tailwind contra las plantillas actuales.
FROM node:24-slim AS css
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind ./tailwind
COPY app/templates ./app/templates
COPY user/templates ./user/templates
COPY managements/templates ./managements/templates
COPY app/static/app/partida.js ./app/static/app/partida.js
RUN npm run build:css

# 2) Dependencias de Python. mysqlclient se compila aquí, con las cabeceras de MySQL/MariaDB.
FROM python:3.14-slim AS deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-produccion.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-produccion.txt

# 3) Base de la app: dependencias, código y estáticos recolectados (lo comparten "proxy" y "app").
FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     DJANGO_DEBUG=0
RUN apt-get update     && apt-get install -y --no-install-recommends libmariadb3     && rm -rf /var/lib/apt/lists/*     && useradd --create-home --uid 1000 mg
WORKDIR /app
COPY --from=deps /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
COPY --from=css /app/app/static/app/estilos.css app/static/app/estilos.css
# collectstatic no toca la base de datos; la clave solo hace falta para cargar la configuración.
RUN DJANGO_SECRET_KEY=solo-para-collectstatic python manage.py collectstatic --noinput

# 4) Proxy (target "proxy", solo para docker compose): nginx sirve /static/ y reenvía HTTP y WebSockets a "web".
FROM nginx:stable-alpine AS proxy
# Toma los DNS del contenedor y genera conf.d/default.conf desde la plantilla al arrancar.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=base /app/staticfiles /usr/share/nginx/static

# 5) App (target "app"): Daphne con Django. Es la ÚLTIMA etapa a propósito: es la que construyen por
#    defecto las plataformas que despliegan un solo Dockerfile (Railway, Render, Fly...).
FROM base AS app
USER mg
EXPOSE 8000
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
# PORT lo define la plataforma (Railway); en docker compose no existe y se usa 8000.
CMD ["sh", "-c", "exec daphne --bind 0.0.0.0 --port ${PORT:-8000} --proxy-headers main.asgi:application"]
