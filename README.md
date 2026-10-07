# MG Simulator

Simulador web de Magic: The Gathering para probar mazos de [Moxfield](https://moxfield.com) en solitario o jugar
partidas de 2 a 5 jugadores con amigos, en tiempo real.

## Funcionalidades

- **Cuentas:** registro con usuario, correo y contraseña; perfil; amigos con solicitudes de amistad.
- **Mazos:** importación desde un enlace público de Moxfield, vista organizada por tipo de carta, actualizar y eliminar.
- **Probar mazos** (`/test/`): mesa individual para robar, hacer mulligan y jugar turnos de prueba.
- **Jugar con amigos** (`/game/`): sala de espera con invitaciones, elección de mazo (guardado o por enlace) y partida
  en tiempo real por WebSocket. Todos los mazos deben ser del mismo formato que el del anfitrión.
  - La mesa no aplica las reglas (como una mesa real), pero sí protege la información oculta: nadie ve la mano ni la
    biblioteca de otro jugador.
  - Turnos y fases, mover cartas entre zonas, girar, transformar, boca abajo, contadores, fichas, cambio de control,
    mulligan, mirar o buscar en la biblioteca, vida, veneno, daño de comandante (por comandante), impuesto de
    comandante, dados, chat y registro de la partida.
- **Panel de administración** (`/manage/`): solo para superusuarios. Estadísticas, usuarios (activar y desactivar) y
  partidas activas. Además, los modelos están registrados en el admin de Django (`/admin/`).

## Tecnologías

| Parte | Tecnología |
|---|---|
| Backend | Django 6.1, Python 3.14 |
| Tiempo real | Django Channels + Daphne (ASGI), Redis en producción |
| Base de datos | SQLite en desarrollo, MySQL 8.4 en producción |
| Estilos | Tailwind CSS v4 compilado con su CLI (Node) |
| Producción | Docker Compose: nginx + Daphne + MySQL + Redis |

## Estructura

```
main/          Configuración del proyecto (settings, urls, asgi)
app/           Núcleo: mazos, importación de Moxfield, mesas de juego, partidas y WebSockets
  juego.py       Lógica de la mesa multijugador (estado, acciones, vista por jugador)
  consumers.py   WebSocket de las partidas
  static/app/    CSS compilado, JS de la mesa e imágenes
user/          Login, registro, perfiles y amigos
managements/   Panel de administración (/manage/)
tailwind/      Fuente del CSS (entrada.css)
docker/        Arranque del contenedor y configuración de nginx
```

## Desarrollo local

Requisitos: Python 3.14 y Node 24.

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt

npm install
npm run build:css              # o `npm run watch:css` mientras editas plantillas

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La app queda en http://127.0.0.1:8000. `runserver` usa Daphne, así que los WebSockets funcionan sin nada más.
Sin variables de entorno se usa SQLite, `DEBUG` activado y un canal de mensajes en memoria.

> Tailwind solo genera las clases que encuentra en las plantillas al compilar. Si agregas clases nuevas, vuelve a
> correr `npm run build:css` (o deja `watch:css` corriendo).

### Tests

```bash
python manage.py test
```

## Producción con Docker

```bash
cp .env.example .env           # y cambia todos los valores "CAMBIA-ESTO"
docker compose up -d --build
```

Se levantan cuatro servicios:

| Servicio | Qué hace |
|---|---|
| `proxy` | nginx: única entrada pública (puerto `PUERTO`, 80 por defecto). Sirve `/static/` y reenvía HTTP y WebSockets a `web`. |
| `web` | Daphne con Django. Al arrancar aplica migraciones y crea el superusuario de `.env` si no existe. |
| `db` | MySQL 8.4 (utf8mb4) con volumen persistente. |
| `redis` | Lleva los avisos de las partidas entre procesos. |

El `Dockerfile` tiene dos imágenes finales: `app` (Django) y `proxy` (nginx con los estáticos ya recolectados).

### Variables de entorno

Todas están documentadas en [`.env.example`](.env.example). Las principales:

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | Obligatoria en producción; sin ella la app no arranca. |
| `DJANGO_ALLOWED_HOSTS` | Dominios de la app, separados por comas (sin esquema). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Los mismos dominios con esquema, p. ej. `https://tudominio.com`. |
| `DJANGO_HTTPS` | `1` solo si los usuarios entran por `https://` (ver abajo). |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | Datos de MySQL. |
| `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | Superusuario inicial (opcional). |
| `EMAIL_HOST` y relacionadas | SMTP (opcional; la app aún no envía correos). |
| `PUERTO` | Puerto del host donde nginx publica la app. |

### HTTPS

nginx atiende HTTP. Para servir por HTTPS hay dos opciones:

- Terminar el HTTPS delante (Cloudflare, un balanceador...): funciona sin cambios, nginx respeta su
  `X-Forwarded-Proto`.
- Poner el certificado en nginx (por ejemplo, Let's Encrypt).

En ambos casos usa `DJANGO_HTTPS=1` y orígenes `https://` en `DJANGO_CSRF_TRUSTED_ORIGINS`. Si los usuarios entran por
`http://`, deja `DJANGO_HTTPS=0`: con `1` las cookies de sesión no se envían y no se puede iniciar sesión.

## Notas

- La importación usa la API **no oficial** de Moxfield (`api2.moxfield.com`); el mazo debe ser público. Si Moxfield la
  cambia o la bloquea, la importación dejará de funcionar.
- Las imágenes de las cartas vienen de Scryfall (`cards.scryfall.io`) y las de la portada, de Moxfield.
- Proyecto de fans, sin relación con Wizards of the Coast. Magic: The Gathering y sus cartas son propiedad de
  Wizards of the Coast.
