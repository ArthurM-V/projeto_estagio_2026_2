from calendar import monthrange
from datetime import date, datetime, time

from django.utils import timezone

from .models import Consulta


HORARIOS_SEMANA = (
    time(8, 0),
    time(9, 0),
    time(10, 0),
    time(11, 0),
    time(13, 0),
    time(14, 0),
    time(15, 0),
    time(16, 0),
    time(17, 0),
)
HORARIOS_SABADO = (
    time(8, 0),
    time(9, 0),
    time(10, 0),
    time(11, 0),
    time(13, 0),
    time(14, 0),
)


def data_maxima_agendamento(data_referencia=None):
    """Retorna a última data disponível: seis meses-calendário à frente."""
    data_referencia = data_referencia or timezone.localdate()
    mes_destino = data_referencia.month + 6
    ano_destino = data_referencia.year + (mes_destino - 1) // 12
    mes_destino = (mes_destino - 1) % 12 + 1
    ultimo_dia = monthrange(ano_destino, mes_destino)[1]
    return date(ano_destino, mes_destino, min(data_referencia.day, ultimo_dia))


def horarios_da_clinica(data):
    if data.weekday() < 5:
        return HORARIOS_SEMANA
    if data.weekday() == 5:
        return HORARIOS_SABADO
    return ()


def horarios_disponiveis(medico, data, consulta_excluida_id=None):
    """Retorna os horários livres do médico em uma data da agenda da clínica."""
    if (
        not medico.ativo
        or data < timezone.localdate()
        or data > data_maxima_agendamento()
    ):
        return []

    fuso_horario = timezone.get_current_timezone()
    inicio = timezone.make_aware(
        datetime.combine(data, time.min),
        fuso_horario,
    )
    fim = timezone.make_aware(
        datetime.combine(data, time.max),
        fuso_horario,
    )
    ocupados = Consulta.objects.filter(
        medico=medico,
        data_horario__range=(inicio, fim),
        status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADO),
        concluida_em__isnull=True,
    )
    if consulta_excluida_id:
        ocupados = ocupados.exclude(pk=consulta_excluida_id)

    ocupados = ocupados.values_list("data_horario", flat=True)
    horarios_ocupados = {
        data_horario.astimezone(fuso_horario).time().replace(tzinfo=None)
        for data_horario in ocupados
    }

    horarios = [
        horario
        for horario in horarios_da_clinica(data)
        if horario not in horarios_ocupados
    ]

    if data == timezone.localdate():
        horario_atual = timezone.localtime().time().replace(tzinfo=None)
        horarios = [horario for horario in horarios if horario > horario_atual]

    return horarios
