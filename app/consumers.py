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
