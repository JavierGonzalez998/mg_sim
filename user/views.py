import re

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app.views import contexto_mazos, volver

from .models import Amistad, Preferencias


class RegistroForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email


def registro(request):
    form = RegistroForm(request.POST or None)
    if form.is_valid():
        login(request, form.save())
        return volver(request, "perfil")  # p. ej. de vuelta al link de invitación que trajo al usuario
    return render(request, "user/registro.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def perfil(request):
    yo = request.user
    amistades = Amistad.de_usuario(yo).select_related("de", "a")
    contexto = {
        "amigos": sorted(((am, am.otro(yo)) for am in amistades if am.aceptada), key=lambda x: x[1].username.lower()),
        "recibidas": [am for am in amistades if not am.aceptada and am.a == yo],
        "enviadas": [am for am in amistades if not am.aceptada and am.de == yo],
    }
    fondo = Preferencias.objects.filter(usuario=yo).first()
    return render(request, "user/perfil.html", {**contexto_mazos(yo), **contexto, "fondo": fondo})


# Solo se aceptan artes de cartas de Scryfall (art crop), nunca una URL cualquiera.
ARTE_SCRYFALL = re.compile(r"https://cards\.scryfall\.io/art_crop/(front|back)/[0-9a-f]/[0-9a-f]/[0-9a-f-]{36}\.jpg(\?\d+)?")


@login_required
@require_POST
def cambiar_fondo(request):
    """Fondo de la zona del usuario en la mesa: un arte de carta elegido en el perfil, o ninguno."""
    url = request.POST.get("fondo", "").strip()
    if url and not ARTE_SCRYFALL.fullmatch(url):
        messages.error(request, "Elige uno de los artes de carta de la lista.")
    else:
        Preferencias.objects.update_or_create(usuario=request.user, defaults={
            "fondo": url, "fondo_nombre": request.POST.get("nombre", "")[:200] if url else ""})
        messages.success(request, "Cambiaste el fondo de tu zona de la mesa." if url else "Quitaste el fondo de tu zona.")
    return redirect(reverse("perfil") + "#fondo")


@login_required
def ver_perfil(request, username):
    otro = get_object_or_404(User, username=username)
    if otro == request.user:
        return redirect("perfil")
    return render(request, "user/ver_perfil.html", {"otro": otro, "amistad": Amistad.entre(request.user, otro)})


@login_required
def buscar_usuarios(request):
    q = request.GET.get("q", "").strip()
    usuarios = (User.objects.filter(username__icontains=q, is_active=True).exclude(pk=request.user.pk)
                .order_by("username")[:20]) if q else []
    return render(request, "user/buscar.html", {"q": q, "usuarios": usuarios})


@login_required
@require_POST
def enviar_solicitud(request):
    otro = get_object_or_404(User, username=request.POST.get("username", ""))
    amistad = Amistad.entre(request.user, otro)
    if otro == request.user:
        messages.error(request, "No puedes enviarte una solicitud a ti mismo.")
    elif not amistad:
        Amistad.objects.create(de=request.user, a=otro)
        messages.success(request, f"Enviaste una solicitud a {otro.username}.")
    elif amistad.a == request.user and not amistad.aceptada:
        # El otro ya nos había enviado una: la aceptamos en vez de duplicar
        amistad.aceptada = True
        amistad.save()
        messages.success(request, f"Ahora eres amigo de {otro.username}.")
    else:
        messages.info(request, "Ya existe una solicitud o amistad con este usuario.")
    return volver(request, "perfil")


@login_required
@require_POST
def aceptar_solicitud(request, pk):
    amistad = get_object_or_404(Amistad, pk=pk, a=request.user, aceptada=False)
    amistad.aceptada = True
    amistad.save()
    messages.success(request, f"Ahora eres amigo de {amistad.de.username}.")
    return volver(request, "perfil")


@login_required
@require_POST
def eliminar_amistad(request, pk):
    """Rechazar, cancelar una solicitud o eliminar a un amigo: en todos los casos se borra la fila."""
    amistad = get_object_or_404(Amistad.de_usuario(request.user), pk=pk)
    amistad.delete()
    messages.success(request, f"Se eliminó la relación con {amistad.otro(request.user).username}.")
    return volver(request, "perfil")
