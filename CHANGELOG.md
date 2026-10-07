# Changelog

Todos los cambios importantes del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y las versiones usan [versionado semántico](https://semver.org/lang/es/).

## [0.1.2] - 2026-10-07

### Añadido

- **Links de invitación:** el anfitrión copia un link desde la sala y lo comparte con quien quiera. Con cuenta, se
  entra con ella (y se pueden usar los mazos guardados); sin cuenta, se juega como **«Invitado 1»**, **«Invitado 2»**…
  (numerados dentro de cada partida) pegando el enlace de un mazo de Moxfield. Los invitados solo tienen acceso a su partida.
- **Fondo de tu zona en la mesa:** en tu perfil buscas una carta y eliges uno de sus artes; se usa como tapete de tu
  parte del tablero en las partidas con amigos, y los demás jugadores también lo ven. Solo para usuarios registrados.
- **Atajos de teclado** con el ratón sobre una carta: **T** girar o enderezar, **C** cementerio, **E** exilio,
  **M** mano, **P** pila, **B** boca abajo, **O** Oracle y rulings. **R** roba una carta.
- **Cartas boca abajo en el exilio** (presagio y similares): solo su dueño ve cuál es. También se puede poner una
  carta boca abajo en el campo desde la biblioteca (manifestar).
- **Oracle y rulings**: busca cualquier carta, o usa el menú de una carta, para ver su texto Oracle y sus rulings
  oficiales sin salir de la partida.

### Cambiado

- **Nueva disposición de la partida:** a la izquierda, el estado de la partida y las acciones; al centro, la mesa;
  a la derecha, el registro, el chat y la búsqueda de Oracle.
- **Tiempo de turno de 5 minutos**, y cada acción distinta suma 10 segundos. Repetir la misma acción (por ejemplo,
  girar varias veces la misma carta) no suma más, así que el turno termina pasando solo. El chat no suma tiempo.
- **Notificaciones en tiempo real:** las invitaciones a partidas y las solicitudes de amistad aparecen (y desaparecen)
  en la campana al momento, sin recargar la página.
- **Una partida a la vez:** quien está en una sala o partida, sea anfitrión o invitado, no puede crear otra hasta
  terminarla, rendirse o salir de la sala.
- **El tiempo se detiene mientras haya algo en la pila** (⏸) y sigue donde quedó cuando la pila se resuelve.
- **Sin botones de fase:** queda un solo botón. Al comienzo cada jugador pulsa «Empezar partida» cuando termina sus
  mulligans (se puede cancelar), y el turno 1 empieza cuando **todos** confirman. Después, el botón es «Pasar turno».
- **Doble clic** para girar o enderezar las cartas del campo y para robar de la biblioteca, igual que para lanzar
  desde la mano. Aplica también a la mesa de prueba.
- **El cementerio y el exilio se ven siempre**, aunque estén vacíos, para poder soltar cartas en ellos.
- **El Mulligan desaparece** al empezar la partida.
- **Los contadores de vida, veneno y daño de comandante** cambian al instante y no pierden clics seguidos.
- **La sección «Versiones» de la portada** muestra el historial de cambios del sitio, con la versión más reciente
  abierta y las anteriores plegadas.

### Eliminado

- Publicar versiones desde el panel de administración.

### Corregido

- En la partida multijugador vuelven a funcionar los clics en la mesa: los contadores de vida, veneno y daño de
  comandante, los botones de fase y abrir el cementerio o el exilio.
- La vida, el veneno y el daño de comandante se pueden anotar en el turno de otro jugador sin pulsar **Responder**.
- En ventanas estrechas, los datos de un rival ya no tapan los contadores propios.
- Los mensajes largos del chat hacen salto de línea en lugar de desbordar el registro; el máximo es de 255 caracteres.
- Las cartas cuya imagen no cargaba (por ejemplo, algunas tierras básicas) se buscan de nuevo por su nombre; si
  aun así no hay imagen, se muestra el nombre de la carta.

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
