from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AgendamentoConsultaForm,
    AtendimentoForm,
    ConsultaAdministrativaForm,
    ConsultaStatusForm,
    ReceitaForm,
    ReceitaMedicamentoFormSet,
    SolicitacaoExameForm,
)
from .models import Atendimento, Consulta, Especialidade, Medico, Paciente, Receita
from .scheduling import horarios_disponiveis


def home(request):
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
    medico_id = request.GET.get("medico")
    data_texto = request.GET.get("data")

    try:
        data_consulta = date.fromisoformat(data_texto)
    except (TypeError, ValueError):
        return JsonResponse({"horarios": []}, status=400)

    medico = get_object_or_404(Medico.objects.filter(ativo=True), pk=medico_id)
    consulta_excluida_id = None
    consulta_id = request.GET.get("consulta")
    if request.user.is_authenticated and request.user.is_superuser and consulta_id:
        consulta_excluida_id = Consulta.objects.filter(
            pk=consulta_id,
            medico=medico,
        ).values_list("pk", flat=True).first()

    horarios = horarios_disponiveis(medico, data_consulta, consulta_excluida_id)

    return JsonResponse(
        {"horarios": [horario.strftime("%H:%M") for horario in horarios]}
    )


def _obter_medico_ativo(usuario):
    try:
        medico = usuario.medico
    except Medico.DoesNotExist:
        raise PermissionDenied("Seu usuário não possui acesso ao painel médico.")

    if not medico.ativo:
        raise PermissionDenied("O cadastro deste médico está inativo.")

    return medico


def _obter_atendimento(consulta):
    try:
        return consulta.atendimento
    except Atendimento.DoesNotExist:
        return None


def _contexto_consulta_medico(
    consulta,
    form,
    form_exame,
    form_receita=None,
    formset_receita=None,
):
    return {
        "consulta": consulta,
        "atendimento": _obter_atendimento(consulta),
        "form": form,
        "form_exame": form_exame,
        "form_receita": form_receita or ReceitaForm(),
        "formset_receita": formset_receita or ReceitaMedicamentoFormSet(
            instance=Receita(),
            prefix="itens",
        ),
        "solicitacoes_exames": consulta.solicitacoes_exames.select_related(
            "exame"
        ).order_by("-solicitado_em"),
        "receitas": consulta.receitas.prefetch_related("itens__medicamento"),
    }


def _consulta_do_superadmin(consulta_id):
    return get_object_or_404(
        Consulta.objects.select_related(
            "paciente",
            "medico__especialidade",
            "atendimento",
        ).prefetch_related(
            "solicitacoes_exames__exame",
            "receitas__itens__medicamento",
        ),
        pk=consulta_id,
    )


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return _dashboard_administrativo(request)

    _obter_medico_ativo(request.user)

    return redirect("medico_dashboard")


def _dashboard_administrativo(request):
    consultas_base = Consulta.objects.select_related(
        "paciente",
        "medico",
        "medico__especialidade",
    ).order_by("data_horario")

    contexto_consultas = _contexto_consultas_administrativas(request, consultas_base)

    return render(
        request,
        "core/dashboard.html",
        {
            **contexto_consultas,
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


def _contexto_consultas_administrativas(request, consultas_base):
    busca = request.GET.get("busca", "").strip()
    medico_atual = request.GET.get("medico", "")
    especialidade_atual = request.GET.get("especialidade", "")
    data_atual = request.GET.get("data", "")
    status_atual = request.GET.get("status", "")
    status_validos = {valor for valor, _ in Consulta.Status.choices}
    consultas = consultas_base

    if busca:
        consultas = consultas.filter(paciente__nome__icontains=busca)

    if status_atual in status_validos:
        consultas = consultas.filter(status=status_atual)
    else:
        status_atual = ""

    if medico_atual.isdigit():
        consultas = consultas.filter(medico_id=medico_atual)
    else:
        medico_atual = ""

    if especialidade_atual.isdigit():
        consultas = consultas.filter(medico__especialidade_id=especialidade_atual)
    else:
        especialidade_atual = ""

    try:
        data_consulta = date.fromisoformat(data_atual) if data_atual else None
    except ValueError:
        data_consulta = None
        data_atual = ""
    if data_consulta:
        consultas = consultas.filter(data_horario__date=data_consulta)

    parametros = request.GET.copy()
    parametros.pop("page", None)
    pagina = Paginator(consultas, 10).get_page(request.GET.get("page"))

    return {
        "consultas": pagina,
        "page_obj": pagina,
        "busca": busca,
        "medico_atual": medico_atual,
        "especialidade_atual": especialidade_atual,
        "data_atual": data_atual,
        "status_atual": status_atual,
        "status_choices": Consulta.Status.choices,
        "medicos": Medico.objects.select_related("especialidade"),
        "especialidades": Especialidade.objects.all(),
        "filtros_query": parametros.urlencode(),
    }


@login_required
@require_GET
def consultas_filtradas(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Seu usuário não possui acesso ao painel administrativo.")

    consultas_base = Consulta.objects.select_related(
        "paciente",
        "medico__especialidade",
    ).order_by("data_horario")
    return render(
        request,
        "core/partials/consultas_lista.html",
        _contexto_consultas_administrativas(request, consultas_base),
    )


@login_required
def medico_dashboard(request):
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
def consulta_administrativo_detail(request, consulta_id):
    if not request.user.is_superuser:
        raise PermissionDenied("Seu usuário não possui acesso ao painel administrativo.")

    consulta = _consulta_do_superadmin(consulta_id)

    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "status":
            status_form = ConsultaStatusForm(request.POST, instance=consulta)
            reagendamento_form = ConsultaAdministrativaForm(instance=consulta)
            if status_form.is_valid():
                try:
                    status_form.save()
                except IntegrityError:
                    status_form.add_error(
                        "status",
                        "Este horário acabou de ser reservado por outra consulta.",
                    )
                else:
                    messages.success(request, "Status da consulta atualizado com sucesso.")
                    return redirect("consulta_administrativo_detail", consulta_id=consulta.id)
        else:
            status_form = ConsultaStatusForm(instance=consulta)
            reagendamento_form = ConsultaAdministrativaForm(request.POST, instance=consulta)
        if acao == "reagendar" and reagendamento_form.is_valid():
            consulta_anterior = consulta.data_horario
            try:
                consulta = reagendamento_form.save()
            except IntegrityError:
                reagendamento_form.add_error(
                    "horario",
                    "Este horário acabou de ser reservado. Escolha outro horário.",
                )
            else:
                if consulta.data_horario != consulta_anterior:
                    messages.success(request, "Consulta reagendada com sucesso.")
                else:
                    messages.info(request, "A consulta já está nesse horário.")
                return redirect("consulta_administrativo_detail", consulta_id=consulta.id)
    else:
        status_form = ConsultaStatusForm(instance=consulta)
        reagendamento_form = ConsultaAdministrativaForm(instance=consulta)

    return render(
        request,
        "core/consulta_administrativo_detail.html",
        {
            "consulta": consulta,
            "atendimento": _obter_atendimento(consulta),
            "status_form": status_form,
            "reagendamento_form": reagendamento_form,
        },
    )


@login_required
@require_POST
def excluir_consulta(request, consulta_id):
    if not request.user.is_superuser:
        raise PermissionDenied("Seu usuário não possui acesso ao painel administrativo.")

    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        status=Consulta.Status.CANCELADA,
    )

    try:
        consulta.delete()
    except ProtectedError:
        messages.error(
            request,
            "Esta consulta possui registros clínicos ou financeiros vinculados e não pode ser excluída.",
        )
        return redirect("consulta_administrativo_detail", consulta_id=consulta.id)

    messages.success(request, "Consulta cancelada excluída com sucesso.")
    return redirect("dashboard")


@login_required
def consulta_medico_detail(request, consulta_id):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        medico=medico,
    )

    atendimento = _obter_atendimento(consulta)

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
        _contexto_consulta_medico(consulta, form, SolicitacaoExameForm()),
    )


@login_required
@require_POST
def solicitar_exame(request, consulta_id):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        medico=medico,
    )
    form = SolicitacaoExameForm(request.POST)

    if form.is_valid():
        solicitacao = form.save(commit=False)
        solicitacao.consulta = consulta
        solicitacao.save()
        messages.success(request, "Solicitação de exame registrada com sucesso.")

        return redirect("consulta_medico_detail", consulta_id=consulta.id)

    return render(
        request,
        "core/consulta_medico_detail.html",
        _contexto_consulta_medico(
            consulta,
            AtendimentoForm(instance=_obter_atendimento(consulta)),
            form,
        ),
        status=400,
    )


@login_required
@require_POST
def emitir_receita(request, consulta_id):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        medico=medico,
    )
    receita = Receita(consulta=consulta)
    form_receita = ReceitaForm(request.POST, instance=receita)
    formset_receita = ReceitaMedicamentoFormSet(
        request.POST,
        instance=receita,
        prefix="itens",
    )

    if form_receita.is_valid() and formset_receita.is_valid():
        with transaction.atomic():
            receita = form_receita.save()
            formset_receita.instance = receita
            formset_receita.save()
        messages.success(request, "Receita emitida com sucesso.")
        return redirect("consulta_medico_detail", consulta_id=consulta.id)

    return render(
        request,
        "core/consulta_medico_detail.html",
        _contexto_consulta_medico(
            consulta,
            AtendimentoForm(instance=_obter_atendimento(consulta)),
            SolicitacaoExameForm(),
            form_receita,
            formset_receita,
        ),
        status=400,
    )


def session_expired_view(request):
    return render(request, "core/session_expired.html")
