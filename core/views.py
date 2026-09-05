from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import AgendamentoConsultaForm, AtendimentoForm
from .models import Atendimento, Consulta, Especialidade, Medico, Paciente
from .scheduling import horarios_disponiveis


def home(request):
    """Exibe a página pública e processa solicitações de consulta."""
    especialidades = Especialidade.objects.all()

    if request.method == "POST":
        form = AgendamentoConsultaForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            data_horario = timezone.make_aware(
                datetime.combine(dados["data"], dados["horario"]),
                timezone.get_current_timezone(),
            )

            try:
                with transaction.atomic():
                    paciente, _ = Paciente.objects.get_or_create(
                        cpf=dados["cpf"],
                        defaults={
                            "nome": dados["nome"],
                            "email": dados["email"],
                            "telefone": dados["telefone"],
                            "data_nascimento": dados["data_nascimento"],
                        },
                    )
                    Consulta.objects.create(
                        paciente=paciente,
                        medico=dados["medico"],
                        data_horario=data_horario,
                        observacoes=dados["observacoes"],
                    )
            except IntegrityError:
                form.add_error(
                    None,
                    "Este horário acabou de ser reservado. Escolha outro horário.",
                )
            else:
                messages.success(
                    request,
                    "Solicitação enviada com sucesso! A clínica confirmará seu horário em breve.",
                )
                return redirect("home")
    else:
        form = AgendamentoConsultaForm()

    return render(
        request,
        "core/home.html",
        {
            "especialidades": especialidades,
            "form": form,
            "form_com_erros": request.method == "POST" and form.errors,
        },
    )


@require_GET
def horarios_disponiveis_view(request):
    """Fornece à página pública os horários livres de um médico."""
    medico_id = request.GET.get("medico")
    data_texto = request.GET.get("data")

    try:
        data_consulta = date.fromisoformat(data_texto)
    except (TypeError, ValueError):
        return JsonResponse({"horarios": []}, status=400)

    medico = get_object_or_404(Medico.objects.filter(ativo=True), pk=medico_id)
    horarios = horarios_disponiveis(medico, data_consulta)

    return JsonResponse(
        {"horarios": [horario.strftime("%H:%M") for horario in horarios]}
    )


def _obter_medico_ativo(usuario):
    """Retorna o médico associado a um usuário autorizado."""
    try:
        medico = usuario.medico
    except Medico.DoesNotExist:
        raise PermissionDenied("Seu usuário não possui acesso ao painel médico.")

    if not medico.ativo:
        raise PermissionDenied("O cadastro deste médico está inativo.")

    return medico


@login_required
def dashboard(request):
    """Encaminha cada perfil autenticado para o painel permitido."""
    if request.user.is_superuser:
        return _dashboard_administrativo(request)

    _obter_medico_ativo(request.user)

    return redirect("medico_dashboard")


def _dashboard_administrativo(request):
    """Exibe consultas e indicadores exclusivos do superadmin."""
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


@login_required
def medico_dashboard(request):
    """Exibe ao médico somente as consultas vinculadas ao seu usuário."""
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)

    consultas = (
        Consulta.objects.filter(medico=medico)
        .select_related("paciente", "atendimento")
        .order_by("data_horario")
    )

    return render(
        request,
        "core/medico_dashboard.html",
        {
            "medico": medico,
            "consultas": consultas,
            "consultas_hoje": consultas.filter(
                data_horario__date=timezone.localdate()
            ).count(),
            "pendentes": consultas.filter(status=Consulta.Status.PENDENTE).count(),
        },
    )


@login_required
def consulta_medico_detail(request, consulta_id):
    """Permite atendimento clínico apenas na consulta do médico logado."""
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        medico=medico,
    )

    try:
        atendimento = consulta.atendimento
    except Atendimento.DoesNotExist:
        atendimento = None

    if request.method == "POST":
        form = AtendimentoForm(request.POST, instance=atendimento)
        if form.is_valid():
            atendimento = form.save(commit=False)
            atendimento.consulta = consulta
            atendimento.save()
            messages.success(request, "Atendimento clínico salvo com sucesso.")
            return redirect("consulta_medico_detail", consulta_id=consulta.id)
    else:
        form = AtendimentoForm(instance=atendimento)

    return render(
        request,
        "core/consulta_medico_detail.html",
        {
            "consulta": consulta,
            "atendimento": atendimento,
            "form": form,
        },
    )

def session_expired_view(request):
    return render(request, "core/session_expired.html")
