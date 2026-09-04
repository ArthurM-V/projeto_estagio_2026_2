from django.contrib import admin

from .models import (
    Atendimento,
    Consulta,
    Convenio,
    Especialidade,
    Exame,
    Medicamento,
    Medico,
    Paciente,
    PacienteConvenio,
    Pagamento,
    Prontuario,
    Receita,
    ReceitaMedicamento,
    SolicitacaoExame,
)


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "medico", "data_horario", "status")
    list_filter = ("status", "medico__especialidade", "data_horario")
    search_fields = ("paciente__nome", "paciente__cpf", "medico__nome")
    ordering = ("data_horario",)


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "email", "telefone", "data_nascimento")
    search_fields = ("nome", "cpf", "email")


admin.site.register(
    [
        Especialidade,
        Atendimento,
        Medico,
        Prontuario,
        Convenio,
        PacienteConvenio,
        Medicamento,
        Receita,
        ReceitaMedicamento,
        Exame,
        SolicitacaoExame,
        Pagamento,
    ]
)
