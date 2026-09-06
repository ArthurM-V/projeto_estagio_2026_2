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
    path(
        "painel/consultas/<int:consulta_id>/",
        views.consulta_administrativo_detail,
        name="consulta_administrativo_detail",
    ),
    path(
        "painel/consultas/<int:consulta_id>/excluir/",
        views.excluir_consulta,
        name="excluir_consulta",
    ),
    path("painel/medico/", views.medico_dashboard, name="medico_dashboard"),
    path(
        "painel/medico/consultas/<int:consulta_id>/",
        views.consulta_medico_detail,
        name="consulta_medico_detail",
    ),
    path(
        "painel/medico/consultas/<int:consulta_id>/exames/solicitar/",
        views.solicitar_exame,
        name="solicitar_exame",
    ),
    path(
        "painel/medico/consultas/<int:consulta_id>/receitas/emitir/",
        views.emitir_receita,
        name="emitir_receita",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("sessao-expirada/", views.session_expired_view, name="session_expired"),
]
