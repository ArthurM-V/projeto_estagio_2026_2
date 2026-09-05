from datetime import datetime, time

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


def horarios_da_clinica(data):
    if data.weekday() < 5:
        return HORARIOS_SEMANA
    if data.weekday() == 5:
        return HORARIOS_SABADO
    return ()


def horarios_disponiveis(medico, data):
    """Retorna os horários livres do médico em uma data da agenda da clínica."""
    if not medico.ativo or data < timezone.localdate():
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
        status__in=(Consulta.Status.PENDENTE, Consulta.Status.CONFIRMADA),
    ).values_list("data_horario", flat=True)
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
