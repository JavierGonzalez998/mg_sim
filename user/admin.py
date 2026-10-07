from django.contrib import admin

from .models import Amistad, Preferencias


@admin.register(Amistad)
class AmistadAdmin(admin.ModelAdmin):
    list_display = ("de", "a", "aceptada", "creada")
    list_filter = ("aceptada",)
    search_fields = ("de__username", "a__username")


@admin.register(Preferencias)
class PreferenciasAdmin(admin.ModelAdmin):
    list_display = ("usuario", "fondo_nombre")
    search_fields = ("usuario__username",)
