from .models import Jugador


def invitaciones(request):
    """Invitaciones a partidas pendientes, para el aviso de base.html."""
    if not request.user.is_authenticated:
        return {}
    return {"invitaciones": Jugador.objects.filter(usuario=request.user, aceptada=False, partida__estado="sala")
            .select_related("partida__anfitrion")}
