from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "horarios-disponiveis/",
        views.horarios_disponiveis_view,
        name="horarios_disponiveis",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path("painel/", views.dashboard, name="dashboard"),
    path("painel/medico/", views.medico_dashboard, name="medico_dashboard"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("sessao-expirada/", views.session_expired_view, name="session_expired"),
]
