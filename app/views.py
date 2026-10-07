import json
import re
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django import forms
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from user.models import Amistad, Preferencias

from . import juego
from .context_processors import invitaciones as invitaciones_y_solicitudes
from .invitados import crear_invitado, es_invitado, nombre_libre, nombre_visible
from .models import ORDEN_CATEGORIAS, Carta, Jugador, Mazo, Partida, avisar_cambio

# Tableros de Moxfield que importamos y su zona en nuestro mazo
BOARDS = {"commanders": "comandante", "mainboard": "principal",
          "companions": "banquillo", "sideboard": "banquillo"}
DOBLE_CARA = {"transform", "modal_dfc", "reversible_card", "double_faced_token"}


def importar_moxfield(moxfield_id):
    # ponytail: API no oficial de Moxfield; si la bloquean, importar desde el texto exportado
    req = Request(f"https://api2.moxfield.com/v3/decks/all/{moxfield_id}",
                  headers={"User-Agent": "mg_simulator/0.1"})
    with urlopen(req, timeout=15) as r:
        datos = json.load(r)
    cartas = []
    for board, zona in BOARDS.items():
        for item in datos["boards"].get(board, {}).get("cards", {}).values():
            c = item["card"]
            cara = (c.get("card_faces") or [{}])[0]
            cartas.append(Carta(
                zona=zona, cantidad=item["quantity"], nombre=c["name"],
                tipo=c.get("type_line") or cara.get("type_line", ""),
                coste=c.get("mana_cost") or cara.get("mana_cost", ""),
                cmc=c.get("cmc", 0), scryfall_id=c["scryfall_id"],
                doble_cara=c.get("layout") in DOBLE_CARA,
            ))
    return datos["name"], cartas, datos.get("format") or ""


class ImportarForm(forms.Form):
    url = forms.URLField(label="Enlace del mazo en Moxfield")

    def clean_url(self):
        m = re.search(r"moxfield\.com/decks/([\w-]+)", self.cleaned_data["url"])
        if not m:
            raise forms.ValidationError("Debe ser un enlace de Moxfield (moxfield.com/decks/...).")
        return m.group(1)


class ProbarForm(ImportarForm):
    mazo = forms.ModelChoiceField(queryset=Mazo.objects.none(), required=False,
                                  label="Uno de mis mazos", empty_label="—")
    field_order = ["mazo", "url"]

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mazo"].queryset = usuario.mazos.order_by("nombre")
        self.fields["url"].required = False
        self.fields["url"].label = "O un enlace de Moxfield"

    def clean_url(self):
        return super().clean_url() if self.cleaned_data.get("url") else ""

    def clean(self):
        datos = super().clean()
        if bool(datos.get("mazo")) == bool(datos.get("url")):
            raise forms.ValidationError("Elige uno de tus mazos o pega un enlace de Moxfield, pero no ambos.")
        return datos


def cargar_moxfield(moxfield_id):
    """Devuelve ((nombre, cartas, formato), None) o (None, mensaje de error)."""
    try:
        return importar_moxfield(moxfield_id), None
    except HTTPError as e:
        return None, ("No se encontró el mazo (¿es privado?)." if e.code == 404
                      else f"Moxfield respondió con un error ({e.code}).")
    except (URLError, TimeoutError, ValueError, KeyError):
        return None, "No se pudo leer el mazo desde Moxfield."


def contexto_mazos(usuario, form=None):
    """Contexto de la sección "Mis mazos" (app/_mazos.html), usada en /mazos/ y en el perfil."""
    total = Sum("cartas__cantidad", filter=~Q(cartas__zona="banquillo"))
    return {"form_importar": form or ImportarForm(),
            "mazos": usuario.mazos.annotate(total=total).order_by("-creado")}


def volver(request, por_defecto="mazos"):
    destino = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(por_defecto)


def mazo_elegido(form):
    """Con un ProbarForm válido: (nombre, cartas, formato) del mazo o del enlace; si falla, deja el error en el form."""
    mazo = form.cleaned_data.get("mazo")  # los invitados no tienen ese campo
    if mazo:
        return mazo.nombre, mazo.cartas.all(), mazo.formato
    cargado, error = cargar_moxfield(form.cleaned_data["url"])
    if error:
        form.add_error("url", error)
    return cargado


def datos_tablero(cartas):
    datos = {"principal": [], "comandantes": []}
    for c in cartas:
        if c.zona == "banquillo":
            continue
        lista = datos["comandantes" if c.zona == "comandante" else "principal"]
        lista += [{"nombre": c.nombre, "imagen": c.imagen, "reverso": c.imagen_reverso,
                   "tierra": c.categoria == "Tierras"}] * c.cantidad
    return datos


def inicio(request):
    try:
        changelog = (settings.BASE_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        changelog = ""
    return render(request, "app/inicio.html", {"versiones": leer_changelog(changelog)})


def _md(texto):
    """Markdown en línea del changelog: **negrita**, `código` y [enlaces](url). El resto se escapa."""
    html = escape(texto)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)
    html = re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', html)
    return mark_safe(html)


def leer_changelog(texto):
    """CHANGELOG.md (formato Keep a Changelog) → [{version, fecha, secciones: [{titulo, cambios: [{texto, sub}]}]}]."""
    versiones, item = [], None
    for linea in texto.splitlines():
        if m := re.match(r"## \[(.+?)\](?: - (\d{4}-\d{2}-\d{2}))?", linea):
            fecha = date.fromisoformat(m[2]) if m[2] else None
            versiones.append({"version": m[1], "fecha": fecha, "secciones": []})
            item = None
        elif not versiones:
            continue
        elif linea.startswith("### "):
            versiones[-1]["secciones"].append({"titulo": linea[4:].strip(), "cambios": []})
            item = None
        elif (m := re.match(r"( *)- (.+)", linea)) and versiones[-1]["secciones"]:
            cambios = versiones[-1]["secciones"][-1]["cambios"]
            item = {"texto": m[2], "sub": []}
            (cambios[-1]["sub"] if m[1] and cambios else cambios).append(item)
        elif item and linea.startswith("  ") and linea.strip():
            item["texto"] += " " + linea.strip()  # continuación de una línea larga
        else:
            item = None
    for v in versiones:
        for s in v["secciones"]:
            for c in s["cambios"]:
                c["texto"] = _md(c["texto"])
                for sub in c["sub"]:
                    sub["texto"] = _md(sub["texto"])
    return versiones


@login_required
def mazos(request):
    form = ImportarForm(request.POST or None)
    if form.is_valid():
        cargado, error = cargar_moxfield(form.cleaned_data["url"])
        if error:
            form.add_error("url", error)
    if form.is_valid():
        nombre, cartas, formato = cargado
        with transaction.atomic():
            mazo = Mazo.objects.create(usuario=request.user, nombre=nombre, formato=formato,
                                       moxfield_id=form.cleaned_data["url"])
            for c in cartas:
                c.mazo = mazo
            Carta.objects.bulk_create(cartas)
        return redirect("mazo", mazo.pk)
    return render(request, "app/mazos.html", contexto_mazos(request.user, form))


@login_required
@require_POST
def actualizar_mazo(request, pk):
    mazo = get_object_or_404(Mazo, pk=pk, usuario=request.user)
    cargado, error = cargar_moxfield(mazo.moxfield_id)
    if error:
        messages.error(request, f"{mazo.nombre}: {error}")
    else:
        mazo.nombre, cartas, mazo.formato = cargado
        with transaction.atomic():
            mazo.save()
            mazo.cartas.all().delete()
            for c in cartas:
                c.mazo = mazo
            Carta.objects.bulk_create(cartas)
        messages.success(request, f"{mazo.nombre} se actualizó desde Moxfield.")
    return volver(request)


@login_required
@require_POST
def eliminar_mazo(request, pk):
    mazo = get_object_or_404(Mazo, pk=pk, usuario=request.user)
    mazo.delete()
    messages.success(request, f"{mazo.nombre} se eliminó.")
    return volver(request)


@login_required
def mazo(request, pk):
    mazo = get_object_or_404(Mazo, pk=pk, usuario=request.user)
    grupos = {}
    for c in mazo.cartas.order_by("cmc", "nombre"):
        grupos.setdefault(c.categoria, []).append(c)
    grupos = [(k, grupos[k], sum(c.cantidad for c in grupos[k])) for k in ORDEN_CATEGORIAS if k in grupos]
    total = sum(t for k, _, t in grupos if k != "Banquillo")
    return render(request, "app/mazo.html", {"mazo": mazo, "grupos": grupos, "total": total})


def solo_pc(vista):
    """El tablero aún no funciona con pantallas táctiles: base.html lo oculta en ellas y muestra un aviso."""
    def envuelta(request, *args, **kwargs):
        request.solo_pc = True
        return vista(request, *args, **kwargs)
    return envuelta


@login_required
@solo_pc
def probar(request):
    form = ProbarForm(request.GET or None, usuario=request.user)
    if form.is_valid():
        mazo = form.cleaned_data["mazo"]
        cargado = mazo_elegido(form)
        if form.is_valid():
            nombre, cartas, _ = cargado
            return render(request, "app/jugar.html", {"nombre": nombre, "mazo": mazo, "datos": datos_tablero(cartas)})
    return render(request, "app/probar.html", {"form": form})


# --- Partidas multijugador (/game/) -----------------------------------------

def _mi_jugador(request, pk, aceptada=True):
    """Partida y Jugador del usuario actual; 404 si no participa (o solo está invitado y se exige aceptada)."""
    partida = get_object_or_404(Partida, pk=pk)
    filtro = {"usuario": request.user} | ({"aceptada": True} if aceptada else {})
    jugador = partida.jugadores.filter(**filtro).first()
    if not jugador:
        raise Http404
    return partida, jugador


def _en_sala(request, partida, solo_anfitrion=False):
    if partida.estado != "sala":
        messages.error(request, "La partida ya comenzó.")
        return False
    if solo_anfitrion and partida.anfitrion_id != request.user.id:
        messages.error(request, "Solo el anfitrión puede hacer esto.")
        return False
    return True


def amigos_de(usuario):
    return [am.otro(usuario) for am in Amistad.de_usuario(usuario).filter(aceptada=True).select_related("de", "a")]


@login_required
@solo_pc
def partidas(request):
    mias = (Partida.objects.filter(jugadores__usuario=request.user, jugadores__aceptada=True)
            .exclude(estado="terminada").select_related("anfitrion").order_by("-creada"))
    return render(request, "app/partidas.html", {"partidas": mias, "en_curso": partida_en_curso(request.user, mias)})


@login_required
def notificaciones(request):
    """Panel de notificaciones ya renderizado, para actualizarlo en vivo (lo pide base.html al recibir el aviso
    de NotificacionesConsumer). `desde` es la página abierta, a la que se vuelve tras aceptar o rechazar."""
    contexto = {"volver_a": request.GET.get("desde", "/")}  # el resto lo pone el context processor
    return JsonResponse({
        "total": invitaciones_y_solicitudes(request)["notificaciones"],
        "panel": render_to_string("app/_notificaciones.html", contexto, request),
        "avisos": render_to_string("app/_avisos_invitacion.html", contexto, request),
    })


def partida_en_curso(usuario, partidas=None):
    """La sala o partida sin terminar en la que está el usuario, o None. No cuenta aquellas en las que se rindió."""
    if partidas is None:
        partidas = (Partida.objects.filter(jugadores__usuario=usuario, jugadores__aceptada=True)
                    .exclude(estado="terminada").order_by("-creada"))
    for p in partidas:
        if p.estado == "sala" or not any(j["id"] == usuario.id and j["rindio"] for j in p.juego["jugadores"]):
            return p
    return None


@login_required
@require_POST
def crear_partida(request):
    # Una partida a la vez: quien está en una sala o partida (sea anfitrión o invitado) no puede crear otra.
    if en_curso := partida_en_curso(request.user):
        messages.error(request, "Ya estás en una partida. Termínala, ríndete o sal de la sala antes de crear otra.")
        return redirect("sala", en_curso.pk)
    partida = Partida.objects.create(anfitrion=request.user)
    Jugador.objects.create(partida=partida, usuario=request.user, aceptada=True)
    return redirect("sala", partida.pk)


@login_required
@solo_pc
def sala(request, pk):
    partida, yo = _mi_jugador(request, pk, aceptada=False)
    if partida.estado != "sala":
        if not yo.aceptada:
            raise Http404
        # Fondo de cada jugador registrado para su zona de la mesa (lo eligen en su perfil).
        fondos = dict(Preferencias.objects.filter(usuario__participaciones__partida=partida, usuario__participaciones__aceptada=True)
                      .exclude(fondo="").values_list("usuario_id", "fondo"))
        return render(request, "app/partida.html", {"partida": partida, "fondos": fondos})
    jugadores = list(partida.jugadores.select_related("usuario").order_by("pk"))
    en_sala = {j.usuario_id for j in jugadores}
    es_anfitrion = partida.anfitrion_id == request.user.id
    invitables = [a for a in amigos_de(request.user) if a.pk not in en_sala] if es_anfitrion else []
    return render(request, "app/sala.html", {
        "partida": partida, "yo": yo, "jugadores": jugadores, "es_anfitrion": es_anfitrion,
        "invitables": invitables, "hay_lugar": len(jugadores) < Partida.MAX_JUGADORES,
        "form_mazo": form_mazo(request.user), "problemas": partida.problemas_para_iniciar(),
        "link": link_invitacion(request, partida) if es_anfitrion else None,
    })


@login_required
@require_POST
def invitar(request, pk):
    partida, yo = _mi_jugador(request, pk)
    if _en_sala(request, partida, solo_anfitrion=True):
        amigo = next((a for a in amigos_de(request.user) if a.username == request.POST.get("username")), None)
        if not amigo:
            messages.error(request, "Solo puedes invitar a tus amigos.")
        elif partida.jugadores.count() >= Partida.MAX_JUGADORES:
            messages.error(request, f"Máximo {Partida.MAX_JUGADORES} jugadores por partida.")
        else:
            Jugador.objects.get_or_create(partida=partida, usuario=amigo)
            partida.tocar()
            messages.success(request, f"Invitaste a {amigo.username}.")
    return redirect("sala", pk)


def form_mazo(usuario, datos=None):
    """Elegir mazo en la sala. Los invitados no tienen mazos guardados: solo pueden pegar un enlace de Moxfield."""
    form = ProbarForm(datos, usuario=usuario)
    if es_invitado(usuario):
        del form.fields["mazo"]
        form.fields["url"].label = "Enlace de tu mazo en Moxfield"
    return form


# --- Links de invitación ------------------------------------------------------
# El link lleva el id de la partida firmado con la SECRET_KEY: no se puede adivinar ni alterar.

SAL_INVITACION = "app.invitacion"


def link_invitacion(request, partida):
    token = signing.dumps(partida.pk, salt=SAL_INVITACION)
    return request.build_absolute_uri(reverse("invitacion", args=[token]))


def invitacion(request, token):
    """Página del link: usuarios con sesión se unen con su cuenta; sin sesión pueden iniciarla, registrarse o
    entrar como invitado (cuenta temporal «Invitado N» que solo puede usar enlaces de Moxfield)."""
    try:
        pk = signing.loads(token, salt=SAL_INVITACION)
    except signing.BadSignature:
        raise Http404
    partida = get_object_or_404(Partida.objects.select_related("anfitrion"), pk=pk)
    yo = partida.jugadores.filter(usuario=request.user).first() if request.user.is_authenticated else None
    if yo and yo.aceptada:
        return redirect("sala", pk)
    unidos = partida.jugadores.filter(aceptada=True).count()
    error = ("Esta partida ya empezó o terminó." if partida.estado != "sala"
             else "La sala está llena." if unidos >= Partida.MAX_JUGADORES else "")
    if request.method == "POST" and not error:
        # Los invitados se numeran dentro de cada partida: «Invitado 1», «Invitado 2»…
        if not request.user.is_authenticated:
            login(request, crear_invitado(nombre_libre(partida)), backend="django.contrib.auth.backends.ModelBackend")
        elif es_invitado(request.user):  # un invitado que llega con el link de otra partida
            request.user.first_name = nombre_libre(partida)
            request.user.save(update_fields=["first_name"])
        Jugador.objects.update_or_create(partida=partida, usuario=request.user, defaults={"aceptada": True})
        partida.tocar()
        return redirect("sala", pk)
    return render(request, "app/invitacion.html", {"partida": partida, "unidos": unidos, "error": error})


@login_required
@require_POST
def unirse(request, pk):
    partida, yo = _mi_jugador(request, pk, aceptada=False)
    if _en_sala(request, partida):
        yo.aceptada = True
        yo.save()
        partida.tocar()
    return redirect("sala", pk)


@login_required
@require_POST
def salir(request, pk):
    """Rechazar la invitación o salir de la sala; si sale el anfitrión, la partida se cancela."""
    partida, yo = _mi_jugador(request, pk, aceptada=False)
    if _en_sala(request, partida):
        if partida.anfitrion_id == request.user.id:
            partida.delete()
            avisar_cambio(pk)
            messages.success(request, "Cancelaste la partida.")
        else:
            yo.delete()
            partida.tocar()
        return redirect("partidas")
    return redirect("sala", pk)


@login_required
@require_POST
def elegir_mazo(request, pk):
    partida, yo = _mi_jugador(request, pk)
    if not _en_sala(request, partida):
        return redirect("sala", pk)
    form = form_mazo(request.user, request.POST)
    cargado = mazo_elegido(form) if form.is_valid() else None
    if not form.is_valid():
        messages.error(request, " ".join(e for errores in form.errors.values() for e in errores))
        return redirect("sala", pk)
    nombre, cartas, formato = cargado
    es_anfitrion = partida.anfitrion_id == request.user.id
    anfitrion_eligio = partida.jugadores.filter(usuario_id=partida.anfitrion_id).exclude(mazo_nombre="").exists()
    if not es_anfitrion and anfitrion_eligio and formato != partida.formato:
        messages.error(request, f"El anfitrión eligió un mazo de formato «{partida.formato or 'sin formato'}»; "
                                f"el tuyo es «{formato or 'sin formato'}».")
        return redirect("sala", pk)
    with transaction.atomic():
        yo.mazo_nombre, yo.formato, yo.cartas = nombre, formato, datos_tablero(cartas)
        yo.save()
        if es_anfitrion:
            partida.formato = formato
            partida.save(update_fields=["formato"])
            distintos = partida.jugadores.exclude(pk=yo.pk).exclude(mazo_nombre="").exclude(formato=formato)
            if distintos.update(mazo_nombre="", formato="", cartas={}):
                messages.info(request, "Algunos jugadores tenían mazos de otro formato y deberán elegir de nuevo.")
    partida.tocar()
    messages.success(request, f"Elegiste {nombre}.")
    return redirect("sala", pk)


@login_required
@require_POST
def iniciar(request, pk):
    partida, yo = _mi_jugador(request, pk)
    if _en_sala(request, partida, solo_anfitrion=True):
        problemas = partida.problemas_para_iniciar()
        if problemas:
            for p in problemas:
                messages.error(request, p)
        else:
            with transaction.atomic():
                partida.jugadores.filter(aceptada=False).delete()
                unidos = partida.jugadores.select_related("usuario")
                partida.juego = juego.crear([(j.usuario_id, nombre_visible(j.usuario), j.cartas) for j in unidos],
                                            partida.formato)
                partida.estado = "jugando"
                partida.save()
            partida.tocar()
    return redirect("sala", pk)


def _indice(partida, usuario):
    return next(i for i, j in enumerate(partida.juego["jugadores"]) if j["id"] == usuario.id)


def estado_para(pk, usuario):
    """Lo que ve `usuario` de la partida (sin la información oculta ajena), o None si ya no participa."""
    partida = Partida.objects.filter(pk=pk).first()
    yo = partida and partida.jugadores.filter(usuario=usuario).first()
    if not yo:
        return None
    datos = {"version": partida.version, "estado": partida.estado}
    if partida.estado != "sala" and yo.aceptada:
        datos["mesa"] = juego.vista(partida.juego, _indice(partida, usuario))
    return datos


@login_required
def estado_partida(request, pk):
    """Lo mismo que envía el WebSocket, por HTTP (para depurar o si el WebSocket no está disponible)."""
    datos = estado_para(pk, request.user)
    if not datos:
        raise Http404
    return JsonResponse(datos)


@login_required
@require_POST
def accion_partida(request, pk):
    _mi_jugador(request, pk)
    try:
        accion = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "JSON inválido."}, status=400)
    if not isinstance(accion, dict):
        return JsonResponse({"error": "JSON inválido."}, status=400)
    # Concurrencia optimista: si otro jugador guardó entre medio, se relee y se reintenta.
    for _ in range(5):
        partida = Partida.objects.get(pk=pk)
        if partida.estado == "sala":
            return JsonResponse({"error": "La partida no ha comenzado."}, status=400)
        yo = _indice(partida, request.user)
        try:
            privado = juego.aplicar(partida.juego, yo, accion)
        except juego.AccionInvalida as e:
            return JsonResponse({"error": str(e)}, status=400)
        estado = "terminada" if partida.juego["ganador"] is not None else partida.estado
        if Partida.objects.filter(pk=pk, version=partida.version).update(
                juego=partida.juego, estado=estado, version=partida.version + 1):
            avisar_cambio(pk)
            return JsonResponse({"version": partida.version + 1, "estado": estado,
                                 "mesa": juego.vista(partida.juego, yo), **(privado or {})})
    return JsonResponse({"error": "La mesa está muy ocupada, intenta de nuevo."}, status=409)
