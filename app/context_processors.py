from user.models import Amistad

from .invitados import es_invitado
from .models import Jugador


def invitaciones(request):
    """Invitaciones a partidas y solicitudes de amistad pendientes, para las notificaciones de base.html."""
    if not request.user.is_authenticated:
        return {}
    invitaciones = list(Jugador.objects.filter(usuario=request.user, aceptada=False, partida__estado="sala")
                        .select_related("partida__anfitrion"))
    solicitudes = list(Amistad.objects.filter(a=request.user, aceptada=False).select_related("de"))
    return {"invitaciones": invitaciones, "solicitudes": solicitudes,
            "notificaciones": len(invitaciones) + len(solicitudes), "es_invitado": es_invitado(request.user)}
