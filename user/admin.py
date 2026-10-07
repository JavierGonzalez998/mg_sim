from django.contrib import admin

from .models import Amistad


@admin.register(Amistad)
class AmistadAdmin(admin.ModelAdmin):
    list_display = ("de", "a", "aceptada", "creada")
    list_filter = ("aceptada",)
    search_fields = ("de__username", "a__username")
