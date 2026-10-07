from django.contrib.auth.models import User
from django.test import TestCase

from .models import Amistad, Preferencias


class LoginTests(TestCase):
    def test_login_flow(self):
        self.assertRedirects(self.client.get("/user/"), "/login/?next=/user/")
        User.objects.create_user("ana", email="ana@example.com", password="secreta123")
        bad = self.client.post("/login/", {"username": "ana", "password": "mal"})
        self.assertEqual(bad.status_code, 200)
        ok = self.client.post("/login/", {"username": "ana", "password": "secreta123"})
        self.assertRedirects(ok, "/user/")
        perfil = self.client.get("/user/")
        self.assertContains(perfil, "ana@example.com")
        self.assertContains(perfil, 'id="sidebar" popover')
        self.assertNotContains(perfil, "Administración")
        self.assertRedirects(self.client.post("/login/logout/"), "/login/")

    def test_registro(self):
        datos = {"username": "luis", "email": "luis@example.com", "password1": "Clave-larga-9", "password2": "Clave-larga-9"}
        self.assertRedirects(self.client.post("/registro/", datos), "/user/")
        self.assertContains(self.client.get("/user/"), "luis@example.com")
        self.client.post("/login/logout/")
        repetido = self.client.post("/registro/", {**datos, "username": "otro", "email": "LUIS@example.com"})
        self.assertContains(repetido, "Ya existe una cuenta con este correo.")
        sin_correo = self.client.post("/registro/", {**datos, "username": "otro", "email": ""})
        self.assertEqual(sin_correo.status_code, 200)
        bad = self.client.post("/registro/", {"username": "luis", "password1": "x", "password2": "y"})
        self.assertEqual(bad.status_code, 200)

    def test_solicitudes_de_amistad(self):
        ana = User.objects.create_user("ana", password="secreta123")
        bob = User.objects.create_user("bob")
        User.objects.create_user("buscar")  # no debe chocar con /user/amigos/buscar/
        self.client.force_login(ana)

        self.assertRedirects(self.client.get("/user/ana/"), "/user/")
        self.assertContains(self.client.get("/user/buscar/"), "Enviar solicitud")
        self.assertContains(self.client.get("/user/amigos/buscar/", {"q": "BO"}), "/user/bob/")
        self.assertEqual(self.client.get("/user/nadie/").status_code, 404)

        r = self.client.post("/user/amigos/solicitar/", {"username": "bob", "next": "/user/bob/"}, follow=True)
        self.assertRedirects(r, "/user/bob/")
        self.assertContains(r, "Solicitud enviada.")
        self.assertContains(self.client.post("/user/amigos/solicitar/", {"username": "bob"}, follow=True),
                            "Ya existe una solicitud")
        self.assertContains(self.client.post("/user/amigos/solicitar/", {"username": "ana"}, follow=True),
                            "a ti mismo")

        amistad = Amistad.objects.get()
        self.assertEqual(self.client.post(f"/user/amigos/{amistad.pk}/aceptar/").status_code, 404)  # ana no puede aceptar la suya

        self.client.force_login(bob)
        perfil = self.client.get("/user/")
        self.assertEqual(perfil.context["recibidas"], [amistad])
        self.client.post(f"/user/amigos/{amistad.pk}/aceptar/")
        self.assertEqual(self.client.get("/user/").context["amigos"], [(amistad, ana)])
        self.assertContains(self.client.get("/user/ana/"), "Son amigos.")

        self.client.post(f"/user/amigos/{amistad.pk}/eliminar/")
        self.assertFalse(Amistad.objects.exists())

    def test_solicitud_cruzada_se_acepta(self):
        ana = User.objects.create_user("ana")
        bob = User.objects.create_user("bob")
        Amistad.objects.create(de=bob, a=ana)
        self.client.force_login(ana)
        self.client.post("/user/amigos/solicitar/", {"username": "bob"})
        self.assertTrue(Amistad.objects.get().aceptada)

    def test_no_tocar_amistad_ajena(self):
        a, b, c = (User.objects.create_user(n) for n in "abc")
        amistad = Amistad.objects.create(de=a, a=b)
        self.client.force_login(c)
        self.assertEqual(self.client.post(f"/user/amigos/{amistad.pk}/eliminar/").status_code, 404)


class FondoTests(TestCase):
    """Fondo de la zona del jugador en la mesa: un arte de carta de Scryfall elegido en el perfil."""

    ARTE = "https://cards.scryfall.io/art_crop/front/4/9/4955a28b-4e5f-4cfd-9a1b-3c2b0e5d7a10.jpg?1562910012"

    def setUp(self):
        self.ana = User.objects.create_user("ana")
        self.client.force_login(self.ana)

    def test_elegir_y_quitar(self):
        self.client.post("/user/fondo/", {"fondo": self.ARTE, "nombre": "Krenko, Mob Boss · Dominaria · artista"})
        self.assertEqual(Preferencias.objects.get(usuario=self.ana).fondo, self.ARTE)
        perfil = self.client.get("/user/")
        self.assertContains(perfil, self.ARTE)
        self.assertContains(perfil, "Krenko, Mob Boss")
        self.client.post("/user/fondo/", {"fondo": ""})
        self.assertEqual(Preferencias.objects.get(usuario=self.ana).fondo, "")

    def test_solo_artes_de_scryfall(self):
        for url in ("https://ejemplo.com/imagen.jpg", "javascript:alert(1)",
                    "https://cards.scryfall.io/normal/front/4/9/4955a28b-4e5f-4cfd-9a1b-3c2b0e5d7a10.jpg",
                    self.ARTE + "');background:red"):
            self.assertContains(self.client.post("/user/fondo/", {"fondo": url}, follow=True), "Elige uno de los artes")
        self.assertFalse(Preferencias.objects.exclude(fondo="").exists())

    def test_se_ve_en_la_mesa(self):
        from app import juego
        from app.models import Jugador, Partida
        Preferencias.objects.create(usuario=self.ana, fondo=self.ARTE)
        bob = User.objects.create_user("bob")
        carta = {"nombre": "C", "imagen": None, "reverso": None, "tierra": False}
        mazo = {"principal": [carta] * 40, "comandantes": []}
        partida = Partida.objects.create(anfitrion=self.ana, estado="jugando",
                                         juego=juego.crear([(self.ana.pk, "ana", mazo), (bob.pk, "bob", mazo)], ""))
        for u in (self.ana, bob):
            Jugador.objects.create(partida=partida, usuario=u, aceptada=True)
        self.client.force_login(bob)  # bob también ve el fondo de ana
        r = self.client.get(f"/game/{partida.pk}/")
        self.assertContains(r, f'<script id="fondos" type="application/json">{{"{self.ana.pk}": "{self.ARTE}"}}</script>', html=False)
