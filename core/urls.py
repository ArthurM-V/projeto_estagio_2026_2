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
    path("painel/medicos/cadastrar/", views.cadastrar_medico, name="cadastrar_medico"),
    path("painel/medicos/<int:medico_id>/", views.medico_administrativo_detail, name="medico_administrativo_detail"),
    path("painel/medicos/<int:medico_id>/redefinir-senha/", views.redefinir_senha_medico, name="redefinir_senha_medico"),
    path(
        "painel/consultas/lista/",
        views.consultas_filtradas,
        name="consultas_filtradas",
    ),
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
        "painel/medico/consultas/lista/",
        views.consultas_medico_filtradas,
        name="consultas_medico_filtradas",
    ),
    path(
        "painel/medico/consultas/<int:consulta_id>/",
        views.consulta_medico_detail,
        name="consulta_medico_detail",
    ),
    path(
        "painel/medico/consultas/<int:consulta_id>/prontuario/",
        views.salvar_prontuario,
        name="salvar_prontuario",
    ),
    path(
        "painel/medico/consultas/<int:consulta_id>/concluir/",
        views.concluir_consulta_medico,
        name="concluir_consulta_medico",
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
