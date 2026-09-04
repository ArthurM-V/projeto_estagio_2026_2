from datetime import date, datetime

from django import forms
from django.utils import timezone

from .models import Consulta, Medico, Paciente
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
