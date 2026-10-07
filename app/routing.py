from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/game/<int:pk>/", consumers.PartidaConsumer.as_asgi()),
    path("ws/notificaciones/", consumers.NotificacionesConsumer.as_asgi()),
]
