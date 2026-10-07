import io
import json
from unittest.mock import patch

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from user.models import Amistad

from . import juego, views
from .models import Carta, Jugador, Mazo, Partida
from .routing import websocket_urlpatterns

MOXFIELD = {
    "name": "Mazo de prueba",
    "format": "commander",
    "boards": {
        "commanders": {"cards": {"a": {"quantity": 1, "card": {
            "name": "Krenko, Mob Boss", "type_line": "Legendary Creature — Goblin Warrior",
            "mana_cost": "{2}{R}{R}", "cmc": 4, "scryfall_id": "abcdef00-0000-0000-0000-000000000001"}}}},
        "mainboard": {"cards": {
            "b": {"quantity": 30, "card": {"name": "Mountain", "type_line": "Basic Land — Mountain",
                                          "cmc": 0, "scryfall_id": "abcdef00-0000-0000-0000-000000000002"}},
            "c": {"quantity": 1, "card": {"name": "Delver of Secrets // Insectile Aberration", "cmc": 1,
                                         "layout": "transform",
                                         "scryfall_id": "abcdef00-0000-0000-0000-000000000003",
                                         "card_faces": [{"type_line": "Creature — Human Wizard", "mana_cost": "{U}"}]}},
            "d": {"quantity": 1, "card": {"name": "Sol Ring", "type_line": "Artifact", "mana_cost": "{1}",
                                         "cmc": 1, "scryfall_id": "abcdef00-0000-0000-0000-000000000004"}},
        }},
        "sideboard": {"cards": {"e": {"quantity": 1, "card": {
            "name": "Pyroblast", "type_line": "Instant", "mana_cost": "{R}", "cmc": 1,
            "scryfall_id": "abcdef00-0000-0000-0000-000000000005"}}}},
    },
}


class MazoTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("ana", password="secreta123"))

    def test_landing(self):
        r = self.client.get("/")
        self.assertContains(r, 'id="sidebar" popover')
        self.assertContains(r, 'id="caracteristicas"')

    def test_url_invalida(self):
        r = self.client.post("/mazos/", {"url": "https://example.com/decks/x"})
        self.assertContains(r, "Debe ser un enlace de Moxfield")

    @patch("app.views.urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(MOXFIELD).encode()))
    def test_importar_organizar_y_jugar(self, mock):
        r = self.client.post("/mazos/", {"url": "https://moxfield.com/decks/AbC-12_x"})
        mazo = Mazo.objects.get()
        self.assertRedirects(r, f"/mazos/{mazo.pk}/")
        self.assertEqual(mazo.formato, "commander")
        delver = mazo.cartas.get(nombre__startswith="Delver")
        self.assertTrue(delver.imagen_reverso.startswith("https://cards.scryfall.io/normal/back/"))
        self.assertIn("/decks/all/AbC-12_x", mock.call_args.args[0].full_url)

        r = self.client.get(f"/mazos/{mazo.pk}/")
        self.assertEqual([(k, n) for k, _, n in r.context["grupos"]],
                         [("Comandante", 1), ("Criaturas", 1), ("Artefactos", 1), ("Tierras", 30), ("Banquillo", 1)])
        self.assertEqual(r.context["total"], 33)
        self.assertContains(r, "https://cards.scryfall.io/normal/front/a/b/abcdef00-0000-0000-0000-000000000004.jpg")

        datos = self.client.get(f"/test/?mazo={mazo.pk}").context["datos"]
        self.assertEqual(len(datos["principal"]), 32)
        self.assertEqual([c["nombre"] for c in datos["comandantes"]], ["Krenko, Mob Boss"])
        self.assertEqual(sum(c["tierra"] for c in datos["principal"]), 30)

    @patch("app.views.urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(MOXFIELD).encode()))
    def test_probar_con_url_no_guarda(self, mock):
        r = self.client.get("/test/", {"url": "https://moxfield.com/decks/AbC-12_x"})
        self.assertEqual(r.context["nombre"], "Mazo de prueba")
        self.assertEqual(len(r.context["datos"]["principal"]), 32)
        self.assertFalse(Mazo.objects.exists())

    def test_probar_selector_y_validacion(self):
        self.assertContains(self.client.get("/test/"), "Elige un mazo")
        self.assertContains(self.client.get("/test/", {"mazo": "", "url": ""}), "pero no ambos")

    def test_probar_protegido(self):
        self.client.logout()
        self.assertRedirects(self.client.get("/test/"), "/login/?next=/test/")

    def test_mazo_ajeno(self):
        otro = Mazo.objects.create(usuario=User.objects.create_user("bob"), nombre="x", moxfield_id="x")
        r = self.client.get("/test/", {"mazo": otro.pk})
        self.assertTemplateUsed(r, "app/probar.html")
        self.assertNotIn("datos", r.context)

    @patch("app.views.urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(MOXFIELD).encode()))
    def test_administrar_desde_perfil(self, mock):
        self.client.post("/mazos/", {"url": "https://moxfield.com/decks/AbC-12_x"})
        mazo = Mazo.objects.get()
        perfil = self.client.get("/user/")
        self.assertContains(perfil, 'id="mazos"')
        self.assertContains(perfil, ">33</td>")

        Carta.objects.filter(mazo=mazo).delete()
        r = self.client.post(f"/mazos/{mazo.pk}/actualizar/", {"next": "/user/"}, follow=True)
        self.assertRedirects(r, "/user/")
        self.assertContains(r, "se actualizó desde Moxfield")
        self.assertEqual(mazo.cartas.count(), 5)

        r = self.client.post(f"/mazos/{mazo.pk}/eliminar/", {"next": "https://malo.com/"})
        self.assertRedirects(r, "/mazos/")
        self.assertFalse(Mazo.objects.exists())

    def test_no_administrar_mazo_ajeno(self):
        otro = Mazo.objects.create(usuario=User.objects.create_user("bob"), nombre="x", moxfield_id="x")
        self.assertEqual(self.client.post(f"/mazos/{otro.pk}/eliminar/").status_code, 404)
        self.assertEqual(self.client.get(f"/mazos/{otro.pk}/eliminar/").status_code, 405)


def mazo_simple(n=40, comandantes=()):
    carta = lambda nombre: {"nombre": nombre, "imagen": None, "reverso": None, "tierra": False}
    return {"principal": [carta(f"Carta {k}") for k in range(n)], "comandantes": [carta(c) for c in comandantes]}


class JuegoTests(TestCase):
    """Lógica de la mesa (app/juego.py), sin HTTP."""

    def setUp(self):
        self.e = juego.crear([(1, "ana", mazo_simple(comandantes=["Krenko"])),
                              (2, "bob", mazo_simple(comandantes=["Tymna", "Thrasios"]))], "commander")
        self.ana = next(i for i, j in enumerate(self.e["jugadores"]) if j["nombre"] == "ana")
        self.bob = 1 - self.ana

    def zona(self, i, z):
        return self.e["jugadores"][i]["zonas"][z]

    def test_inicio(self):
        self.assertEqual(len(self.zona(self.ana, "mano")), 7)
        self.assertEqual(len(self.zona(self.ana, "biblioteca")), 33)
        self.assertEqual(self.e["jugadores"][self.ana]["vida"], 40)
        self.assertEqual(len(self.zona(self.ana, "mando")), 1)
        self.assertEqual(len(self.zona(self.bob, "mando")), 2)

    def test_informacion_oculta(self):
        v = juego.vista(self.e, self.ana)
        self.assertEqual(len(v["jugadores"][self.ana]["zonas"]["mano"]), 7)
        self.assertEqual(v["jugadores"][self.bob]["zonas"]["mano"], 7)
        self.assertEqual(v["jugadores"][self.bob]["zonas"]["biblioteca"], 33)
        self.assertNotIn("Carta", json.dumps(v["jugadores"][self.bob]["zonas"]))

        carta = self.zona(self.ana, "mano")[0]
        juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": carta, "zona": "campo", "boca_abajo": True})
        rival = juego.vista(self.e, self.bob)["jugadores"][self.ana]["zonas"]["campo"][0]
        self.assertTrue(rival["oculta"])
        self.assertNotIn("nombre", rival)
        self.assertNotIn(self.e["cartas"][carta]["nombre"], json.dumps(juego.vista(self.e, self.bob)["log"]))

    def test_no_tocar_mano_ajena(self):
        carta = self.zona(self.bob, "mano")[0]
        with self.assertRaises(juego.AccionInvalida):
            juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": carta, "zona": "cementerio"})

    def test_cambio_de_control_y_vuelta_al_dueno(self):
        carta = self.zona(self.bob, "mano")[0]
        juego.aplicar(self.e, self.bob, {"accion": "mover", "carta": carta, "zona": "campo"})
        juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": carta, "zona": "campo", "jugador": self.ana})
        self.assertIn(carta, self.zona(self.ana, "campo"))
        juego.aplicar(self.e, self.ana, {"accion": "girar", "carta": carta})
        juego.aplicar(self.e, self.ana, {"accion": "contador", "carta": carta, "tipo": "+1/+1", "delta": 2})
        juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": carta, "zona": "cementerio"})
        self.assertIn(carta, self.zona(self.bob, "cementerio"))  # al cementerio de su dueño
        self.assertEqual((self.e["cartas"][carta]["girada"], self.e["cartas"][carta]["contadores"]), (False, {}))

    def test_fichas_dejan_de_existir(self):
        juego.aplicar(self.e, self.ana, {"accion": "ficha", "nombre": "Goblin 1/1", "cantidad": 3})
        fichas = list(self.zona(self.ana, "campo"))
        self.assertEqual(len(fichas), 3)
        juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": fichas[0], "zona": "cementerio"})
        self.assertNotIn(fichas[0], self.e["cartas"])
        self.assertEqual(self.zona(self.ana, "cementerio"), [])

    def test_impuesto_de_comandante(self):
        cmdr = self.zona(self.ana, "mando")[0]
        for _ in range(2):
            juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": cmdr, "zona": "campo"})
            juego.aplicar(self.e, self.ana, {"accion": "mover", "carta": cmdr, "zona": "mando"})
        self.assertEqual(juego.vista(self.e, self.ana)["jugadores"][self.ana]["zonas"]["mando"][0]["impuesto"], 4)

    def test_dano_de_comandante_por_comandante(self):
        krenko = self.zona(self.ana, "mando")[0]
        juego.aplicar(self.e, self.ana, {"accion": "dano_comandante", "jugador": self.bob, "carta": krenko, "delta": 5})
        bob = self.e["jugadores"][self.bob]
        self.assertEqual((bob["dano_comandante"][krenko], bob["vida"]), (5, 35))

        # Los compañeros de bob llevan cuentas separadas contra ana
        tymna, thrasios = self.zona(self.bob, "mando")
        juego.aplicar(self.e, self.bob, {"accion": "dano_comandante", "jugador": self.ana, "carta": tymna, "delta": 21})
        juego.aplicar(self.e, self.bob, {"accion": "dano_comandante", "jugador": self.ana, "carta": thrasios, "delta": 3})
        ana = self.e["jugadores"][self.ana]
        self.assertEqual((ana["dano_comandante"], ana["vida"]), ({tymna: 21, thrasios: 3}, 16))
        self.assertIn("letal", self.e["log"][-2]["t"])
        self.assertEqual({c["nombre"] for c in juego.vista(self.e, self.ana)["comandantes"]},
                         {"Krenko", "Tymna", "Thrasios"})

        with self.assertRaises(juego.AccionInvalida):  # una carta cualquiera no hace daño de comandante
            juego.aplicar(self.e, self.ana, {"accion": "dano_comandante", "jugador": self.bob,
                                             "carta": self.zona(self.ana, "mano")[0], "delta": 1})

    def test_turnos_mirar_y_rendirse(self):
        activo = self.e["activo"]
        with self.assertRaises(juego.AccionInvalida):
            juego.aplicar(self.e, 1 - activo, {"accion": "pasar_turno"})
        juego.aplicar(self.e, activo, {"accion": "pasar_turno"})
        self.assertEqual((self.e["activo"], self.e["turno"]), (1 - activo, 2))
        self.assertEqual(len(self.zona(1 - activo, "mano")), 8)

        nuevo = self.e["activo"]
        privado = juego.aplicar(self.e, nuevo, {"accion": "mirar", "n": 3})
        self.assertEqual([c["id"] for c in privado["vistazo"]], self.zona(nuevo, "biblioteca")[:3])

        juego.aplicar(self.e, self.ana, {"accion": "rendirse"})
        self.assertEqual(self.e["ganador"], self.bob)
        with self.assertRaises(juego.AccionInvalida):
            juego.aplicar(self.e, self.bob, {"accion": "robar"})

    def test_prioridad_y_pila(self):
        activo, otro = self.e["activo"], 1 - self.e["activo"]
        juego.aplicar(self.e, otro, {"accion": "robar"})  # preparación: todos actúan (mulligans)
        juego.aplicar(self.e, activo, {"accion": "fase", "fase": "principal1"})
        with self.assertRaisesMessage(juego.AccionInvalida, "Responder"):
            juego.aplicar(self.e, otro, {"accion": "robar"})

        hechizo = self.zona(activo, "mano")[0]
        juego.aplicar(self.e, activo, {"accion": "mover", "carta": hechizo, "zona": "pila"})
        juego.aplicar(self.e, otro, {"accion": "responder"})
        with self.assertRaises(juego.AccionInvalida):  # ahora el activo espera
            juego.aplicar(self.e, activo, {"accion": "robar"})
        respuesta = self.zona(otro, "mano")[0]
        juego.aplicar(self.e, otro, {"accion": "mover", "carta": respuesta, "zona": "pila"})
        self.assertEqual(juego.vista(self.e, activo)["pila"][-1]["controlador"], otro)
        juego.aplicar(self.e, otro, {"accion": "pasar_prioridad"})
        self.assertEqual(juego.vista(self.e, activo)["prioridad"], activo)

        with self.assertRaisesMessage(juego.AccionInvalida, "pila"):
            juego.aplicar(self.e, activo, {"accion": "pasar_turno"})
        with self.assertRaisesMessage(juego.AccionInvalida, "arriba"):
            juego.aplicar(self.e, activo, {"accion": "mover", "carta": hechizo, "zona": "cementerio"})
        juego.aplicar(self.e, activo, {"accion": "mover", "carta": respuesta, "zona": "campo"})
        self.assertIn(respuesta, self.zona(otro, "campo"))  # resuelve en el campo de quien la lanzó
        juego.aplicar(self.e, activo, {"accion": "mover", "carta": hechizo, "zona": "cementerio"})
        juego.aplicar(self.e, activo, {"accion": "pasar_turno"})

    def test_tiempo_de_turno(self):
        activo = self.e["activo"]
        with self.assertRaisesMessage(juego.AccionInvalida, "tiempo"):
            juego.aplicar(self.e, 1 - activo, {"accion": "tiempo"})
        self.e["inicio_turno"] -= juego.DURACION_TURNO
        juego.aplicar(self.e, 1 - activo, {"accion": "tiempo"})
        self.assertEqual((self.e["activo"], self.e["turno"]), (1 - activo, 2))
        self.assertGreater(juego.vista(self.e, activo)["restante"], juego.DURACION_TURNO - 5)

    def test_mulligan(self):
        juego.aplicar(self.e, self.ana, {"accion": "mulligan"})
        self.assertEqual((len(self.zona(self.ana, "mano")), len(self.zona(self.ana, "biblioteca"))), (7, 33))
        self.assertEqual(self.e["jugadores"][self.ana]["mulligans"], 1)


class PartidaTests(TestCase):
    """Sala de espera e invitaciones (/game/)."""

    def setUp(self):
        self.ana = User.objects.create_user("ana")
        self.bob = User.objects.create_user("bob")
        self.eva = User.objects.create_user("eva")  # no es amiga de ana
        Amistad.objects.create(de=self.ana, a=self.bob, aceptada=True)
        self.mazos = {u: Mazo.objects.create(usuario=u, nombre=f"Mazo {u}", moxfield_id="x", formato="commander")
                      for u in (self.ana, self.bob)}
        for mazo in self.mazos.values():
            Carta.objects.create(mazo=mazo, zona="principal", cantidad=40, nombre="Mountain",
                                 tipo="Basic Land — Mountain", scryfall_id="abcdef00-0000-0000-0000-000000000002")

    def como(self, usuario):
        self.client.force_login(usuario)
        return self.client

    def test_flujo_completo(self):
        r = self.como(self.ana).post("/game/crear/")
        partida = Partida.objects.get()
        self.assertRedirects(r, f"/game/{partida.pk}/")

        self.assertContains(self.client.post(f"/game/{partida.pk}/invitar/", {"username": "eva"}, follow=True),
                            "Solo puedes invitar a tus amigos.")
        self.client.post(f"/game/{partida.pk}/invitar/", {"username": "bob"})
        self.client.post(f"/game/{partida.pk}/mazo/", {"mazo": self.mazos[self.ana].pk, "url": ""})
        self.assertContains(self.client.post(f"/game/{partida.pk}/iniciar/", follow=True), "entre 2 y 5")

        # bob ve la notificación, se une y elige mazo
        self.assertContains(self.como(self.bob).get("/"), "ana te invitó a una partida")
        self.client.post(f"/game/{partida.pk}/unirse/")
        self.client.post(f"/game/{partida.pk}/mazo/", {"mazo": self.mazos[self.bob].pk, "url": ""})
        self.assertEqual(self.client.post(f"/game/{partida.pk}/iniciar/").status_code, 302)
        self.assertEqual(Partida.objects.get().estado, "sala")  # bob no es el anfitrión

        version = Partida.objects.get().version
        self.como(self.ana).post(f"/game/{partida.pk}/iniciar/")
        partida.refresh_from_db()
        self.assertEqual(partida.estado, "jugando")
        self.assertContains(self.client.get(f"/game/{partida.pk}/"), "/static/app/partida.js")

        estado = self.client.get(f"/game/{partida.pk}/estado/").json()
        self.assertGreater(estado["version"], version)
        self.assertEqual(len(estado["mesa"]["jugadores"]), 2)

        r = self.client.post(f"/game/{partida.pk}/accion/", {"accion": "dado", "caras": 20},
                             content_type="application/json")
        self.assertIn("tiró un d20", r.json()["mesa"]["log"][-1]["t"])
        r = self.client.post(f"/game/{partida.pk}/accion/", {"accion": "inventada"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

        self.assertEqual(self.como(self.eva).get(f"/game/{partida.pk}/estado/").status_code, 404)

    def test_formato_distinto(self):
        self.mazos[self.bob].formato = "modern"
        self.mazos[self.bob].save()
        partida = Partida.objects.create(anfitrion=self.ana, formato="commander")
        Jugador.objects.create(partida=partida, usuario=self.ana, aceptada=True, mazo_nombre="x", formato="commander",
                               cartas=mazo_simple())
        Jugador.objects.create(partida=partida, usuario=self.bob, aceptada=True)
        r = self.como(self.bob).post(f"/game/{partida.pk}/mazo/", {"mazo": self.mazos[self.bob].pk, "url": ""},
                                     follow=True)
        self.assertContains(r, "formato «commander»")
        self.assertEqual(partida.jugadores.get(usuario=self.bob).mazo_nombre, "")

    def test_maximo_cinco(self):
        partida = Partida.objects.create(anfitrion=self.ana)
        Jugador.objects.create(partida=partida, usuario=self.ana, aceptada=True)
        for k in range(4):
            Jugador.objects.create(partida=partida, usuario=User.objects.create_user(f"x{k}"))
        r = self.como(self.ana).post(f"/game/{partida.pk}/invitar/", {"username": "bob"}, follow=True)
        self.assertContains(r, "Máximo 5 jugadores")

    def test_anfitrion_cancela(self):
        self.como(self.ana).post("/game/crear/")
        partida = Partida.objects.get()
        self.client.post(f"/game/{partida.pk}/salir/")
        self.assertFalse(Partida.objects.exists())

    def test_protegido(self):
        self.assertRedirects(self.client.get("/game/"), "/login/?next=/game/")


class WebsocketTests(TestCase):
    """La mesa se empuja por WebSocket a cada jugador, cada uno con su vista."""

    def setUp(self):
        self.ana = User.objects.create_user("ana")
        self.bob = User.objects.create_user("bob")
        self.eva = User.objects.create_user("eva")
        self.partida = Partida.objects.create(anfitrion=self.ana, estado="jugando", formato="commander",
                                              juego=juego.crear([(self.ana.pk, "ana", mazo_simple()),
                                                                 (self.bob.pk, "bob", mazo_simple())], "commander"))
        for u in (self.ana, self.bob):
            Jugador.objects.create(partida=self.partida, usuario=u, aceptada=True)

    async def conectar(self, usuario):
        com = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/game/{self.partida.pk}/")
        com.scope["user"] = usuario
        conectado, _ = await com.connect()
        return com, conectado

    async def test_empuja_cambios_a_cada_jugador(self):
        bob, conectado = await self.conectar(self.bob)
        self.assertTrue(conectado)
        inicial = await bob.receive_json_from()
        yo = inicial["mesa"]["yo"]
        self.assertEqual(len(inicial["mesa"]["jugadores"][yo]["zonas"]["mano"]), 7)
        self.assertEqual(inicial["mesa"]["jugadores"][1 - yo]["zonas"]["mano"], 7)  # la de ana, solo cantidad

        await self.async_client.aforce_login(self.ana)
        r = await self.async_client.post(f"/game/{self.partida.pk}/accion/", {"accion": "moneda"},
                                         content_type="application/json")
        self.assertEqual(r.status_code, 200)
        aviso = await bob.receive_json_from()
        self.assertEqual(aviso["version"], inicial["version"] + 1)
        self.assertIn("ana lanzó una moneda", aviso["mesa"]["log"][-1]["t"])
        await bob.disconnect()

    async def test_rechaza_a_quien_no_juega(self):
        _, conectado = await self.conectar(self.eva)
        self.assertFalse(conectado)


class ConfigMysqlTests(TestCase):
    """main.settings.config_mysql con las variables de docker compose y de Railway."""

    def config(self, **env):
        from unittest.mock import patch as parchear

        from main.settings import config_mysql
        with parchear.dict("os.environ", env, clear=True):
            return config_mysql()

    def test_variantes(self):
        self.assertIsNone(self.config())
        compose = self.config(MYSQL_DATABASE="mg", MYSQL_USER="u", MYSQL_PASSWORD="p", MYSQL_HOST="db")
        self.assertEqual((compose["HOST"], compose["NAME"], compose["PORT"]), ("db", "mg", "3306"))
        railway = self.config(MYSQL_DATABASE="railway", MYSQLHOST="mysql.railway.internal", MYSQLUSER="root",
                              MYSQLPASSWORD="p", MYSQLPORT="3306")
        self.assertEqual((railway["HOST"], railway["USER"]), ("mysql.railway.internal", "root"))
        url = self.config(MYSQL_URL="mysql://root:p%40ss@mysql.railway.internal:3306/railway", MYSQL_DATABASE="otra")
        self.assertEqual((url["HOST"], url["NAME"], url["PASSWORD"]), ("mysql.railway.internal", "railway", "p@ss"))

    def test_sin_host_avisa(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaisesMessage(ImproperlyConfigured, "MYSQL_URL"):
            self.config(MYSQL_DATABASE="railway", MYSQL_ROOT_PASSWORD="x")


class MovilTests(TestCase):
    def test_tablero_con_aviso_tactil(self):
        self.client.force_login(User.objects.create_user("ana"))
        for url in ("/test/", "/game/"):
            self.assertContains(self.client.get(url), 'class="solo-pc"')
        self.assertNotContains(self.client.get("/mazos/"), "aviso-tactil")


CHANGELOG = """# Changelog

## [0.2.0] - 2026-10-08

### Añadido

- **Pila** de hechizos con `prioridad` y una línea
  larga que sigue.
- Partidas:
  - Sub <b>cambio</b>.

## [0.1.0] - 2026-10-07

### Corregido

- Arreglo.

[0.2.0]: https://github.com/x/compare
"""


class VersionesTests(TestCase):
    def test_leer_changelog(self):
        v = views.leer_changelog(CHANGELOG)
        self.assertEqual([(x["version"], str(x["fecha"])) for x in v], [("0.2.0", "2026-10-08"), ("0.1.0", "2026-10-07")])
        cambios = v[0]["secciones"][0]["cambios"]
        self.assertEqual(v[0]["secciones"][0]["titulo"], "Añadido")
        self.assertEqual(cambios[0]["texto"],
                         "<strong>Pila</strong> de hechizos con <code>prioridad</code> y una línea larga que sigue.")
        self.assertEqual(cambios[1]["sub"][0]["texto"], "Sub &lt;b&gt;cambio&lt;/b&gt;.")  # el HTML se escapa
        self.assertEqual(v[1]["secciones"][0]["cambios"][0]["texto"], "Arreglo.")

    def test_portada_muestra_el_changelog_del_proyecto(self):
        version = views.leer_changelog((settings.BASE_DIR / "CHANGELOG.md").read_text(encoding="utf-8"))[0]["version"]
        self.assertContains(self.client.get("/"), f"v{version}")


class NotificacionesTests(TestCase):
    def test_invitaciones_y_solicitudes_en_la_barra(self):
        ana, bob, eva = (User.objects.create_user(n) for n in ("ana", "bob", "eva"))
        Amistad.objects.create(de=eva, a=ana)
        partida = Partida.objects.create(anfitrion=bob, formato="commander")
        Jugador.objects.create(partida=partida, usuario=ana)
        self.client.force_login(ana)
        r = self.client.get("/mazos/")
        self.assertContains(r, 'aria-label="Notificaciones (2)"')
        self.assertContains(r, "bob te invitó a una partida")
        self.assertContains(r, f'/user/amigos/{Amistad.objects.get().pk}/aceptar/')
