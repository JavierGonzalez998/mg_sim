from django import template

from app.invitados import nombre_visible

register = template.Library()


@register.filter
def nombre(usuario):
    """Nombre para mostrar: «Invitado N» para los invitados, el nombre de usuario para el resto."""
    return nombre_visible(usuario)
