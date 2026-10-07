"use strict";
// Mesa multijugador: recibe su vista por WebSocket (app/consumers.py) y envía acciones por POST.

const raiz = document.getElementById("mesa");
const { ws: URL_WS, accion: URL_ACCION, salir: URL_SALIR, csrf: CSRF } = raiz.dataset;
const CAMPO = new Set(["campo", "tierras"]);
const NOMBRE = { biblioteca: "Biblioteca", mano: "Mano", campo: "Campo de batalla", tierras: "Tierras",
                 cementerio: "Cementerio", exilio: "Exilio", mando: "Zona de mando" };
const FASES = [["comienzo", "Comienzo"], ["principal1", "Principal 1"], ["combate", "Combate"],
               ["principal2", "Principal 2"], ["final", "Final"]];

let mesa = null, version = -1, porId = {}, dialogo = null, arrastrando = false;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

// --- Comunicación -----------------------------------------------------------

async function accion(datos) {
  const r = await fetch(URL_ACCION, {
    method: "POST", body: JSON.stringify(datos),
    headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
  });
  let d;
  try { d = await r.json(); } catch { d = { error: "Error del servidor." }; }
  if (!r.ok) { aviso(d.error || "Error."); return null; }
  recibir(d);
  if (d.vistazo) { dialogo = { tipo: "vistazo", cartas: d.vistazo }; renderDialogo(); }
  return d;
}

function recibir(d) {
  if (d.version <= version) return;  // la respuesta del POST y el aviso del WebSocket traen la misma versión
  version = d.version;
  if (d.mesa) { mesa = d.mesa; if (!arrastrando) render(); }
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
    : c.imagen ? `<img src="${esc(c.imagen)}" alt="${esc(c.nombre)}" draggable="false">`
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

function htmlJugador(p, i) {
  const z = p.zonas, propio = i === mesa.yo;
  const boton = (stat, delta, txt, extra = "") =>
    `<button data-stat="${stat}" data-jugador="${i}" data-delta="${delta}" ${extra} aria-label="${stat} ${delta}">${txt}</button>`;
  const pila = (zona, contenido) =>
    `<div class="zona pila" data-zona="${zona}" data-jugador="${i}" title="${NOMBRE[zona]}">${contenido}</div>`;
  const tope = zona => z[zona].length ? htmlCarta(z[zona].at(-1), zona, i) : "";
  // Daño recibido de cada comandante rival (por comandante, así los compañeros cuentan por separado).
  const rivales = mesa.comandantes.filter(c => c.dueno !== i);
  const cmdr = !mesa.dano_comandante || !rivales.length ? "" : `<span class="cmdr">Daño de comandante: ${rivales.map(c => {
    const n = p.dano_comandante[c.id] || 0;
    return `<span class="${n >= mesa.dano_letal ? "letal" : ""}" title="De ${esc(mesa.jugadores[c.dueno].nombre)}">${esc(c.nombre)}
      ${boton("dano_comandante", -1, "−", `data-carta="${c.id}"`)}<b>${n}</b>${boton("dano_comandante", 1, "+", `data-carta="${c.id}"`)}</span>`;
  }).join(" · ")}</span>`;
  return `
    <section class="jugador ${propio ? "propio" : ""} ${i === mesa.activo ? "activo" : ""} ${p.rindio ? "rindio" : ""}">
      <header>
        <strong>${esc(p.nombre)}${p.rindio ? " (se rindió)" : ""}</strong>
        <span>♥ ${boton("vida", -1, "−")}<b>${p.vida}</b>${boton("vida", 1, "+")}</span>
        <span>☠ ${boton("veneno", -1, "−")}<b>${p.veneno}</b>${boton("veneno", 1, "+")}</span>
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
  const miTurno = mesa.activo === mesa.yo && mesa.ganador === null;
  $("#info").innerHTML = mesa.ganador !== null
    ? `<p class="ganador">🏆 Ganó ${esc(mesa.jugadores[mesa.ganador].nombre)}</p> <a href="${URL_SALIR}">Volver</a>`
    : `<p>Turno ${mesa.turno} · juega <b>${esc(mesa.jugadores[mesa.activo].nombre)}</b>${mesa.formato ? ` · ${esc(mesa.formato)}` : ""}</p>`;
  $("#fases").innerHTML = FASES.map(([f, n]) =>
    `<button data-fase="${f}" class="${f === mesa.fase ? "actual" : ""}" ${miTurno ? "" : "disabled"}>${n}</button>`).join("");
  $("#pasar").disabled = !miTurno;
  const log = $("#log");
  const alFinal = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
  log.innerHTML = mesa.log.map(l =>
    `<li${l.carta?.imagen ? ` data-img="${esc(l.carta.imagen)}"` : ""}>${esc(l.t)}</li>`).join("");
  if (alFinal) log.scrollTop = log.scrollHeight;
}

function renderDialogo() {
  const dlg = $("#dialogo");
  if (!dialogo) { if (dlg.open) dlg.close(); return; }
  let titulo, html, pie = "";
  if (dialogo.tipo === "zona") {
    const p = mesa.jugadores[dialogo.jugador];
    titulo = `${NOMBRE[dialogo.zona]} de ${p.nombre}`;
    html = cartas(p.zonas[dialogo.zona], dialogo.zona, dialogo.jugador);
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

// --- Acciones de botones y menús -------------------------------------------

function pedirN(texto, f, porDefecto = 1) {
  const n = parseInt(prompt(texto, porDefecto), 10);
  if (n > 0) f(n);
}

const BOTONES = {
  pasar_turno: () => accion({ accion: "pasar_turno" }),
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
    ops.push(["Jugar", () => mover(id, c.tierra ? "tierras" : "campo", { jugador: yo })]);
    ops.push(["Jugar boca abajo", () => mover(id, "campo", { jugador: yo, boca_abajo: true })]);
    ops.push(["Revelar", hacer("revelar")]);
  } else if (zona !== "biblioteca") {
    ops.push(["Añadir contador…", otroContador]);
  }
  for (const t of Object.keys(c.contadores || {})) ops.push([`Quitar un contador ${t}`, hacer("contador", { tipo: t, delta: -1 })]);
  ops.push(null);
  for (const destino of ["mano", "campo", "tierras", "cementerio", "exilio", "mando"]) {
    if (destino === zona) continue;
    const jugador = CAMPO.has(destino) ? (CAMPO.has(zona) ? j : yo) : undefined;
    ops.push([`→ ${NOMBRE[destino]}`, () => mover(id, destino, { jugador })]);
  }
  ops.push(["→ Biblioteca (arriba)", () => mover(id, "biblioteca")]);
  ops.push(["→ Biblioteca (fondo)", () => mover(id, "biblioteca", { posicion: "abajo" })]);
  return ops;
}

function opcionesBiblioteca() {
  return [["Robar", BOTONES.robar], ["Robar varias…", BOTONES.robar_n], ["Mirar arriba…", BOTONES.mirar],
          ["Buscar en la biblioteca", BOTONES.buscar], ["Moler…", BOTONES.moler], null,
          ["Barajar", BOTONES.barajar], ["Mulligan", BOTONES.mulligan]];
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
  const fase = e.target.closest("[data-fase]");
  if (fase) return accion({ accion: "fase", fase: fase.dataset.fase });
  const stat = e.target.closest("[data-stat]");
  if (stat) return accion({ accion: stat.dataset.stat, jugador: +stat.dataset.jugador,
                            delta: +stat.dataset.delta, carta: stat.dataset.carta });
  const carta = e.target.closest(".carta"), info = carta && porId[carta.dataset.id];
  if (info && CAMPO.has(info.zona)) return accion({ accion: "girar", carta: info.c.id });
  const pila = e.target.closest(".pila");
  if (pila) {
    const j = +pila.dataset.jugador, zona = pila.dataset.zona;
    if (zona === "biblioteca" && j === mesa.yo) return BOTONES.robar();
    if (zona !== "biblioteca") { dialogo = { tipo: "zona", jugador: j, zona }; renderDialogo(); }
  }
});

document.addEventListener("dblclick", e => {
  const carta = e.target.closest(".carta"), info = carta && porId[carta.dataset.id];
  if (info?.zona === "mano") mover(info.c.id, info.c.tierra ? "tierras" : "campo", { jugador: mesa.yo });
});

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
document.addEventListener("keydown", e => { if (e.key === "Escape") cerrarMenu(); });

conectar();
