from datetime import date, datetime
from datetime import timedelta
import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Max
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
    ConfirmacaoRedefinicaoSenhaForm,
    MedicoCadastroForm,
    ReceitaForm,
    ReceitaMedicamentoFormSet,
    SolicitacaoExameForm,
)
from .models import Atendimento, Consulta, Especialidade, Medico, Paciente, Prontuario, Receita, RedefinicaoSenhaMedico
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


def _consulta_confirmada_para_registro(request, consulta):
    """Impede qualquer alteração clínica fora de uma consulta confirmada."""
    if consulta.status == Consulta.Status.CONFIRMADO and not consulta.esta_concluida:
        return True

    messages.error(
        request,
        "Registros clínicos só podem ser alterados em consultas confirmadas e ainda não concluídas.",
    )
    return False


def _estado_prontuario(consulta):
    try:
        prontuario = consulta.paciente.prontuario
    except Prontuario.DoesNotExist:
        prontuario = None

    atendimento = _obter_atendimento(consulta)
    alteracoes = [atendimento.atualizado_em] if atendimento else []
    for campo in ("emitida_em", "solicitado_em"):
        modelo = consulta.receitas if campo == "emitida_em" else consulta.solicitacoes_exames
        data = modelo.aggregate(ultima=Max(campo))["ultima"]
        if data:
            alteracoes.append(data)
    ultima_alteracao = max(alteracoes, default=None)
    pode_atualizar = (
        consulta.status == Consulta.Status.CONFIRMADO
        and not consulta.esta_concluida
        and (
        prontuario is None or (ultima_alteracao and ultima_alteracao > prontuario.atualizado_em)
        )
    )
    return prontuario, pode_atualizar


def _dados_prontuario(consulta):
    atendimento = _obter_atendimento(consulta)
    dados_pessoais = []
    if atendimento and atendimento.sexo:
        dados_pessoais.append(f"Sexo: {atendimento.get_sexo_display()}")

    anamnese_partes = dados_pessoais
    if atendimento and atendimento.sintomas:
        anamnese_partes.append(f"Queixas e sintomas:\n{atendimento.sintomas}")

    evolucao_partes = [
        f"Consulta de {timezone.localtime(consulta.data_horario):%d/%m/%Y às %H:%M}."
    ]
    if atendimento and atendimento.diagnostico:
        evolucao_partes.append(f"Diagnóstico:\n{atendimento.diagnostico}")
    if atendimento and atendimento.conduta:
        evolucao_partes.append(f"Conduta:\n{atendimento.conduta}")
    if atendimento and atendimento.observacoes:
        evolucao_partes.append(f"Observações clínicas:\n{atendimento.observacoes}")

    exames = consulta.solicitacoes_exames.select_related("exame").order_by("solicitado_em")
    if exames:
        itens_exames = [
            f"- {solicitacao.exame.nome} ({solicitacao.get_status_display()})"
            for solicitacao in exames
        ]
        evolucao_partes.append("Exames solicitados:\n" + "\n".join(itens_exames))

    receitas = consulta.receitas.prefetch_related("itens__medicamento").order_by("emitida_em")
    prescricoes_partes = []
    if receitas:
        itens_receita = []
        for receita in receitas:
            for item in receita.itens.all():
                itens_receita.append(
                    f"- {item.medicamento.nome}: {item.dosagem}, {item.frequencia}, por {item.duracao}."
                )
            if receita.orientacoes:
                itens_receita.append(f"- Orientações: {receita.orientacoes}")
        if itens_receita:
            prescricoes_partes.append("Medicamentos e orientações:\n" + "\n".join(itens_receita))

    return {
        "anamnese": "\n\n".join(anamnese_partes),
        "evolucao_clinica": "\n\n".join(evolucao_partes),
        "prescricoes": "\n\n".join(prescricoes_partes),
    }


def _contexto_consulta_medico(
    consulta,
    form,
    form_exame,
    form_receita=None,
    formset_receita=None,
):
    prontuario, pode_atualizar_prontuario = _estado_prontuario(consulta)
    dados_prontuario = _dados_prontuario(consulta)
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
        "prontuario": prontuario,
        "pode_atualizar_prontuario": pode_atualizar_prontuario,
        "dados_prontuario": dados_prontuario,
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


def _dashboard_administrativo(request, form_medico=None, form_redefinicao=None, medico_redefinicao=None):
    consultas_base = Consulta.objects.select_related(
        "paciente",
        "medico",
        "medico__especialidade",
    ).order_by("data_horario")

    contexto_consultas = _contexto_consultas_administrativas(request, consultas_base)

    credenciais = request.session.pop("credenciais_medico", None)
    medico_credencial = None
    if credenciais:
        medico_credencial = get_object_or_404(Medico, pk=credenciais["medico_id"])

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
                status=Consulta.Status.CONFIRMADO
            ).count(),
            "consultas_hoje": consultas_base.filter(
                data_horario__date=timezone.localdate()
            ).count(),
            "form_medico": form_medico or MedicoCadastroForm(),
            "medicos_equipe": Medico.objects.select_related("especialidade", "usuario"),
            "form_redefinicao": form_redefinicao or ConfirmacaoRedefinicaoSenhaForm(usuario_atual=request.user),
            "medico_redefinicao": medico_redefinicao,
            "credenciais": credenciais,
            "medico_credencial": medico_credencial,
            "aba_ativa": "medicos" if form_medico is not None or medico_redefinicao is not None or credenciais else "consultas",
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


def _senha_automatica(medico):
    alfabeto = string.ascii_letters + string.digits
    senhas_anteriores = list(medico.redefinicoes_senha.values_list("senha_hash", flat=True)) if medico.pk else []
    senha_atual = medico.usuario.password if medico.usuario else ""
    while True:
        caracteres = [secrets.choice(string.ascii_lowercase), secrets.choice(string.ascii_uppercase), secrets.choice(string.digits)]
        caracteres += [secrets.choice(alfabeto) for _ in range(7)]
        secrets.SystemRandom().shuffle(caracteres)
        senha = "".join(caracteres)
        if not check_password(senha, senha_atual) and not any(check_password(senha, senha_hash) for senha_hash in senhas_anteriores):
            return senha


def _username_disponivel(nome):
    base = "".join(caractere for caractere in nome.lower() if caractere.isalnum())[:140] or "medico"
    User = get_user_model()
    username, indice = base, 2
    while User.objects.filter(username=username).exists():
        username = f"{base[:145]}{indice}"
        indice += 1
    return username


def _apenas_superadmin(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Seu usuário não possui acesso ao painel administrativo.")


@login_required
def cadastrar_medico(request):
    _apenas_superadmin(request)
    form = MedicoCadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            medico = form.save(commit=False)
            senha = _senha_automatica(medico)
            usuario = get_user_model().objects.create_user(username=_username_disponivel(medico.nome), email=medico.email, password=senha, is_staff=False, is_superuser=False)
            medico.usuario = usuario
            medico.save()
            RedefinicaoSenhaMedico.objects.create(medico=medico, redefinida_por=request.user, senha_hash=make_password(senha), foi_redefinicao=False)
        request.session["credenciais_medico"] = {"medico_id": medico.id, "senha": senha, "acao": "criado"}
        return redirect("dashboard")
    return _dashboard_administrativo(request, form)


@login_required
def redefinir_senha_medico(request, medico_id):
    _apenas_superadmin(request)
    medico = get_object_or_404(Medico.objects.select_related("usuario"), pk=medico_id, usuario__isnull=False)
    ultima = medico.redefinicoes_senha.filter(foi_redefinicao=True).first()
    if ultima and ultima.redefinida_em > timezone.now() - timedelta(days=15):
        messages.error(request, "A senha deste médico só pode ser redefinida novamente após 15 dias.")
        return redirect("dashboard")
    form = ConfirmacaoRedefinicaoSenhaForm(request.POST or None, usuario_atual=request.user)
    if request.method == "POST" and form.is_valid():
        senha = _senha_automatica(medico)
        with transaction.atomic():
            medico.usuario.set_password(senha)
            medico.usuario.save(update_fields=("password",))
            RedefinicaoSenhaMedico.objects.create(medico=medico, redefinida_por=request.user, senha_hash=make_password(senha))
        request.session["credenciais_medico"] = {"medico_id": medico.id, "senha": senha, "acao": "redefinida"}
        return redirect("dashboard")
    return _dashboard_administrativo(
        request,
        form_redefinicao=form,
        medico_redefinicao=medico,
    )


def _contexto_medico_administrativo(medico, form_edicao=None, form_confirmacao_edicao=None, form_confirmacao_desligamento=None, secao_aberta=None):
    return {
        "medico": medico,
        "form_edicao": form_edicao or MedicoCadastroForm(instance=medico),
        "form_confirmacao_edicao": form_confirmacao_edicao or ConfirmacaoRedefinicaoSenhaForm(usuario_atual=None, prefix="confirmacao_edicao"),
        "form_confirmacao_desligamento": form_confirmacao_desligamento or ConfirmacaoRedefinicaoSenhaForm(usuario_atual=None, prefix="confirmacao_desligamento"),
        "secao_aberta": secao_aberta,
        "total_consultas_medico": medico.consultas.count(),
    }


@login_required
def medico_administrativo_detail(request, medico_id):
    _apenas_superadmin(request)
    medico = get_object_or_404(
        Medico.objects.select_related("especialidade", "usuario").prefetch_related("consultas"),
        pk=medico_id,
    )

    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "editar":
            form_edicao = MedicoCadastroForm(request.POST, instance=medico)
            form_confirmacao_edicao = ConfirmacaoRedefinicaoSenhaForm(
                request.POST, usuario_atual=request.user, prefix="confirmacao_edicao"
            )
            if form_edicao.is_valid() and form_confirmacao_edicao.is_valid():
                medico = form_edicao.save()
                if medico.usuario:
                    medico.usuario.email = medico.email
                    medico.usuario.save(update_fields=("email",))
                messages.success(request, "Dados do médico atualizados com sucesso.")
                return redirect("medico_administrativo_detail", medico_id=medico.id)
            return render(
                request,
                "core/medico_administrativo_detail.html",
                _contexto_medico_administrativo(
                    medico,
                    form_edicao=form_edicao,
                    form_confirmacao_edicao=form_confirmacao_edicao,
                    secao_aberta="edicao",
                ),
                status=400,
            )

        if acao == "desligar":
            form_confirmacao_desligamento = ConfirmacaoRedefinicaoSenhaForm(
                request.POST, usuario_atual=request.user, prefix="confirmacao_desligamento"
            )
            if form_confirmacao_desligamento.is_valid():
                medico.ativo = False
                medico.save(update_fields=("ativo",))
                if medico.usuario:
                    medico.usuario.is_active = False
                    medico.usuario.save(update_fields=("is_active",))
                messages.success(request, "Médico desligado e acesso ao painel bloqueado.")
                return redirect("medico_administrativo_detail", medico_id=medico.id)
            return render(
                request,
                "core/medico_administrativo_detail.html",
                _contexto_medico_administrativo(
                    medico,
                    form_confirmacao_desligamento=form_confirmacao_desligamento,
                    secao_aberta="desligamento",
                ),
                status=400,
            )

    return render(request, "core/medico_administrativo_detail.html", _contexto_medico_administrativo(medico))


@login_required
def medico_dashboard(request):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)

    consultas_base = (
        Consulta.objects.filter(medico=medico)
        .select_related("paciente", "atendimento")
        .order_by("data_horario")
    )

    return render(
        request,
        "core/medico_dashboard.html",
        {
            "medico": medico,
            **_contexto_consultas_medico(request, consultas_base),
            "consultas_hoje": consultas_base.filter(
                data_horario__date=timezone.localdate()
            ).count(),
            "pendentes": consultas_base.filter(status=Consulta.Status.PENDENTE).count(),
        },
    )


def _contexto_consultas_medico(request, consultas_base):
    busca = request.GET.get("busca", "").strip()
    status_atual = request.GET.get("status", "")
    data_atual = request.GET.get("data", "")
    consultas = consultas_base

    if busca:
        consultas = consultas.filter(paciente__nome__icontains=busca)
    status_validos = {valor for valor, _ in Consulta.Status.choices}
    if status_atual in status_validos:
        consultas = consultas.filter(status=status_atual)
    else:
        status_atual = ""
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
        "status_atual": status_atual,
        "data_atual": data_atual,
        "status_choices": Consulta.Status.choices,
        "filtros_query": parametros.urlencode(),
    }


@login_required
@require_GET
def consultas_medico_filtradas(request):
    if request.user.is_superuser:
        raise PermissionDenied("Seu usuário não possui acesso ao painel médico.")
    medico = _obter_medico_ativo(request.user)
    consultas_base = (
        Consulta.objects.filter(medico=medico)
        .select_related("paciente", "atendimento")
        .order_by("data_horario")
    )
    return render(
        request,
        "core/partials/consultas_medico_lista.html",
        _contexto_consultas_medico(request, consultas_base),
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
            "prontuario": _estado_prontuario(consulta)[0],
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
        status=Consulta.Status.CANCELADO,
    )

    try:
        consulta.delete()
    except ProtectedError:
        messages.error(
            request,
            "Esta consulta possui registros clínicos vinculados e não pode ser excluída.",
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
        if not _consulta_confirmada_para_registro(request, consulta):
            return redirect("consulta_medico_detail", consulta_id=consulta.id)

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
def salvar_prontuario(request, consulta_id):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "medico__especialidade"),
        pk=consulta_id,
        medico=medico,
    )
    if not _consulta_confirmada_para_registro(request, consulta):
        return redirect("consulta_medico_detail", consulta_id=consulta.id)

    prontuario, pode_atualizar = _estado_prontuario(consulta)
    if not pode_atualizar:
        messages.error(request, "O prontuário não pode ser atualizado neste momento.")
        return redirect("consulta_medico_detail", consulta_id=consulta.id)

    Prontuario.objects.update_or_create(
        paciente=consulta.paciente,
        defaults=_dados_prontuario(consulta),
    )
    messages.success(request, "Prontuário atualizado com sucesso.")
    return redirect("consulta_medico_detail", consulta_id=consulta.id)


@login_required
@require_POST
def concluir_consulta_medico(request, consulta_id):
    if request.user.is_superuser:
        return redirect("dashboard")

    medico = _obter_medico_ativo(request.user)
    consulta = get_object_or_404(Consulta, pk=consulta_id, medico=medico)
    if consulta.status != Consulta.Status.CONFIRMADO:
        messages.error(request, "Somente consultas confirmadas podem ser concluídas pelo médico.")
    elif consulta.esta_concluida:
        messages.info(request, "Esta consulta já foi concluída.")
    elif not _obter_atendimento(consulta):
        messages.error(request, "Registre o atendimento clínico antes de concluir a consulta.")
    else:
        consulta.concluida_em = timezone.now()
        consulta.save(update_fields=("concluida_em",))
        messages.success(request, "Consulta marcada como concluída.")
    return redirect("consulta_medico_detail", consulta_id=consulta.id)


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
    if not _consulta_confirmada_para_registro(request, consulta):
        return redirect("consulta_medico_detail", consulta_id=consulta.id)

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
    if not _consulta_confirmada_para_registro(request, consulta):
        return redirect("consulta_medico_detail", consulta_id=consulta.id)

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
