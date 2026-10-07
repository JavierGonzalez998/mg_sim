"""Jugadores invitados: entran a una partida con su link sin tener cuenta.

Al entrar se les crea una cuenta temporal sin contraseña (no puede volver a iniciar sesión). Se muestran como
«Invitado 1», «Invitado 2»… numerados dentro de cada partida (ese nombre va en first_name); el username es único
e interno («Invitado #a1b2c3d4»): lleva un espacio, que el registro no admite, así que no choca con usuarios reales.
"""
import re
import secrets

from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.shortcuts import redirect

PREFIJO = "Invitado "


def es_invitado(usuario):
    return (usuario.is_authenticated and usuario.username.startswith(PREFIJO)
            and not usuario.has_usable_password())


def nombre_visible(usuario):
    return usuario.first_name if es_invitado(usuario) and usuario.first_name else usuario.username


def nombre_libre(partida):
    """«Invitado N» con el menor N que no use otro invitado de esa partida."""
    usados = {u.first_name for u in User.objects.filter(participaciones__partida=partida, username__startswith=PREFIJO)}
    return next(f"{PREFIJO}{n}" for n in range(1, len(usados) + 2) if f"{PREFIJO}{n}" not in usados)


def crear_invitado(nombre):
    while True:
        try:
            with transaction.atomic():  # sin contraseña
                return User.objects.create_user(f"{PREFIJO}#{secrets.token_hex(4)}", first_name=nombre)
        except IntegrityError:  # id interno repetido (casi imposible): se prueba otro
            pass


class SoloSuPartida:
    """Los invitados solo pueden usar su partida: cualquier otra página los devuelve a ella. Si ya no están
    en ninguna (terminó, salieron o se canceló), se cierra su sesión."""

    PERMITIDAS = re.compile(r"^/(game/\d+/|game/invitacion/|notificaciones/|static/|login/logout/)")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if es_invitado(request.user) and not self.PERMITIDAS.match(request.path):
            from .views import partida_en_curso
            if partida := partida_en_curso(request.user):
                return redirect("sala", partida.pk)
            logout(request)
            return redirect("inicio")
        return self.get_response(request)
