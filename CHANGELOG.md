# Changelog

Todos los cambios importantes del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y las versiones usan [versionado semántico](https://semver.org/lang/es/).

## [0.1.2] - 2026-10-07

### Cambiado

- **La sección «Versiones» de la portada** muestra el historial de cambios del sitio, con la versión más reciente
  abierta y las anteriores plegadas.

### Eliminado

- Publicar versiones desde el panel de administración.

## [0.1.1] - 2026-10-07

### Añadido

- **Prioridad en las partidas multijugador.** Durante el turno de un jugador, solo él puede actuar. Los demás tienen
  que pulsar **Responder** para tomar la prioridad y **Pasar prioridad** para devolverla. Las respuestas se pueden
  encadenar (responder a una respuesta). El jugador con prioridad se marca con «✋ prioridad».
- **Pila de hechizos.** Zona compartida en el panel lateral. Las cartas se lanzan a la pila (doble clic, menú o
  arrastrar) y se resuelven de arriba abajo. Al resolver, la carta va al campo de quien la lanzó. No se puede pasar
  el turno con la pila llena.
- **Fase de preparación.** Al empezar la partida, todos los jugadores pueden hacer sus mulligans a la vez hasta que
  el primer jugador cambie de fase.
- **Tiempo de turno de 10 minutos**, con cuenta atrás en la mesa. Al agotarse, el turno pasa solo al siguiente
  jugador.
- **Notificaciones en la barra superior** (🔔): invitaciones a partidas y solicitudes de amistad, con un contador.
  Se pueden aceptar o rechazar desde ahí mismo.
- **Sección «Versiones» en la portada** con los últimos cambios del sitio.
- **Publicar versiones desde el panel de administración** (`/manage/`), con versión, título y notas.

### Cambiado

- **Tablero solo para PC.** En pantallas táctiles (móviles y tablets) el tablero de `/test/` y `/game/` se oculta y
  se muestra un aviso para jugar desde un PC o notebook.
- **Panel lateral de la partida reorganizado** en tres bloques: «Fases» (con **Pasar turno**), «Pila y prioridad»
  y «Acciones».
- En la mesa multijugador, el doble clic en una carta de la mano la lanza a la pila. Las tierras se siguen jugando
  directamente.
- El impuesto de comandante se cuenta al lanzar el comandante desde la zona de mando a la pila.

## [0.1.0] - 2026-10-07

Primera versión.

### Añadido

- **Cuentas:** registro con usuario, correo y contraseña; inicio de sesión en `/login/` y perfil en `/user/`.
- **Amigos:** búsqueda de usuarios, solicitudes de amistad y perfiles públicos.
- **Mazos:** importación desde enlaces públicos de Moxfield, vista organizada por tipo de carta, actualizar y
  eliminar.
- **Probar mazos** (`/test/`): mesa individual para robar, hacer mulligan y jugar turnos de prueba.
- **Jugar con amigos** (`/game/`):
  - Sala de espera con invitaciones (de 2 a 5 jugadores) y elección de mazo, guardado o por enlace de Moxfield.
  - Todos los mazos deben ser del formato del anfitrión.
  - Partida en tiempo real, con la información oculta protegida: nadie ve la mano ni la biblioteca de otro.
  - Turnos y fases, zonas, girar, transformar, boca abajo, contadores, fichas, cambio de control, mirar o buscar en
    la biblioteca.
  - Vida, veneno, daño de comandante (por comandante) e impuesto de comandante.
  - Dados, moneda, chat y registro de la partida.
- **Panel de administración** (`/manage/`), solo para superusuarios: estadísticas, activar y desactivar usuarios, y
  eliminar partidas.
- **Diseño «Grimorio»** y portada con cartas de ejemplo.

[0.1.2]: https://github.com/JavierGonzalez998/mg_sim/compare/2029abc...main
[0.1.1]: https://github.com/JavierGonzalez998/mg_sim/compare/c404f96...2029abc
[0.1.0]: https://github.com/JavierGonzalez998/mg_sim/commits/c404f96
