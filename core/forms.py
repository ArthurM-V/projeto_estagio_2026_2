from datetime import date, datetime
import re

from django import forms
from django.contrib.auth import authenticate
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Atendimento,
    Consulta,
    Exame,
    Medicamento,
    Medico,
    Paciente,
    Prontuario,
    Receita,
    ReceitaMedicamento,
    Especialidade,
    SolicitacaoExame,
)
from .scheduling import horarios_da_clinica, horarios_disponiveis


class AgendamentoConsultaForm(forms.Form):
    nome = forms.CharField(
        label="Nome completo",
        max_length=120,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "off", "placeholder": "000.000.000-00"}
        ),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "voce@exemplo.com"}),
    )
    telefone = forms.CharField(
        label="Telefone",
        max_length=20,
        widget=forms.TextInput(
            attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "(00) 00000-0000"}
        ),
    )
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    medico = forms.ModelChoiceField(
        label="Médico",
        queryset=Medico.objects.none(),
        empty_label="Selecione um profissional",
    )
    data = forms.DateField(
        label="Data da consulta",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    horario = forms.ChoiceField(
        label="Horário disponível",
        choices=(("", "Selecione um médico e uma data primeiro"),),
    )
    observacoes = forms.CharField(
        label="Observações (opcional)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Conte, se desejar, algum detalhe que ajude no seu atendimento.",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medico"].queryset = Medico.objects.filter(
            ativo=True
        ).select_related("especialidade")
        self._definir_horarios_disponiveis()

    def _definir_horarios_disponiveis(self):
        medico_id = self.data.get("medico")
        data_texto = self.data.get("data")

        if not medico_id or not data_texto:
            return

        try:
            medico = self.fields["medico"].queryset.get(pk=medico_id)
            data_consulta = date.fromisoformat(data_texto)
        except (Medico.DoesNotExist, ValueError):
            return

        horarios = horarios_disponiveis(medico, data_consulta)
        self.fields["horario"].choices = [
            (horario.strftime("%H:%M"), horario.strftime("%H:%M"))
            for horario in horarios
        ]

    def clean_cpf(self):
        cpf_informado = self.cleaned_data["cpf"].strip()
        if not re.fullmatch(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", cpf_informado):
            raise forms.ValidationError("Informe o CPF apenas com números, no formato 000.000.000-00.")

        cpf = re.sub(r"\D", "", cpf_informado)

        return cpf

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        partes = nome.split()
        if len(partes) < 2 or any(not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ]+)*", parte) for parte in partes):
            raise forms.ValidationError("Informe nome e sobrenome, usando apenas letras.")
        return nome

    def clean_telefone(self):
        telefone_informado = self.cleaned_data["telefone"].strip()
        if not re.fullmatch(r"(?:\(\d{2}\)|\d{2})[ .-]?\d{4,5}-?\d{4}", telefone_informado):
            raise forms.ValidationError("Informe um telefone com DDD e 8 ou 9 dígitos, como (11) 99999-9999.")
        return re.sub(r"\D", "", telefone_informado)

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data["data_nascimento"]

        if data_nascimento > timezone.localdate():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")

        return data_nascimento

    def clean_data(self):
        data = self.cleaned_data["data"]

        if data < timezone.localdate():
            raise forms.ValidationError("Escolha uma data de hoje ou futura.")

        return data

    def clean(self):
        cleaned_data = super().clean()
        medico = cleaned_data.get("medico")
        data = cleaned_data.get("data")
        horario = cleaned_data.get("horario")
        cpf = cleaned_data.get("cpf")
        email = cleaned_data.get("email")

        if cpf and email and Paciente.objects.filter(email__iexact=email).exclude(cpf=cpf).exists():
            self.add_error("email", "Este e-mail já pertence a outro paciente cadastrado.")

        if medico and data and horario:
            horario = datetime.strptime(horario, "%H:%M").time()
            cleaned_data["horario"] = horario
            data_horario = timezone.make_aware(
                datetime.combine(data, horario),
                timezone.get_current_timezone(),
            )
            existe_conflito = Consulta.objects.filter(
                medico=medico,
                data_horario=data_horario,
                status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO),
                concluida_em__isnull=True,
            ).exists()

            if existe_conflito:
                raise forms.ValidationError(
                    "Este médico já possui uma consulta neste horário. Escolha outro horário."
                )

        return cleaned_data


class ConsultaAdministrativaForm(forms.ModelForm):
    data = forms.DateField(
        label="Nova data",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    horario = forms.ChoiceField(
        label="Novo horário",
        choices=(("", "Selecione uma data"),),
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
            }
        ),
    )

    class Meta:
        model = Consulta
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            data_horario = timezone.localtime(self.instance.data_horario)
            self.initial.setdefault("data", data_horario.date())
            self.initial.setdefault("horario", data_horario.strftime("%H:%M"))

        data_texto = self.data.get("data") if self.is_bound else self.initial.get("data")
        if isinstance(data_texto, date):
            data_consulta = data_texto
        else:
            try:
                data_consulta = date.fromisoformat(data_texto)
            except (TypeError, ValueError):
                return

        horarios = horarios_disponiveis(
            self.instance.medico,
            data_consulta,
            consulta_excluida_id=self.instance.pk,
        )
        horario_atual = timezone.localtime(self.instance.data_horario)
        horario_atual_sem_fuso = horario_atual.time().replace(tzinfo=None)
        if (
            data_consulta == horario_atual.date()
            and horario_atual_sem_fuso in horarios_da_clinica(data_consulta)
            and horario_atual_sem_fuso not in horarios
        ):
            horarios.append(horario_atual_sem_fuso)
            horarios.sort()
        self.fields["horario"].choices = [("", "Selecione um horário")] + [
            (horario.strftime("%H:%M"), horario.strftime("%H:%M"))
            for horario in horarios
        ]

    def clean(self):
        cleaned_data = super().clean()
        data_consulta = cleaned_data.get("data")
        horario_texto = cleaned_data.get("horario")

        if not data_consulta or not horario_texto:
            return cleaned_data

        try:
            horario = datetime.strptime(horario_texto, "%H:%M").time()
        except ValueError:
            self.add_error("horario", "Selecione um horário válido.")
            return cleaned_data

        if horario not in horarios_da_clinica(data_consulta):
            self.add_error("horario", "Este horário não faz parte da agenda da clínica.")
            return cleaned_data

        data_horario = timezone.make_aware(
            datetime.combine(data_consulta, horario),
            timezone.get_current_timezone(),
        )
        horario_foi_alterado = data_horario != self.instance.data_horario

        if horario_foi_alterado and data_horario <= timezone.now():
            self.add_error("data", "Escolha uma data e horário futuros para reagendar.")

        if self.instance.status in (Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO):
            existe_conflito = Consulta.objects.filter(
                medico=self.instance.medico,
                data_horario=data_horario,
                status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO),
                concluida_em__isnull=True,
            ).exclude(pk=self.instance.pk).exists()
            if existe_conflito:
                self.add_error(
                    "horario",
                    "Este médico já possui uma consulta ativa neste horário.",
                )

        cleaned_data["data_horario"] = data_horario
        return cleaned_data

    def save(self, commit=True):
        consulta = super().save(commit=False)
        consulta.data_horario = self.cleaned_data["data_horario"]
        if commit:
            consulta.save()
        return consulta


class ConsultaStatusForm(forms.ModelForm):
    class Meta:
        model = Consulta
        fields = ("status",)
        labels = {"status": "Status da consulta"}
        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            )
        }

    def clean_status(self):
        status = self.cleaned_data["status"]
        if status in (Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO):
            existe_conflito = Consulta.objects.filter(
                medico=self.instance.medico,
                data_horario=self.instance.data_horario,
                status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO),
                concluida_em__isnull=True,
            ).exclude(pk=self.instance.pk).exists()
            if existe_conflito:
                raise forms.ValidationError(
                    "Há outra consulta ativa para este médico neste horário."
                )
        return status


class AtendimentoForm(forms.ModelForm):
    """Registra as informações clínicas de uma consulta."""

    sintomas = forms.CharField(
        label="Sintomas",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Descreva os sintomas relatados pelo paciente.",
                "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
            }
        ),
    )

    class Meta:
        model = Atendimento
        fields = ("sexo", "sintomas", "diagnostico", "conduta", "observacoes")
        labels = {
            "sexo": "Sexo (opcional)",
            "diagnostico": "Diagnóstico (opcional)",
            "conduta": "Conduta (opcional)",
            "observacoes": "Observações clínicas (opcional)",
        }

        widgets = {
            "sexo": forms.Select(
                attrs={
                    "class": "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "diagnostico": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Registre o diagnóstico, se houver.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "conduta": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Descreva a conduta adotada.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "observacoes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Inclua observações relevantes.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
        }


class SolicitacaoExameForm(forms.ModelForm):
    """Solicita um exame para a consulta em atendimento."""

    class Meta:
        model = SolicitacaoExame
        fields = ("exame", "observacoes")
        labels = {
            "exame": "Exame",
            "observacoes": "Observações (opcional)",
        }
        widgets = {
            "exame": forms.Select(
                attrs={
                    "class": "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "observacoes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Informe preparo, prioridade ou outra orientação.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exame"].queryset = Exame.objects.order_by("nome")
        self.fields["exame"].empty_label = "Selecione um exame"


class ReceitaForm(forms.ModelForm):
    class Meta:
        model = Receita
        fields = ("orientacoes",)
        labels = {"orientacoes": "Orientações gerais (opcional)"}
        widgets = {
            "orientacoes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Inclua recomendações gerais para o paciente.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            )
        }


class ReceitaMedicamentoForm(forms.ModelForm):
    class Meta:
        model = ReceitaMedicamento
        fields = ("medicamento", "dosagem", "frequencia", "duracao", "instrucoes")
        labels = {
            "medicamento": "Medicamento",
            "dosagem": "Dosagem",
            "frequencia": "Frequência",
            "duracao": "Duração",
            "instrucoes": "Instruções (opcional)",
        }
        widgets = {
            "medicamento": forms.Select(
                attrs={
                    "class": "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "dosagem": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: 500 mg",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "frequencia": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: a cada 8 horas",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "duracao": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: 5 dias",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
            "instrucoes": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Ex.: tomar após as refeições.",
                    "class": "w-full rounded-xl border border-slate-300 px-3.5 py-3 text-sm leading-6 outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medicamento"].queryset = Medicamento.objects.order_by("nome")
        self.fields["medicamento"].empty_label = "Selecione um medicamento"


ReceitaMedicamentoFormSet = inlineformset_factory(
    Receita,
    ReceitaMedicamento,
    form=ReceitaMedicamentoForm,
    extra=5,
    min_num=1,
    max_num=5,
    validate_min=True,
    validate_max=True,
    can_delete=True,
)


CAMPO_PADRAO = "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100"


class MedicoCadastroForm(forms.ModelForm):
    class Meta:
        model = Medico
        fields = ("nome", "crm", "email", "telefone", "especialidade")
        widgets = {
            "nome": forms.TextInput(attrs={"class": CAMPO_PADRAO, "autocomplete": "name", "placeholder": "Nome completo"}),
            "crm": forms.TextInput(attrs={"class": CAMPO_PADRAO, "autocomplete": "off", "placeholder": "SP 123456"}),
            "email": forms.EmailInput(attrs={"class": CAMPO_PADRAO, "autocomplete": "email", "placeholder": "medico@exemplo.com"}),
            "telefone": forms.TextInput(attrs={"class": CAMPO_PADRAO, "inputmode": "tel", "autocomplete": "tel", "placeholder": "(00) 00000-0000"}),
            "especialidade": forms.Select(attrs={"class": CAMPO_PADRAO}),
        }

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if not all(parte.replace("-", "").isalpha() for parte in nome.split()):
            raise forms.ValidationError("Informe apenas letras no nome do médico.")
        return nome

    def clean_crm(self):
        crm = self.cleaned_data["crm"].upper().strip()
        if not re.fullmatch(r"[A-Z]{2}\s?\d{4,6}", crm):
            raise forms.ValidationError("Informe o CRM no formato UF seguido de 4 a 6 dígitos, como SP 123456.")
        return f"{crm[:2]} {crm[2:].strip()}"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Medico.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um médico cadastrado com este e-mail.")
        return email

    def clean_telefone(self):
        telefone = self.cleaned_data["telefone"].strip()
        if not telefone:
            return telefone
        if not re.fullmatch(r"(?:\(\d{2}\)|\d{2})[ .-]?\d{4,5}-?\d{4}", telefone):
            raise forms.ValidationError("Informe um telefone com DDD e 8 ou 9 dígitos, como (11) 99999-9999.")
        return re.sub(r"\D", "", telefone)


class ConfirmacaoRedefinicaoSenhaForm(forms.Form):
    usuario = forms.CharField(label="Seu usuário", widget=forms.TextInput(attrs={"class": CAMPO_PADRAO, "autocomplete": "username"}))
    senha = forms.CharField(label="Sua senha", widget=forms.PasswordInput(attrs={"class": CAMPO_PADRAO, "autocomplete": "current-password"}))

    def __init__(self, *args, usuario_atual, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_atual = usuario_atual

    def clean(self):
        dados = super().clean()
        usuario = authenticate(username=dados.get("usuario"), password=dados.get("senha"))
        if not usuario or usuario.pk != self.usuario_atual.pk or not usuario.is_superuser:
            raise forms.ValidationError("Confirme com as credenciais do superadmin autenticado.")
        return dados
