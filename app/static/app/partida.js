"use strict";
// Mesa multijugador: recibe su vista por WebSocket (app/consumers.py) y envía acciones por POST.

const raiz = document.getElementById("mesa");
const { ws: URL_WS, urlAccion: URL_ACCION, salir: URL_SALIR, csrf: CSRF } = raiz.dataset;
const CAMPO = new Set(["campo", "tierras"]);
const NOMBRE = { biblioteca: "Biblioteca", mano: "Mano", campo: "Campo de batalla", tierras: "Tierras",
                 cementerio: "Cementerio", exilio: "Exilio", mando: "Zona de mando", pila: "Pila" };

let mesa = null, version = -1, porId = {}, dialogo = null, arrastrando = false;
const FONDOS = JSON.parse(document.getElementById("fondos").textContent);  // id de usuario → arte para su zona
let finTurno = 0, tiempoPedido = null;  // finTurno: en el reloj local (performance.now), para no depender de la hora del PC
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

// --- Comunicación -----------------------------------------------------------

async function accion(datos, silencioso = false) {
  const r = await fetch(URL_ACCION, {
    method: "POST", body: JSON.stringify(datos),
    headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
  });
  let d;
  try { d = await r.json(); } catch { d = { error: "Error del servidor." }; }
  if (!r.ok) { if (!silencioso) aviso(d.error || "Error."); return null; }
  recibir(d);
  if (d.vistazo) { dialogo = { tipo: "vistazo", cartas: d.vistazo }; renderDialogo(); }
  return d;
}

function recibir(d) {
  if (d.version <= version) return;  // la respuesta del POST y el aviso del WebSocket traen la misma versión
  version = d.version;
  if (d.mesa) {
    mesa = d.mesa;
    finTurno = performance.now() + mesa.restante * 1000;
    if (!arrastrando) render();
  }
}

function conectar() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${URL_WS}`);
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.eliminada) return location.assign(URL_SALIR);
    recibir(d);
  };
  ws.onclose = () => setTimeout(conectar, 2000);  // al reconectar, el servidor reenvía el estado completo
}

function aviso(texto) {
  const el = $("#aviso");
  el.textContent = texto;
  el.hidden = false;
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => (el.hidden = true), 3500);
}

// --- Pintado ----------------------------------------------------------------

function htmlCarta(c, zona, j) {
  porId[c.id] = { c, zona, j };
  const clases = ["carta", c.girada && "girada", c.boca_abajo && "boca-abajo", c.ficha && "ficha"].filter(Boolean);
  const cara = c.oculta ? `<div class="dorso"></div>`
    : c.imagen ? `<img src="${esc(c.imagen)}" alt="${esc(c.nombre)}" draggable="false" loading="lazy" onerror="sinImagen(this)">`
    : `<div class="texto">${esc(c.nombre)}</div>`;
  const chips = Object.entries(c.contadores || {}).map(([t, n]) => [`${t} ×${n}`]);
  if (c.comandante && c.impuesto) chips.push([`impuesto +${c.impuesto}`]);
  if (c.boca_abajo) chips.push(["boca abajo"]);
  if (c.dueno !== j && CAMPO.has(zona)) chips.push([`de ${mesa.jugadores[c.dueno].nombre}`]);
  const html = chips.map(([t], k) => `<span class="chip" style="top:${2 + k * 15}px">${esc(t)}</span>`).join("");
  const titulo = c.oculta ? "Carta boca abajo" : c.nombre;
  return `<div class="${clases.join(" ")}" draggable="true" data-id="${c.id}" title="${esc(titulo)}">${cara}${html}</div>`;
}

const cartas = (lista, zona, j) => lista.map(c => htmlCarta(c, zona, j)).join("");

// Si una imagen no carga (p. ej. Scryfall retiró el id de esa impresión), se pide otra vez a Scryfall por el nombre;
// si tampoco carga, se muestra el nombre de la carta.
function sinImagen(img) {
  if (!img.dataset.porNombre) {
    img.dataset.porNombre = "1";
    img.src = `https://api.scryfall.com/cards/named?fuzzy=${encodeURIComponent(img.alt)}&format=image&version=normal`;
    return;
  }
  img.replaceWith(Object.assign(document.createElement("div"), { className: "texto", textContent: img.alt }));
}

function htmlJugador(p, i) {
  const z = p.zonas, propio = i === mesa.yo;
  const boton = (stat, delta, txt, extra = "") =>
    `<button data-stat="${stat}" data-jugador="${i}" data-delta="${delta}" ${extra} aria-label="${stat} ${delta}">${txt}</button>`;
  // Valor del contador más los clics que aún no se enviaron (ver sumarStat).
  const valor = (stat, n, carta = "") => n + (pendiente.get(`${stat}|${i}|${carta}`) || 0);
  const pila = (zona, contenido) =>
    `<div class="zona pila" data-zona="${zona}" data-jugador="${i}" title="${NOMBRE[zona]}">${contenido}</div>`;
  // El cementerio y el exilio vacíos muestran un hueco: siguen siendo visibles para soltar cartas.
  const tope = zona => z[zona].length ? htmlCarta(z[zona].at(-1), zona, i) : `<div class="hueco"></div>`;
  // Daño recibido de cada comandante rival (por comandante, así los compañeros cuentan por separado).
  const rivales = mesa.comandantes.filter(c => c.dueno !== i);
  const cmdr = !mesa.dano_comandante || !rivales.length ? "" : `<span class="cmdr">Daño de comandante: ${rivales.map(c => {
    const n = valor("dano_comandante", p.dano_comandante[c.id] || 0, c.id);
    return `<span class="${n >= mesa.dano_letal ? "letal" : ""}" title="De ${esc(mesa.jugadores[c.dueno].nombre)}">${esc(c.nombre)}
      ${boton("dano_comandante", -1, "−", `data-carta="${c.id}"`)}<b>${n}</b>${boton("dano_comandante", 1, "+", `data-carta="${c.id}"`)}</span>`;
  }).join(" · ")}</span>`;
  return `
    <section class="jugador ${propio ? "propio" : ""} ${i === mesa.activo ? "activo" : ""} ${p.rindio ? "rindio" : ""}
      ${FONDOS[p.id] ? "con-fondo" : ""}" ${FONDOS[p.id] ? `style="--fondo: url('${esc(FONDOS[p.id])}')"` : ""}>
      <header>
        <strong>${esc(p.nombre)}${p.rindio ? " (se rindió)" : ""}</strong>
        ${i === mesa.prioridad && !mesa.preparacion ? `<span class="prio">✋ prioridad</span>` : ""}
        <span>♥ ${boton("vida", -1, "−")}<b>${valor("vida", p.vida)}</b>${boton("vida", 1, "+")}</span>
        <span>☠ ${boton("veneno", -1, "−")}<b>${valor("veneno", p.veneno)}</b>${boton("veneno", 1, "+")}</span>
        ${propio ? "" : `<span>✋ ${z.mano}</span>`}
        <span>📚 ${z.biblioteca}</span>
        ${p.mulligans ? `<span>Mulligans: ${p.mulligans}</span>` : ""}
        ${cmdr}
      </header>
      <div class="cuerpo">
        <div class="zona mando" data-zona="mando" data-jugador="${i}"><h4>Mando</h4><div class="cartas">${cartas(z.mando, "mando", i)}</div></div>
        <div class="zona campo" data-zona="campo" data-jugador="${i}"><h4>Campo de batalla</h4><div class="cartas">${cartas(z.campo, "campo", i)}</div></div>
        <div class="zona tierras" data-zona="tierras" data-jugador="${i}"><h4>Tierras</h4><div class="cartas">${cartas(z.tierras, "tierras", i)}</div></div>
        <div class="pilas">
          ${pila("biblioteca", `<div class="dorso"></div><span class="n">📚 ${z.biblioteca}</span>`)}
          ${pila("cementerio", `${tope("cementerio")}<span class="n">🪦 ${z.cementerio.length}</span>`)}
          ${pila("exilio", `${tope("exilio")}<span class="n">⛔ ${z.exilio.length}</span>`)}
        </div>
      </div>
    </section>`;
}

function render() {
  porId = {};
  const yo = mesa.yo, mio = mesa.jugadores[yo];
  $("#rivales").innerHTML = mesa.jugadores.map((p, i) => i === yo ? "" : htmlJugador(p, i)).join("");
  $("#propio").innerHTML = htmlJugador(mio, yo);
  const mano = $("#mano");
  mano.dataset.zona = "mano";
  mano.dataset.jugador = yo;
  mano.innerHTML = `<h4>Mano (${mio.zonas.mano.length})</h4><div class="cartas">${cartas(mio.zonas.mano, "mano", yo)}</div>`;
  renderLateral();
  renderDialogo();
}

function renderLateral() {
  const vivo = mesa.ganador === null && !mesa.jugadores[mesa.yo].rindio;
  const tengo = vivo && (mesa.prioridad === mesa.yo || mesa.preparacion);
  const miTurno = tengo && mesa.activo === mesa.yo;
  $("#info").innerHTML = mesa.ganador !== null
    ? `<p class="ganador">🏆 Ganó ${esc(mesa.jugadores[mesa.ganador].nombre)}</p> <a href="${URL_SALIR}">Volver</a>`
    : `<p>Turno ${mesa.turno} · juega <b>${esc(mesa.jugadores[mesa.activo].nombre)}</b>${mesa.formato ? ` · ${esc(mesa.formato)}` : ""}
       · <span id="reloj"></span></p>`;
  reloj();
  // Un solo botón. En la preparación cada jugador confirma «Empezar partida» (el turno 1 empieza cuando todos
  // confirman; pulsarlo otra vez cancela); después, el jugador activo lo usa para pasar el turno.
  const listo = mesa.listos.includes(mesa.yo);
  $("#pasar").disabled = mesa.preparacion ? !vivo : !miTurno;
  $("#pasar").innerHTML = `<strong>${!mesa.preparacion ? "Pasar turno" : listo ? "Listo ✓ (cancelar)" : "Empezar partida"}</strong>`;
  $("#pasar").title = mesa.preparacion ? "Cuando todos lo pulsen se cierran los mulligans y empieza el turno 1" : "";
  const vivos = mesa.jugadores.filter(p => !p.rindio);
  $("#prioridad").innerHTML = mesa.preparacion
    ? `Preparación: hagan sus mulligans. Listos ${mesa.listos.length}/${vivos.length}` +
      (mesa.listos.length ? `: <b>${mesa.listos.map(i => esc(mesa.jugadores[i].nombre)).join(", ")}</b>` : "")
    : `Prioridad: <b>${esc(mesa.jugadores[mesa.prioridad].nombre)}</b>`;
  // La pila se muestra con la carta de arriba primero.
  $("#pila").dataset.jugador = mesa.yo;
  $("#pila").innerHTML = mesa.pila.slice().reverse().map(c => htmlCarta(c, "pila", c.controlador)).join("");
  $("#responder").hidden = !vivo || tengo;
  $("#pasar-prioridad").hidden = !vivo || mesa.preparacion || mesa.prioridad !== mesa.yo || mesa.activo === mesa.yo;
  for (const b of document.querySelectorAll(".botones button:not([data-accion=rendirse])")) b.disabled = !tengo;
  $('[data-accion="mulligan"]').hidden = !mesa.preparacion;  // solo antes de empezar
  const log = $("#log");
  const alFinal = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
  log.innerHTML = mesa.log.map(l =>
    `<li${l.carta?.imagen ? ` data-img="${esc(l.carta.imagen)}"` : ""}>${esc(l.t)}</li>`).join("");
  if (alFinal) log.scrollTop = log.scrollHeight;
}

// Cuenta atrás del turno. Al llegar a cero cualquier jugador avisa; el servidor comprueba el tiempo y pasa el turno.
function reloj() {
  const el = $("#reloj");
  if (!mesa || !el) return;
  // Con algo en la pila el servidor detiene el reloj: se muestra congelado.
  const s = mesa.pausado ? mesa.restante : Math.max(0, Math.ceil((finTurno - performance.now()) / 1000));
  el.textContent = `${mesa.pausado ? "⏸" : "⏱"} ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  el.title = mesa.pausado ? "Tiempo detenido hasta que se resuelva la pila" : "";
  el.classList.toggle("prio", s <= 60 && !mesa.pausado);
  if (s === 0 && !mesa.pausado && tiempoPedido !== mesa.turno) {
    tiempoPedido = mesa.turno;
    accion({ accion: "tiempo" }, true).then(d => { if (!d) setTimeout(() => (tiempoPedido = null), 3000); });
  }
}
setInterval(reloj, 1000);

function renderDialogo() {
  const dlg = $("#dialogo");
  if (!dialogo) { if (dlg.open) dlg.close(); return; }
  let titulo, html, pie = "";
  if (dialogo.tipo === "zona") {
    const p = mesa.jugadores[dialogo.jugador];
    titulo = `${NOMBRE[dialogo.zona]} de ${p.nombre}`;
    html = cartas(p.zonas[dialogo.zona], dialogo.zona, dialogo.jugador);
  } else if (dialogo.tipo === "oraculo") {
    titulo = dialogo.nombre;
    html = dialogo.html;
  } else {
    titulo = `Tu biblioteca: ${dialogo.cartas.length} carta(s) a la vista (la primera es la de arriba)`;
    html = cartas(dialogo.cartas, "biblioteca", mesa.yo);
    pie = `<button data-accion="barajar">Barajar biblioteca</button> Clic derecho o arrastrar para mover cada carta.`;
  }
  $("#dialogo-titulo").textContent = titulo;
  $("#dialogo-cartas").innerHTML = html || "<p>Vacío.</p>";
  $("#dialogo-pie").innerHTML = pie;
  if (!dlg.open) dlg.show();
}

// Tras mover una carta que estaba en el vistazo de la biblioteca, sale de la lista.
function sacarDelVistazo(id) {
  if (dialogo?.tipo !== "vistazo") return;
  dialogo.cartas = dialogo.cartas.filter(c => c.id !== id);
  renderDialogo();
}

async function mover(id, zona, extra = {}) {
  const d = await accion({ accion: "mover", carta: id, zona, ...extra });
  if (d) sacarDelVistazo(id);
  return d;
}

// Texto Oracle y rulings oficiales desde la API pública de Scryfall.
async function verOraculo(nombre) {
  dialogo = { tipo: "oraculo", nombre, html: "<p>Buscando en Scryfall…</p>" };
  renderDialogo();
  let html;
  try {
    const r = await fetch(`https://api.scryfall.com/cards/named?fuzzy=${encodeURIComponent(nombre)}`);
    const c = await r.json();
    if (!r.ok) throw new Error(c.details || "No se encontró la carta.");
    const rulings = (await (await fetch(c.rulings_uri)).json()).data;
    const caras = (c.card_faces || [c]).map(f => `
      <h4>${esc(f.name)} <span class="coste">${esc(f.mana_cost || "")}</span></h4>
      <p class="tipo">${esc(f.type_line || c.type_line)}</p>
      <p class="texto-oracle">${esc(f.oracle_text || "")}</p>
      ${f.power ? `<p><b>${esc(f.power)}/${esc(f.toughness)}</b></p>` : ""}${f.loyalty ? `<p>Lealtad: <b>${esc(f.loyalty)}</b></p>` : ""}`).join("");
    const imagen = c.image_uris?.normal || c.card_faces?.[0]?.image_uris?.normal;
    html = `<div class="oraculo">${imagen ? `<img src="${esc(imagen)}" alt="${esc(c.name)}">` : ""}<div>${caras}
      <h4>Rulings</h4>${rulings.length ? `<ul class="rulings">${rulings.map(x =>
        `<li><time>${esc(x.published_at)}</time> ${esc(x.comment)}</li>`).join("")}</ul>` : "<p>Sin rulings oficiales.</p>"}
      <p><a href="${esc(c.scryfall_uri)}" target="_blank" rel="noopener">Ver en Scryfall →</a></p></div></div>`;
  } catch (err) {
    html = `<p>${esc(err.message || "No se pudo consultar Scryfall.")}</p>`;
  }
  if (dialogo?.tipo === "oraculo" && dialogo.nombre === nombre) { dialogo.html = html; renderDialogo(); }
}

// Contadores (vida, veneno, daño de comandante): el número cambia al instante y los clics seguidos se envían juntos.
// Así no se pierden clics rápidos aunque la mesa se repinte entre medio.
const pendiente = new Map();  // "stat|jugador|carta" → delta sin enviar
let envioStats;

function sumarStat(b) {
  const { stat, jugador, carta = "", delta } = b.dataset;
  const clave = `${stat}|${jugador}|${carta}`;
  pendiente.set(clave, (pendiente.get(clave) || 0) + +delta);
  const n = b.parentElement.querySelector("b");
  n.textContent = +n.textContent + +delta;
  clearTimeout(envioStats);
  envioStats = setTimeout(enviarStats, 350);
}

async function enviarStats() {
  for (const [clave, delta] of [...pendiente]) {
    pendiente.delete(clave);
    const [stat, jugador, carta] = clave.split("|");
    if (delta) await accion({ accion: stat, jugador: +jugador, delta, ...(carta && { carta }) });
  }
}

// --- Acciones de botones y menús -------------------------------------------

function pedirN(texto, f, porDefecto = 1) {
  const n = parseInt(prompt(texto, porDefecto), 10);
  if (n > 0) f(n);
}

const BOTONES = {
  pasar_turno: () => accion({ accion: mesa.preparacion ? "listo" : "pasar_turno" }),
  responder: () => accion({ accion: "responder" }),
  pasar_prioridad: () => accion({ accion: "pasar_prioridad" }),
  robar: () => accion({ accion: "robar" }),
  robar_n: () => pedirN("¿Cuántas cartas robar?", n => accion({ accion: "robar", n })),
  enderezar: () => accion({ accion: "enderezar" }),
  barajar: () => { if (dialogo?.tipo === "vistazo") dialogo = null; accion({ accion: "barajar" }); },
  mulligan: () => confirm("¿Hacer mulligan? Vuelves a robar 7.") && accion({ accion: "mulligan" }),
  mirar: () => pedirN("¿Cuántas cartas de arriba quieres mirar?", n => accion({ accion: "mirar", n })),
  buscar: () => accion({ accion: "mirar", n: 0 }),
  moler: () => pedirN("¿Cuántas cartas poner en el cementerio?", n => accion({ accion: "moler", n })),
  revelar_mano: () => accion({ accion: "revelar_mano" }),
  ficha: () => {
    const nombre = prompt("Nombre de la ficha (ej. Goblin 1/1 rojo):");
    if (nombre) pedirN("¿Cuántas?", cantidad => accion({ accion: "ficha", nombre, cantidad }));
  },
  dado: () => pedirN("¿Cuántas caras?", caras => accion({ accion: "dado", caras }), 20),
  moneda: () => accion({ accion: "moneda" }),
  rendirse: () => confirm("¿Seguro que quieres rendirte?") && accion({ accion: "rendirse" }),
};

function opcionesCarta({ c, zona, j }) {
  const yo = mesa.yo, id = c.id, ops = [];
  const hacer = (nombre, extra = {}) => () => accion({ accion: nombre, carta: id, ...extra });
  const otroContador = () => {
    const tipo = prompt("Tipo de contador (ej. carga, lealtad, tiempo):");
    if (tipo) accion({ accion: "contador", carta: id, tipo, delta: 1 });
  };
  if (CAMPO.has(zona)) {
    ops.push([c.girada ? "Enderezar" : "Girar", hacer("girar")]);
    if (c.reverso) ops.push(["Transformar", hacer("voltear")]);
    ops.push([c.boca_abajo || c.oculta ? "Poner boca arriba" : "Poner boca abajo", hacer("boca_abajo")]);
    ops.push(["Contador +1/+1", hacer("contador", { tipo: "+1/+1", delta: 1 })]);
    ops.push(["Contador −1/−1", hacer("contador", { tipo: "-1/-1", delta: 1 })]);
    ops.push(["Otro contador…", otroContador]);
    if (!c.oculta) ops.push(["Crear ficha copia", hacer("copiar")]);
    mesa.jugadores.forEach((o, k) => {
      if (k !== j && !o.rindio) ops.push([`Dar el control a ${o.nombre}`, () => mover(id, zona, { jugador: k })]);
    });
  } else if (zona === "mano") {
    if (c.tierra) ops.push(["Jugar", () => mover(id, "tierras", { jugador: yo })]);
    else ops.push(["Lanzar (a la pila)", () => mover(id, "pila")], ["Poner en el campo", () => mover(id, "campo", { jugador: yo })]);
    ops.push(["Jugar boca abajo (transfigurar, disfrazar…)", () => mover(id, "campo", { jugador: yo, boca_abajo: true })]);
    ops.push(["Exiliar boca abajo (presagio…)", () => mover(id, "exilio", { boca_abajo: true })]);
    ops.push(["Revelar", hacer("revelar")]);
  } else if (zona === "pila") {
    ops.push(["Resolver (al campo)", () => mover(id, c.tierra ? "tierras" : "campo", { jugador: j })]);
  } else if (zona === "biblioteca") {
    ops.push(["Al campo boca abajo (manifestar…)", () => mover(id, "campo", { jugador: yo, boca_abajo: true })]);
    ops.push(["Exiliar boca abajo", () => mover(id, "exilio", { boca_abajo: true })]);
  } else {
    if (zona === "exilio") ops.push([c.boca_abajo || c.oculta ? "Poner boca arriba" : "Poner boca abajo", hacer("boca_abajo")]);
    ops.push(["Añadir contador…", otroContador]);
  }
  if (!c.oculta) ops.push(["Oracle y rulings", () => verOraculo(c.nombre)]);
  for (const t of Object.keys(c.contadores || {})) ops.push([`Quitar un contador ${t}`, hacer("contador", { tipo: t, delta: -1 })]);
  ops.push(null);
  for (const destino of ["pila", "mano", "campo", "tierras", "cementerio", "exilio", "mando"]) {
    if (destino === zona) continue;
    const jugador = CAMPO.has(destino) ? (CAMPO.has(zona) || zona === "pila" ? j : yo) : undefined;
    ops.push([`→ ${NOMBRE[destino]}`, () => mover(id, destino, { jugador })]);
  }
  ops.push(["→ Biblioteca (arriba)", () => mover(id, "biblioteca")]);
  ops.push(["→ Biblioteca (fondo)", () => mover(id, "biblioteca", { posicion: "abajo" })]);
  return ops;
}

function opcionesBiblioteca() {
  return [["Robar", BOTONES.robar], ["Robar varias…", BOTONES.robar_n], ["Mirar arriba…", BOTONES.mirar],
          ["Buscar en la biblioteca", BOTONES.buscar], ["Moler…", BOTONES.moler], null,
          ["Barajar", BOTONES.barajar], ...(mesa.preparacion ? [["Mulligan", BOTONES.mulligan]] : [])];
}

function abrirMenu(ops, x, y) {
  const menu = $("#menu");
  menu.replaceChildren(...ops.map(op => {
    if (!op) return document.createElement("hr");
    const b = document.createElement("button");
    b.textContent = op[0];
    b.onclick = () => { cerrarMenu(); op[1](); };
    return b;
  }));
  menu.hidden = false;
  menu.style.left = Math.min(x, innerWidth - menu.offsetWidth - 8) + "px";
  menu.style.top = Math.min(y, innerHeight - menu.offsetHeight - 8) + "px";
}

function cerrarMenu() { $("#menu").hidden = true; }

// --- Eventos ----------------------------------------------------------------

document.addEventListener("click", e => {
  if (!e.target.closest("#menu")) cerrarMenu();
  const boton = e.target.closest("[data-accion]");
  if (boton) return BOTONES[boton.dataset.accion]?.();
  const stat = e.target.closest("[data-stat]");
  if (stat) { if (e.detail === 0) sumarStat(stat); return; }  // con ratón ya se sumó en pointerdown; esto es teclado
  const pila = e.target.closest(".pila");
  if (pila && pila.dataset.zona !== "biblioteca") {
    dialogo = { tipo: "zona", jugador: +pila.dataset.jugador, zona: pila.dataset.zona };
    renderDialogo();
  }
});

// Los contadores responden al presionar (no al soltar): si la mesa se repinta entre medio, el clic no se pierde.
document.addEventListener("pointerdown", e => {
  const stat = e.button === 0 && e.target.closest("[data-stat]");
  if (stat) { e.preventDefault(); sumarStat(stat); }
});

// Doble clic: en la mano lanza (tierras: juega), en el campo gira o endereza, en tu biblioteca roba.
document.addEventListener("dblclick", e => {
  const carta = e.target.closest(".carta"), info = carta && porId[carta.dataset.id];
  if (info?.zona === "mano") return info.c.tierra ? mover(info.c.id, "tierras", { jugador: mesa.yo }) : mover(info.c.id, "pila");
  if (info && CAMPO.has(info.zona)) return accion({ accion: "girar", carta: info.c.id });
  const biblioteca = e.target.closest('.pila[data-zona="biblioteca"]');
  if (biblioteca && +biblioteca.dataset.jugador === mesa.yo) BOTONES.robar();
});

// Atajos con el ratón sobre una carta (R roba sin necesidad de carta).
let sobre = null;  // id de la carta bajo el ratón
const ATAJOS = {
  t: ({ c, zona }) => CAMPO.has(zona) && accion({ accion: "girar", carta: c.id }),
  c: ({ c }) => mover(c.id, "cementerio"),
  e: ({ c }) => mover(c.id, "exilio"),
  m: ({ c }) => mover(c.id, "mano"),
  p: ({ c }) => mover(c.id, "pila"),
  b: ({ c, zona }) => zona === "mano" || zona === "biblioteca"
    ? mover(c.id, "campo", { jugador: mesa.yo, boca_abajo: true })
    : accion({ accion: "boca_abajo", carta: c.id }),
  o: ({ c }) => !c.oculta && verOraculo(c.nombre),
};

document.addEventListener("contextmenu", e => {
  const carta = e.target.closest(".carta"), info = carta && porId[carta.dataset.id];
  const biblioteca = e.target.closest('.pila[data-zona="biblioteca"]');
  const ops = info ? opcionesCarta(info)
    : biblioteca && +biblioteca.dataset.jugador === mesa.yo ? opcionesBiblioteca() : null;
  if (!ops) return;
  e.preventDefault();
  abrirMenu(ops, e.clientX, e.clientY);
});

document.addEventListener("dragstart", e => {
  const carta = e.target.closest(".carta");
  if (!carta) return;
  arrastrando = true;
  e.dataTransfer.setData("text/plain", carta.dataset.id);
  $("#vista").hidden = true;
});
document.addEventListener("dragend", () => { arrastrando = false; if (mesa) render(); });
document.addEventListener("dragover", e => { if (e.target.closest(".zona")) e.preventDefault(); });
document.addEventListener("drop", e => {
  const zona = e.target.closest(".zona");
  const id = e.dataTransfer.getData("text/plain"), info = porId[id];
  if (!zona || !info) return;
  e.preventDefault();
  const destino = zona.dataset.zona, j = +zona.dataset.jugador;
  if (destino === info.zona && j === info.j) return;
  mover(id, destino, { jugador: j, posicion: e.shiftKey ? "abajo" : "arriba" });
});

document.addEventListener("mouseover", e => {
  sobre = e.target.closest(".carta")?.dataset.id ?? null;
  const vista = $("#vista");
  const img = e.target.closest(".carta")?.querySelector("img")?.src || e.target.closest("#log li")?.dataset.img;
  vista.hidden = !img;
  if (img && vista.src !== img) vista.src = img;
});

$("#dialogo-cerrar").onclick = () => { dialogo = null; renderDialogo(); };
$("#chat").onsubmit = e => {
  e.preventDefault();
  const input = e.target.texto;
  if (input.value.trim()) accion({ accion: "chat", texto: input.value });
  input.value = "";
};
$("#oraculo").onsubmit = e => {
  e.preventDefault();
  const nombre = e.target.carta.value.trim();
  if (nombre) verOraculo(nombre);
};
document.addEventListener("keydown", e => {
  if (e.key === "Escape") return cerrarMenu();
  if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || e.target.closest("input, textarea, select")) return;
  const k = e.key.toLowerCase(), info = sobre && porId[sobre];
  if (k === "r") return BOTONES.robar();
  if (info && ATAJOS[k]) { e.preventDefault(); ATAJOS[k](info); }
});

conectar();
