from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import Consulta, Especialidade, Medico


def home(request):
    """Exibe a página pública da clínica."""
    especialidades = Especialidade.objects.all()
    medicos = Medico.objects.filter(ativo=True).select_related("especialidade")

    return render(
        request,
        "core/home.html",
        {
            "especialidades": especialidades,
            "medicos": medicos,
        },
    )


@login_required
def dashboard(request):
    """Exibe consultas e indicadores para a equipe administrativa."""
    consultas_base = Consulta.objects.select_related(
        "paciente",
        "medico",
        "medico__especialidade",
    ).order_by("data_horario")

    status_atual = request.GET.get("status", "")
    status_validos = {valor for valor, _ in Consulta.Status.choices}
    consultas = consultas_base

    if status_atual in status_validos:
        consultas = consultas.filter(status=status_atual)
    else:
        status_atual = ""

    return render(
        request,
        "core/dashboard.html",
        {
            "consultas": consultas,
            "status_atual": status_atual,
            "status_choices": Consulta.Status.choices,
            "total_consultas": consultas_base.count(),
            "pendentes": consultas_base.filter(
                status=Consulta.Status.PENDENTE
            ).count(),
            "confirmadas": consultas_base.filter(
                status=Consulta.Status.CONFIRMADA
            ).count(),
            "consultas_hoje": consultas_base.filter(
                data_horario__date=timezone.localdate()
            ).count(),
        },
    )
