from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Consulta, Especialidade, Medico, Paciente


class AgendamentoConsultaTests(TestCase):
    def setUp(self):
        especialidade = Especialidade.objects.create(nome="Clínica Geral")
        self.medico = Medico.objects.create(
            nome="Marina Alves",
            crm="SP 123456",
            email="marina.alves@smarthealth.test",
            especialidade=especialidade,
        )
        self.data_consulta = timezone.localdate() + timedelta(days=1)
        while self.data_consulta.weekday() == 6:
            self.data_consulta += timedelta(days=1)
        self.horario = time(10, 0)

    def dados_validos(self):
        return {
            "nome": "Ana Silva",
            "cpf": "123.456.789-09",
            "email": "ana.silva@example.com",
            "telefone": "(11) 99999-0000",
            "data_nascimento": "1990-05-20",
            "medico": str(self.medico.id),
            "data": self.data_consulta.isoformat(),
            "horario": self.horario.strftime("%H:%M"),
            "observacoes": "",
        }

    def test_envio_valido_cria_paciente_e_consulta_pendente(self):
        resposta = self.client.post(reverse("home"), self.dados_validos())

        self.assertRedirects(resposta, reverse("home"))
        paciente = Paciente.objects.get(cpf="12345678909")
        consulta = Consulta.objects.get()

        self.assertEqual(consulta.paciente, paciente)
        self.assertEqual(consulta.medico, self.medico)
        self.assertEqual(consulta.status, Consulta.Status.PENDENTE)

    def test_horario_ocupado_nao_e_oferecido_e_nao_duplica_consulta(self):
        paciente = Paciente.objects.create(
            nome="Paciente existente",
            cpf="98765432100",
            email="existente@example.com",
            telefone="(11) 98888-0000",
            data_nascimento="1985-01-10",
        )
        data_horario = timezone.make_aware(
            datetime.combine(self.data_consulta, self.horario),
            timezone.get_current_timezone(),
        )
        Consulta.objects.create(
            paciente=paciente,
            medico=self.medico,
            data_horario=data_horario,
        )

        resposta = self.client.post(reverse("home"), self.dados_validos())

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("horario", resposta.context["form"].errors)
        self.assertNotIn(
            ("10:00", "10:00"),
            resposta.context["form"].fields["horario"].choices,
        )
        self.assertEqual(Consulta.objects.count(), 1)
