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

# 3) App (target "app"): Daphne con Django, sin compiladores.
FROM python:3.14-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 mg
WORKDIR /app
COPY --from=deps /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
COPY --from=css /app/app/static/app/estilos.css app/static/app/estilos.css
# collectstatic no toca la base de datos; la clave solo hace falta para cargar la configuración.
RUN DJANGO_SECRET_KEY=solo-para-collectstatic python manage.py collectstatic --noinput
USER mg
EXPOSE 8000
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
CMD ["daphne", "--bind", "0.0.0.0", "--port", "8000", "--proxy-headers", "main.asgi:application"]

# 4) Proxy (target "proxy"): nginx sirve /static/ ya recolectados y reenvía HTTP y WebSockets a "app".
FROM nginx:stable-alpine AS proxy
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=app /app/staticfiles /usr/share/nginx/static
