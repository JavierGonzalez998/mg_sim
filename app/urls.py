from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("versiones/", views.versiones, name="versiones"),
    path("mazos/", views.mazos, name="mazos"),
    path("mazos/<int:pk>/", views.mazo, name="mazo"),
    path("mazos/<int:pk>/actualizar/", views.actualizar_mazo, name="actualizar_mazo"),
    path("mazos/<int:pk>/eliminar/", views.eliminar_mazo, name="eliminar_mazo"),
    path("test/", views.probar, name="probar"),
    path("game/", views.partidas, name="partidas"),
    path("game/crear/", views.crear_partida, name="crear_partida"),
    path("game/<int:pk>/", views.sala, name="sala"),
    path("game/<int:pk>/invitar/", views.invitar, name="invitar"),
    path("game/<int:pk>/unirse/", views.unirse, name="unirse"),
    path("game/<int:pk>/salir/", views.salir, name="salir"),
    path("game/<int:pk>/mazo/", views.elegir_mazo, name="elegir_mazo"),
    path("game/<int:pk>/iniciar/", views.iniciar, name="iniciar"),
    path("game/<int:pk>/estado/", views.estado_partida, name="estado_partida"),
    path("game/<int:pk>/accion/", views.accion_partida, name="accion_partida"),
]
