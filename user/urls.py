from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="user/login.html"), name="login"),
    path("login/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("registro/", views.registro, name="registro"),
    path("user/", views.perfil, name="perfil"),
    path("user/amigos/buscar/", views.buscar_usuarios, name="buscar_usuarios"),
    path("user/amigos/solicitar/", views.enviar_solicitud, name="enviar_solicitud"),
    path("user/amigos/<int:pk>/aceptar/", views.aceptar_solicitud, name="aceptar_solicitud"),
    path("user/amigos/<int:pk>/eliminar/", views.eliminar_amistad, name="eliminar_amistad"),
    # Va al final y con un solo segmento para no chocar con las rutas de arriba
    path("user/<str:username>/", views.ver_perfil, name="ver_perfil"),
]
