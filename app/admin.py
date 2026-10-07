from django.contrib import admin

from .models import Carta, Jugador, Mazo, Partida


class CartaInline(admin.TabularInline):
    model = Carta
    extra = 0
    fields = ("cantidad", "nombre", "zona", "tipo", "coste", "doble_cara")


@admin.register(Mazo)
class MazoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "usuario", "formato", "creado")
    list_filter = ("formato",)
    search_fields = ("nombre", "usuario__username")
    inlines = [CartaInline]


class JugadorInline(admin.TabularInline):
    model = Jugador
    extra = 0
    fields = ("usuario", "aceptada", "mazo_nombre", "formato")


@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ("pk", "anfitrion", "estado", "formato", "creada")
    list_filter = ("estado", "formato")
    search_fields = ("anfitrion__username",)
    readonly_fields = ("juego", "version")
    inlines = [JugadorInline]
