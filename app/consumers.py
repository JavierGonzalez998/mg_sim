from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .views import estado_para


class PartidaConsumer(AsyncJsonWebsocketConsumer):
    """Envía a cada jugador su vista de la partida al conectarse y cada vez que algo cambia.

    Las acciones se siguen enviando por POST (/game/<id>/accion/); aquí solo se empujan los cambios.
    """

    async def connect(self):
        self.pk = self.scope["url_route"]["kwargs"]["pk"]
        self.grupo = f"partida_{self.pk}"
        if not self.scope["user"].is_authenticated or not await self.estado():
            await self.close()
            return
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()
        await self.partida_cambio()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def partida_cambio(self, event=None):
        datos = await self.estado()
        await self.send_json(datos or {"eliminada": True})
        if not datos:
            await self.close()

    @database_sync_to_async
    def estado(self):
        return estado_para(self.pk, self.scope["user"])


class NotificacionesConsumer(AsyncJsonWebsocketConsumer):
    """Avisa al usuario cuando cambian sus invitaciones o solicitudes (ver avisar_notificaciones en models.py).

    Solo manda el aviso; el navegador pide el panel ya renderizado a /notificaciones/.
    """

    async def connect(self):
        usuario = self.scope["user"]
        if not usuario.is_authenticated:
            await self.close()
            return
        self.grupo = f"usuario_{usuario.pk}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "grupo"):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def notificaciones_cambio(self, event):
        await self.send_json({"notificaciones": True})
