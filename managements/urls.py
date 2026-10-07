from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("usuarios/<int:pk>/activo/", views.cambiar_activo, name="cambiar_activo"),
    path("partidas/<int:pk>/eliminar/", views.eliminar_partida, name="eliminar_partida"),
]
