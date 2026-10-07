import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from app.models import Jugador, Partida


class SidebarTests(TestCase):
    def test_sidebar_en_todas_las_paginas(self):
        for url in ("/", "/login/", "/registro/"):
            r = self.client.get(url)
            self.assertContains(r, 'id="sidebar" popover', msg_prefix=url)
            self.assertContains(r, "Registrarse", msg_prefix=url)


class PanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("jefe", password="x")
        self.ana = User.objects.create_user("ana", email="ana@example.com")

    def test_solo_superusuario(self):
        self.assertRedirects(self.client.get("/manage/"), "/login/?next=/manage/")
        staff = User.objects.create_user("staff", is_staff=True)
        for u in (self.ana, staff):
            self.client.force_login(u)
            self.assertEqual(self.client.get("/manage/").status_code, 403)
            self.assertEqual(self.client.post(f"/manage/usuarios/{self.ana.pk}/activo/").status_code, 403)
            self.assertNotContains(self.client.get("/"), "Panel de administración")

        self.client.force_login(self.admin)
        r = self.client.get("/manage/")
        self.assertContains(r, "ana@example.com")
        self.assertContains(self.client.get("/"), "Panel de administración")

    def test_buscar_y_desactivar_usuario(self):
        self.client.force_login(self.admin)
        r = self.client.get("/manage/", {"q": "ana"})
        self.assertEqual([u.username for u in r.context["usuarios"]], ["ana"])

        self.client.post(f"/manage/usuarios/{self.ana.pk}/activo/")
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_active)

        r = self.client.post(f"/manage/usuarios/{self.admin.pk}/activo/", follow=True)
        self.assertContains(r, "No puedes desactivar tu propia cuenta.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_eliminar_partida(self):
        partida = Partida.objects.create(anfitrion=self.ana)
        Jugador.objects.create(partida=partida, usuario=self.ana, aceptada=True)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/manage/"), f"/manage/partidas/{partida.pk}/eliminar/")
        self.client.post(f"/manage/partidas/{partida.pk}/eliminar/")
        self.assertFalse(Partida.objects.exists())
        self.assertEqual(self.client.get(f"/admin/app/partida/").status_code, 200)


class PublicarVersionTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("jefe", password="x"))

    def test_sin_token(self):
        with self.settings(GITHUB_TOKEN=""):
            self.assertContains(self.client.get("/manage/"), "define <code>GITHUB_TOKEN</code>")

    @patch("app.views.urlopen")
    def test_publica_release(self, urlopen):
        urlopen.return_value = io.BytesIO(json.dumps({"tag_name": "v1.0.0"}).encode())
        cache.set("versiones", {"cambios": []})
        with self.settings(GITHUB_TOKEN="t"):
            r = self.client.post("/manage/versiones/publicar/", {"etiqueta": "v1.0.0", "titulo": "", "notas": "Pila"})
        self.assertRedirects(r, "/manage/")
        req = urlopen.call_args.args[0]
        self.assertEqual((req.get_method(), req.full_url), ("POST", "https://api.github.com/repos/JavierGonzalez998/mg_sim/releases"))
        self.assertEqual(json.loads(req.data), {"tag_name": "v1.0.0", "name": "v1.0.0", "body": "Pila"})
        self.assertIsNone(cache.get("versiones"))

    @patch("app.views.urlopen", side_effect=HTTPError("u", 422, "x", {}, None))
    def test_version_repetida_conserva_el_formulario(self, urlopen):
        with self.settings(GITHUB_TOKEN="t"):
            r = self.client.post("/manage/versiones/publicar/", {"etiqueta": "v1.0.0", "notas": "Mis notas"})
        self.assertContains(r, "ya existe en GitHub")
        self.assertContains(r, "Mis notas")

    def test_etiqueta_invalida(self):
        with self.settings(GITHUB_TOKEN="t"):
            self.assertContains(self.client.post("/manage/versiones/publicar/", {"etiqueta": "uno"}), "v1.2.0")
