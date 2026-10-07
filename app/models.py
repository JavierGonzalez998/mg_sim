from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import models

# Orden en que se muestran los grupos del mazo; el primer tipo que coincida gana
# (así "Artifact Creature" cuenta como criatura y "Artifact Land" como tierra).
TIPOS = [
    ("Planeswalker", "Planeswalkers"),
    ("Battle", "Batallas"),
    ("Creature", "Criaturas"),
    ("Land", "Tierras"),
    ("Instant", "Instantáneos"),
    ("Sorcery", "Conjuros"),
    ("Artifact", "Artefactos"),
    ("Enchantment", "Encantamientos"),
]
ORDEN_CATEGORIAS = ["Comandante", "Planeswalkers", "Batallas", "Criaturas", "Instantáneos",
                    "Conjuros", "Artefactos", "Encantamientos", "Tierras", "Otros", "Banquillo"]


class Mazo(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mazos")
    nombre = models.CharField(max_length=200)
    moxfield_id = models.CharField(max_length=64)
    formato = models.CharField(max_length=40, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Carta(models.Model):
    ZONAS = [("comandante", "Comandante"), ("principal", "Principal"), ("banquillo", "Banquillo")]

    mazo = models.ForeignKey(Mazo, on_delete=models.CASCADE, related_name="cartas")
    zona = models.CharField(max_length=10, choices=ZONAS)
    cantidad = models.PositiveSmallIntegerField()
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=200)
    coste = models.CharField(max_length=100, blank=True)
    cmc = models.FloatField(default=0)
    scryfall_id = models.CharField(max_length=36)
    doble_cara = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cantidad} {self.nombre}"

    def _imagen(self, cara):
        s = self.scryfall_id
        return f"https://cards.scryfall.io/normal/{cara}/{s[0]}/{s[1]}/{s}.jpg"

    @property
    def imagen(self):
        return self._imagen("front")

    @property
    def imagen_reverso(self):
        return self._imagen("back") if self.doble_cara else None

    @property
    def categoria(self):
        if self.zona != "principal":
            return self.get_zona_display()
        return next((c for t, c in TIPOS if t in self.tipo), "Otros")


def avisar_cambio(partida_id):
    """Avisa a los conectados por WebSocket (app/consumers.py) para que cada uno pida su vista."""
    async_to_sync(get_channel_layer().group_send)(f"partida_{partida_id}", {"type": "partida.cambio"})


class Partida(models.Model):
    ESTADOS = [("sala", "En sala de espera"), ("jugando", "En juego"), ("terminada", "Terminada")]
    MIN_JUGADORES, MAX_JUGADORES = 2, 5

    anfitrion = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="partidas_creadas")
    estado = models.CharField(max_length=10, choices=ESTADOS, default="sala")
    formato = models.CharField(max_length=40, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    # Estado completo de la mesa (ver app/juego.py). `version` sube con cada cambio:
    # sirve para que los clientes sepan si hay novedades y para no pisar escrituras simultáneas.
    juego = models.JSONField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Partida {self.pk} de {self.anfitrion}"

    def tocar(self):
        Partida.objects.filter(pk=self.pk).update(version=models.F("version") + 1)
        avisar_cambio(self.pk)

    def problemas_para_iniciar(self):
        unidos = [j for j in self.jugadores.all() if j.aceptada]
        problemas = []
        if not self.MIN_JUGADORES <= len(unidos) <= self.MAX_JUGADORES:
            problemas.append(f"Se necesitan entre {self.MIN_JUGADORES} y {self.MAX_JUGADORES} jugadores unidos.")
        if any(not j.mazo_nombre for j in unidos):
            problemas.append("Todos los jugadores deben elegir un mazo.")
        elif len({j.formato for j in unidos}) > 1:
            problemas.append("Todos los mazos deben ser del mismo formato que el del anfitrión.")
        return problemas


class Jugador(models.Model):
    """Un usuario en una partida. Mientras `aceptada` es False, es una invitación pendiente."""
    partida = models.ForeignKey(Partida, on_delete=models.CASCADE, related_name="jugadores")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participaciones")
    aceptada = models.BooleanField(default=False)
    mazo_nombre = models.CharField(max_length=200, blank=True)
    formato = models.CharField(max_length=40, blank=True)
    # Copia del mazo al elegirlo ({"principal": [...], "comandantes": [...]}), así sirve igual
    # para mazos guardados que para enlaces de Moxfield sin guardar.
    cartas = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["partida", "usuario"], name="jugador_unico")]

    def __str__(self):
        return f"{self.usuario} en {self.partida}"
