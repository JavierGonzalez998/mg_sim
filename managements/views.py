from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.models import Mazo, Partida, avisar_cambio
from user.models import Amistad


def solo_superusuario(vista):
    """Sin sesión: al login. Con sesión pero sin ser superusuario: 403."""
    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


@solo_superusuario
def panel(request):
    hace_7_dias = timezone.now() - timedelta(days=7)
    partidas_por_estado = dict(Partida.objects.values_list("estado").annotate(n=Count("pk")))
    q = request.GET.get("q", "").strip()
    usuarios = User.objects.annotate(n_mazos=Count("mazos", distinct=True)).order_by("-date_joined")
    if q:
        usuarios = usuarios.filter(Q(username__icontains=q) | Q(email__icontains=q))
    return render(request, "managements/index.html", {
        "estadisticas": [
            ("Usuarios", User.objects.count(), f"{User.objects.filter(date_joined__gte=hace_7_dias).count()} nuevos esta semana"),
            ("Activos (7 días)", User.objects.filter(last_login__gte=hace_7_dias).count(), "iniciaron sesión"),
            ("Mazos", Mazo.objects.count(), f"{Mazo.objects.values('usuario').distinct().count()} usuarios con mazos"),
            ("Partidas en juego", partidas_por_estado.get("jugando", 0),
             f"{partidas_por_estado.get('sala', 0)} en sala · {partidas_por_estado.get('terminada', 0)} terminadas"),
            ("Amistades", Amistad.objects.filter(aceptada=True).count(),
             f"{Amistad.objects.filter(aceptada=False).count()} solicitudes pendientes"),
        ],
        "formatos": Mazo.objects.values("formato").annotate(n=Count("pk")).order_by("-n")[:10],
        "q": q,
        "usuarios": usuarios[:25],
        "partidas": (Partida.objects.exclude(estado="terminada").select_related("anfitrion")
                     .annotate(n_jugadores=Count("jugadores", filter=Q(jugadores__aceptada=True)))
                     .order_by("-creada")[:25]),
    })


@solo_superusuario
@require_POST
def cambiar_activo(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        messages.success(request, f"{usuario.username} quedó {'activado' if usuario.is_active else 'desactivado'}.")
    return redirect("panel")


@solo_superusuario
@require_POST
def eliminar_partida(request, pk):
    partida = get_object_or_404(Partida, pk=pk)
    partida.delete()
    avisar_cambio(pk)  # los jugadores conectados vuelven a /game/
    messages.success(request, f"Se eliminó la partida {pk}.")
    return redirect("panel")
