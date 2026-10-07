from django.conf import settings
from django.db import models


class Amistad(models.Model):
    """Solicitud de amistad de `de` a `a`; al aceptarse, ambos son amigos."""
    de = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitudes_enviadas")
    a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitudes_recibidas")
    aceptada = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["de", "a"], name="amistad_unica"),
            models.CheckConstraint(condition=~models.Q(de=models.F("a")), name="amistad_no_consigo_mismo"),
        ]

    def __str__(self):
        return f"{self.de} → {self.a}{'' if self.aceptada else ' (pendiente)'}"

    @classmethod
    def de_usuario(cls, usuario):
        return cls.objects.filter(models.Q(de=usuario) | models.Q(a=usuario))

    @classmethod
    def entre(cls, u1, u2):
        return cls.objects.filter(models.Q(de=u1, a=u2) | models.Q(de=u2, a=u1)).first()

    def otro(self, usuario):
        return self.a if self.de == usuario else self.de
