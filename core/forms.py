from datetime import date, datetime

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Atendimento,
    Consulta,
    Exame,
    Medicamento,
    Medico,
    Paciente,
    Receita,
    ReceitaMedicamento,
    SolicitacaoExame,
)
from .scheduling import horarios_disponiveis


class AgendamentoConsultaForm(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=120)
    cpf = forms.CharField(label="CPF", max_length=14)
    email = forms.EmailField(label="E-mail")
    telefone = forms.CharField(label="Telefone", max_length=20)
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
        cpf = "".join(caractere for caractere in self.cleaned_data["cpf"] if caractere.isdigit())

        if len(cpf) != 11:
            raise forms.ValidationError("Informe um CPF com 11 dígitos.")

        return cpf

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
                status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADA),
            ).exists()

            if existe_conflito:
                raise forms.ValidationError(
                    "Este médico já possui uma consulta neste horário. Escolha outro horário."
                )

        return cleaned_data


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
        fields = ("sintomas", "diagnostico", "conduta", "observacoes")
        labels = {
            "diagnostico": "Diagnóstico (opcional)",
            "conduta": "Conduta (opcional)",
            "observacoes": "Observações clínicas (opcional)",
        }
        widgets = {
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
