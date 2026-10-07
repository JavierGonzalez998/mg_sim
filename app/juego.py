"""Mesa de Magic multijugador: estado, acciones y vista por jugador.

No aplica las reglas del juego (como una mesa real, los jugadores mueven sus cartas);
sí protege la información oculta: nadie ve la mano ni la biblioteca de otro.
Prioridad: solo actúa quien la tiene (el jugador activo, salvo que otro pulse «Responder»). Las respuestas se
apilan: al pasar la prioridad vuelve a quien la tenía antes. La pila de hechizos se resuelve de arriba abajo.
El estado es un dict serializable a JSON que se guarda en Partida.juego.
"""
import random
import time

ZONAS = ("biblioteca", "mano", "campo", "tierras", "cementerio", "exilio", "mando")
OCULTAS = {"biblioteca", "mano"}
CAMPO = {"campo", "tierras"}
FASES = ("comienzo", "principal1", "combate", "principal2", "final")
NOMBRE_ZONA = {"biblioteca": "la biblioteca", "mano": "la mano", "campo": "el campo de batalla",
               "tierras": "el campo de batalla", "cementerio": "el cementerio", "exilio": "el exilio",
               "mando": "la zona de mando", "pila": "la pila"}
MAX_LOG = 200
DANO_COMANDANTE_LETAL = 21
DURACION_TURNO = 10 * 60  # segundos; al agotarse, el turno pasa solo


class AccionInvalida(Exception):
    pass


def vida_inicial(formato):
    f = formato.lower()
    if "brawl" in f:
        return 25
    return 40 if f == "commander" else 20


def con_dano_comandante(formato):
    f = formato.lower()
    return "commander" in f or f == "pauperedh"


# --- Creación ---------------------------------------------------------------

def crear(jugadores, formato):
    """jugadores: lista de (user_id, nombre, mazo) con mazo = {"principal": [...], "comandantes": [...]}."""
    orden = list(jugadores)
    random.shuffle(orden)
    e = {"formato": formato, "turno": 1, "activo": 0, "fase": "comienzo", "ganador": None,
         "cartas": {}, "jugadores": [], "log": [], "sig": 0, "pila": [], "prioridad": [0],
         "inicio_turno": time.time()}
    for i, (uid, nombre, mazo) in enumerate(orden):
        e["jugadores"].append({"id": uid, "nombre": nombre, "vida": vida_inicial(formato), "veneno": 0,
                               "dano_comandante": {}, "mulligans": 0, "rindio": False,
                               "zonas": {z: [] for z in ZONAS}})
        for c in mazo["principal"]:
            _nueva_carta(e, i, c, "biblioteca")
        for c in mazo["comandantes"]:
            _nueva_carta(e, i, c, "mando", comandante=True)
        random.shuffle(e["jugadores"][i]["zonas"]["biblioteca"])
        _robar(e, i, 7)
    _log(e, f"Comienza la partida. Empieza {orden[0][1]}. Cada jugador robó 7 cartas. Mientras {orden[0][1]} "
            f"no cambie de fase, todos pueden hacer sus mulligans.")
    return e


def _nueva_carta(e, dueno, datos, zona, **extra):
    cid = str(e["sig"])
    e["sig"] += 1
    e["cartas"][cid] = {"nombre": datos["nombre"], "imagen": datos.get("imagen"), "reverso": datos.get("reverso"),
                        "tierra": datos.get("tierra", False), "dueno": dueno, "girada": False,
                        "boca_abajo": False, "volteada": False, "contadores": {}, "ficha": False,
                        "comandante": False, "lanzamientos": 0, **extra}
    e["jugadores"][dueno]["zonas"][zona].append(cid)
    return cid


# --- Utilidades -------------------------------------------------------------

def _log(e, texto, carta=None):
    e["log"].append({"t": texto, "carta": carta})
    del e["log"][:-MAX_LOG]


def _publica(c):
    return {"nombre": c["nombre"], "imagen": c["reverso"] if c["volteada"] else c["imagen"]}


def _nombre(e, i):
    return e["jugadores"][i]["nombre"]


def _ubicar(e, cid):
    if cid in e["pila"]:
        return e["cartas"][cid]["controlador"], "pila"
    for i, j in enumerate(e["jugadores"]):
        for z, ids in j["zonas"].items():
            if cid in ids:
                return i, z
    raise AccionInvalida("Esa carta no está en la mesa.")


def _carta(e, yo, a):
    """Devuelve (cid, jugador, zona). Las zonas ocultas solo las toca su dueño."""
    cid = str(a.get("carta"))
    if cid not in e["cartas"]:
        raise AccionInvalida("Esa carta no existe.")
    i, z = _ubicar(e, cid)
    if z in OCULTAS and i != yo:
        raise AccionInvalida("No puedes tocar cartas ocultas de otro jugador.")
    return cid, i, z


def _jugador(e, valor):
    try:
        i = int(valor)
    except (TypeError, ValueError):
        raise AccionInvalida("Jugador inválido.")
    if not 0 <= i < len(e["jugadores"]):
        raise AccionInvalida("Jugador inválido.")
    return i


def _entero(a, clave, defecto, minimo, maximo):
    try:
        n = int(a.get(clave, defecto))
    except (TypeError, ValueError):
        raise AccionInvalida(f"Valor inválido para {clave}.")
    return max(minimo, min(maximo, n))


def _texto(a, clave, maximo):
    t = str(a.get(clave, "")).strip()[:maximo]
    if not t:
        raise AccionInvalida("Falta el texto.")
    return t


def _lista(e, i, z):
    return e["pila"] if z == "pila" else e["jugadores"][i]["zonas"][z]


def _con_prioridad(e):
    return e["prioridad"][-1]


def _preparacion(e):
    """Antes de que el primer jugador cambie de fase todos actúan a la vez (mulligans)."""
    return e["turno"] == 1 and e["fase"] == "comienzo"


def _robar(e, i, n):
    biblioteca = e["jugadores"][i]["zonas"]["biblioteca"]
    robadas = biblioteca[:n]
    del biblioteca[:n]
    e["jugadores"][i]["zonas"]["mano"].extend(robadas)
    return len(robadas)


def _salir_del_campo(e, cid):
    """Al dejar el campo de batalla la carta vuelve a ser un objeto nuevo (regla 400.7)."""
    c = e["cartas"][cid]
    c.update(girada=False, boca_abajo=False, volteada=False, contadores={})


# --- Acciones ---------------------------------------------------------------

def a_robar(e, yo, a):
    n = _entero(a, "n", 1, 1, 30)
    robadas = _robar(e, yo, n)
    _log(e, f"{_nombre(e, yo)} robó {robadas} carta{'s' if robadas != 1 else ''}.")


def a_barajar(e, yo, a):
    random.shuffle(e["jugadores"][yo]["zonas"]["biblioteca"])
    _log(e, f"{_nombre(e, yo)} barajó su biblioteca.")


def a_mulligan(e, yo, a):
    # Mulligan de Londres: se roban 7 y luego el jugador pone N al fondo (con "mover").
    j = e["jugadores"][yo]
    j["zonas"]["biblioteca"].extend(j["zonas"]["mano"])
    j["zonas"]["mano"] = []
    random.shuffle(j["zonas"]["biblioteca"])
    _robar(e, yo, 7)
    j["mulligans"] += 1
    _log(e, f"{j['nombre']} hizo mulligan ({j['mulligans']}). Debe poner {j['mulligans']} carta(s) al fondo "
            f"(en multijugador el primer mulligan es gratis).")


def a_moler(e, yo, a):
    n = _entero(a, "n", 1, 1, 100)
    z = e["jugadores"][yo]["zonas"]
    molidas = z["biblioteca"][:n]
    del z["biblioteca"][:n]
    z["cementerio"].extend(molidas)
    _log(e, f"{_nombre(e, yo)} puso {len(molidas)} carta(s) de su biblioteca en su cementerio.")


def a_mirar(e, yo, a):
    """Mira las n cartas superiores (n=0: toda la biblioteca). Solo el que mira recibe las cartas."""
    n = _entero(a, "n", 1, 0, 1000)
    biblioteca = e["jugadores"][yo]["zonas"]["biblioteca"]
    ids = biblioteca if n == 0 else biblioteca[:n]
    _log(e, f"{_nombre(e, yo)} " + ("buscó en su biblioteca." if n == 0
                                     else f"miró las {len(ids)} carta(s) superiores de su biblioteca."))
    return {"vistazo": [_ver(e, cid, yo, yo) for cid in ids]}


def a_mover(e, yo, a):
    cid, origen_j, origen_z = _carta(e, yo, a)
    zona = a.get("zona")
    if zona not in ZONAS + ("pila",):
        raise AccionInvalida("Zona inválida.")
    if origen_z == "pila":
        if zona == "pila":
            return
        if cid != e["pila"][-1]:
            raise AccionInvalida("La pila se resuelve en orden: primero la carta de arriba.")
    c = e["cartas"][cid]
    # Al campo va al jugador elegido (cambia el control); desde la pila, por defecto a quien la lanzó;
    # a cualquier otra zona, siempre a la de su dueño.
    destino_j = _jugador(e, a.get("jugador", origen_j if origen_z == "pila" else yo)) if zona in CAMPO else c["dueno"]
    visible_antes = origen_z not in OCULTAS and not c["boca_abajo"]
    _lista(e, origen_j, origen_z).remove(cid)

    if origen_z in CAMPO and zona not in CAMPO:
        if c["ficha"]:
            del e["cartas"][cid]
            _log(e, f"{_nombre(e, yo)} quitó la ficha {c['nombre']} (dejó de existir).")
            return
        _salir_del_campo(e, cid)
    if origen_z == "mando" and zona in CAMPO | {"pila"} and c["comandante"]:
        c["lanzamientos"] += 1
    if zona in CAMPO and a.get("boca_abajo"):
        c["boca_abajo"] = True  # jugar boca abajo (transfigurar, manifestar...) sin revelar la carta

    if zona == "pila":
        c["controlador"] = yo
        e["pila"].append(cid)
        _log(e, f"{_nombre(e, yo)} lanzó {c['nombre']}.", _publica(c))
        return
    destino = e["jugadores"][destino_j]["zonas"][zona]
    if zona == "biblioteca" and a.get("posicion") != "abajo":
        destino.insert(0, cid)
    else:
        destino.append(cid)

    if origen_j == destino_j and {origen_z, zona} <= CAMPO:
        return  # entre campo y tierras del mismo jugador: solo es orden visual
    visible = visible_antes or (zona not in OCULTAS and not c["boca_abajo"])
    que = f"{c['nombre']}" if visible else "una carta"
    donde = NOMBRE_ZONA[zona]
    if zona == "biblioteca":
        donde = "el fondo de la biblioteca" if a.get("posicion") == "abajo" else "la parte superior de la biblioteca"
    de_quien = "" if destino_j == yo else f" de {_nombre(e, destino_j)}"
    _log(e, f"{_nombre(e, yo)} movió {que} de {NOMBRE_ZONA[origen_z]} a {donde}{de_quien}.",
         _publica(c) if visible else None)


def _en_campo(e, yo, a):
    cid, i, z = _carta(e, yo, a)
    if z not in CAMPO:
        raise AccionInvalida("La carta debe estar en el campo de batalla.")
    return cid, e["cartas"][cid]


def a_girar(e, yo, a):
    cid, c = _en_campo(e, yo, a)
    c["girada"] = not c["girada"]
    nombre = "una carta boca abajo" if c["boca_abajo"] else c["nombre"]
    _log(e, f"{_nombre(e, yo)} {'giró' if c['girada'] else 'enderezó'} {nombre}.")


def a_enderezar(e, yo, a):
    z = e["jugadores"][yo]["zonas"]
    for cid in z["campo"] + z["tierras"]:
        e["cartas"][cid]["girada"] = False
    _log(e, f"{_nombre(e, yo)} enderezó sus permanentes.")


def a_voltear(e, yo, a):
    cid, i, z = _carta(e, yo, a)
    c = e["cartas"][cid]
    if not c["reverso"]:
        raise AccionInvalida("Esta carta no tiene reverso.")
    c["volteada"] = not c["volteada"]
    _log(e, f"{_nombre(e, yo)} transformó {c['nombre']}.", _publica(c))


def a_boca_abajo(e, yo, a):
    cid, c = _en_campo(e, yo, a)
    c["boca_abajo"] = not c["boca_abajo"]
    _log(e, f"{_nombre(e, yo)} puso {'boca abajo una carta' if c['boca_abajo'] else 'boca arriba ' + c['nombre']}.",
         None if c["boca_abajo"] else _publica(c))


def a_contador(e, yo, a):
    cid, i, z = _carta(e, yo, a)
    if z in OCULTAS:
        raise AccionInvalida("No se ponen contadores en cartas ocultas.")
    c = e["cartas"][cid]
    tipo = _texto(a, "tipo", 20)
    delta = _entero(a, "delta", 1, -99, 99)
    n = max(0, c["contadores"].get(tipo, 0) + delta)
    if n:
        c["contadores"][tipo] = n
    else:
        c["contadores"].pop(tipo, None)
    nombre = "una carta boca abajo" if c["boca_abajo"] else c["nombre"]
    _log(e, f"{_nombre(e, yo)} {'puso' if delta > 0 else 'quitó'} {abs(delta)} contador(es) {tipo} "
            f"{'en' if delta > 0 else 'de'} {nombre} (ahora {n}).")


def a_vida(e, yo, a):
    i = _jugador(e, a.get("jugador", yo))
    delta = _entero(a, "delta", 0, -999, 999)
    e["jugadores"][i]["vida"] += delta
    _log(e, f"{_nombre(e, yo)}: vida de {_nombre(e, i)} {delta:+d} → {e['jugadores'][i]['vida']}.")


def a_veneno(e, yo, a):
    i = _jugador(e, a.get("jugador", yo))
    j = e["jugadores"][i]
    j["veneno"] = max(0, j["veneno"] + _entero(a, "delta", 1, -99, 99))
    _log(e, f"{_nombre(e, yo)}: veneno de {j['nombre']} → {j['veneno']}.")


def a_dano_comandante(e, yo, a):
    """Daño de combate de un comandante concreto a `jugador`; también resta esa vida.

    Se cuenta por comandante (no por jugador): con dos comandantes compañeros, cada uno lleva su cuenta.
    """
    i = _jugador(e, a.get("jugador", yo))
    cid = str(a.get("carta"))
    c = e["cartas"].get(cid)
    if not c or not c["comandante"]:
        raise AccionInvalida("Esa carta no es un comandante.")
    delta = _entero(a, "delta", 1, -99, 99)
    j = e["jugadores"][i]
    actual = j["dano_comandante"].get(cid, 0)
    nuevo = max(0, actual + delta)
    j["dano_comandante"][cid] = nuevo
    j["vida"] -= nuevo - actual
    aviso = " ¡Daño letal de comandante!" if nuevo >= DANO_COMANDANTE_LETAL else ""
    _log(e, f"{_nombre(e, yo)}: daño de {c['nombre']} ({_nombre(e, c['dueno'])}) a {j['nombre']} → {nuevo} "
            f"(vida {j['vida']}).{aviso}", _publica(c))


def a_ficha(e, yo, a):
    nombre = _texto(a, "nombre", 60)
    n = _entero(a, "cantidad", 1, 1, 30)
    for _ in range(n):
        _nueva_carta(e, yo, {"nombre": nombre}, "campo", ficha=True)
    _log(e, f"{_nombre(e, yo)} creó {n} ficha(s) de {nombre}.")


def a_copiar(e, yo, a):
    cid, c = _en_campo(e, yo, a)
    _nueva_carta(e, yo, {"nombre": c["nombre"], "imagen": c["imagen"], "reverso": c["reverso"]}, "campo", ficha=True)
    _log(e, f"{_nombre(e, yo)} creó una ficha copia de {c['nombre']}.", _publica(c))


def a_revelar(e, yo, a):
    cid, i, z = _carta(e, yo, a)
    c = e["cartas"][cid]
    _log(e, f"{_nombre(e, yo)} reveló {c['nombre']}.", _publica(c))


def a_revelar_mano(e, yo, a):
    nombres = [e["cartas"][cid]["nombre"] for cid in e["jugadores"][yo]["zonas"]["mano"]]
    _log(e, f"{_nombre(e, yo)} reveló su mano: {', '.join(nombres) or '(vacía)'}.")


def a_dado(e, yo, a):
    caras = _entero(a, "caras", 6, 2, 1000)
    _log(e, f"{_nombre(e, yo)} tiró un d{caras}: {random.randint(1, caras)}.")


def a_moneda(e, yo, a):
    _log(e, f"{_nombre(e, yo)} lanzó una moneda: {random.choice(['cara', 'cruz'])}.")


def _solo_activo(e, yo):
    if e["activo"] != yo:
        raise AccionInvalida("Solo el jugador activo puede hacer esto.")


def a_fase(e, yo, a):
    _solo_activo(e, yo)
    if a.get("fase") not in FASES:
        raise AccionInvalida("Fase inválida.")
    e["fase"] = a["fase"]


def _siguiente_vivo(e, desde):
    n = len(e["jugadores"])
    for paso in range(1, n + 1):
        i = (desde + paso) % n
        if not e["jugadores"][i]["rindio"]:
            return i
    return desde


def _pasar_turno(e):
    e["activo"] = _siguiente_vivo(e, e["activo"])
    e["turno"] += 1
    e["fase"] = "principal1"
    e["prioridad"] = [e["activo"]]
    e["inicio_turno"] = time.time()
    a_enderezar(e, e["activo"], {})
    _robar(e, e["activo"], 1)
    _log(e, f"Turno {e['turno']}: {_nombre(e, e['activo'])} enderezó y robó una carta.")


def a_pasar_turno(e, yo, a):
    _solo_activo(e, yo)
    if e["pila"]:
        raise AccionInvalida("Resuelve la pila antes de pasar el turno.")
    _pasar_turno(e)


def _restante(e):
    return e["inicio_turno"] + DURACION_TURNO - time.time()


def a_tiempo(e, yo, a):
    """Lo pide el navegador de cualquier jugador cuando su cuenta atrás llega a cero."""
    if _restante(e) > 2:  # margen por el desfase de los relojes
        raise AccionInvalida("Al turno aún le queda tiempo.")
    _log(e, f"⏱ Se acabó el tiempo de {_nombre(e, e['activo'])}.")
    _pasar_turno(e)


def a_responder(e, yo, a):
    if _con_prioridad(e) == yo:
        raise AccionInvalida("Ya tienes la prioridad.")
    e["prioridad"].append(yo)
    _log(e, f"✋ {_nombre(e, yo)} responde y toma la prioridad.")


def a_pasar_prioridad(e, yo, a):
    if len(e["prioridad"]) == 1:
        raise AccionInvalida("Eres el jugador activo: la prioridad vuelve a ti cuando los demás terminan.")
    e["prioridad"].pop()
    _log(e, f"{_nombre(e, yo)} pasó la prioridad a {_nombre(e, _con_prioridad(e))}.")


def a_rendirse(e, yo, a):
    j = e["jugadores"][yo]
    if j["rindio"]:
        return
    j["rindio"] = True
    e["prioridad"] = [i for i in e["prioridad"] if i != yo] or [e["activo"]]
    _log(e, f"{j['nombre']} se rindió.")
    vivos = [i for i, x in enumerate(e["jugadores"]) if not x["rindio"]]
    if len(vivos) == 1:
        e["ganador"] = vivos[0]
        _log(e, f"¡{_nombre(e, vivos[0])} gana la partida!")
    elif e["activo"] == yo:
        _pasar_turno(e)


def a_chat(e, yo, a):
    _log(e, f"💬 {_nombre(e, yo)}: {_texto(a, 'texto', 300)}")


ACCIONES = {nombre[2:]: f for nombre, f in globals().items() if nombre.startswith("a_")}
SIN_PRIORIDAD = {a_chat, a_rendirse, a_responder, a_tiempo}


def _actualizar(e):
    """Partidas empezadas antes de que existieran la pila y la prioridad."""
    e.setdefault("pila", [])
    e.setdefault("prioridad", [e["activo"]])
    e.setdefault("inicio_turno", time.time())


def aplicar(e, yo, a):
    """Aplica la acción `a` del jugador `yo` sobre `e`. Devuelve datos privados para él, o None."""
    f = ACCIONES.get(a.get("accion"))
    if not f:
        raise AccionInvalida("Acción desconocida.")
    if e["ganador"] is not None and f is not a_chat:
        raise AccionInvalida("La partida terminó.")
    if e["jugadores"][yo]["rindio"] and f not in (a_chat, a_tiempo):
        raise AccionInvalida("Te rendiste; solo puedes usar el chat.")
    _actualizar(e)
    if f not in SIN_PRIORIDAD and _con_prioridad(e) != yo and not _preparacion(e):
        raise AccionInvalida(f"Tiene la prioridad {_nombre(e, _con_prioridad(e))}. Pulsa «Responder» para actuar.")
    return f(e, yo, a)


# --- Vista ------------------------------------------------------------------

def _ver(e, cid, zona_de, yo):
    c = e["cartas"][cid]
    if c["boca_abajo"] and zona_de != yo:
        return {"id": cid, "oculta": True, "girada": c["girada"], "contadores": c["contadores"], "dueno": c["dueno"]}
    return {"id": cid, **_publica(c), "tierra": c["tierra"], "girada": c["girada"], "boca_abajo": c["boca_abajo"],
            "contadores": c["contadores"], "ficha": c["ficha"], "comandante": c["comandante"],
            "impuesto": 2 * c["lanzamientos"], "dueno": c["dueno"], "reverso": bool(c["reverso"])}


def vista(e, yo):
    """Lo que ve el jugador `yo`: sus cartas ocultas sí, las ajenas solo como cantidad."""
    _actualizar(e)
    jugadores = []
    for i, j in enumerate(e["jugadores"]):
        zonas = {}
        for z, ids in j["zonas"].items():
            if z == "biblioteca" or (z == "mano" and i != yo):
                zonas[z] = len(ids)
            else:
                zonas[z] = [_ver(e, cid, i, yo) for cid in ids]
        jugadores.append({k: j[k] for k in ("id", "nombre", "vida", "veneno", "dano_comandante", "mulligans", "rindio")}
                         | {"zonas": zonas})
    # Los comandantes son información pública: se listan para el contador de daño de cada uno.
    comandantes = [{"id": cid, "nombre": c["nombre"], "dueno": c["dueno"]}
                   for cid, c in e["cartas"].items() if c["comandante"]]
    return {"yo": yo, "turno": e["turno"], "activo": e["activo"], "fase": e["fase"], "formato": e["formato"],
            "dano_comandante": con_dano_comandante(e["formato"]), "comandantes": comandantes,
            "dano_letal": DANO_COMANDANTE_LETAL, "ganador": e["ganador"],
            "jugadores": jugadores, "log": e["log"][-80:], "prioridad": _con_prioridad(e),
            "preparacion": _preparacion(e), "restante": max(0, round(_restante(e))),
            "pila": [_ver(e, cid, e["cartas"][cid]["controlador"], yo) | {"controlador": e["cartas"][cid]["controlador"]}
                     for cid in e["pila"]]}
