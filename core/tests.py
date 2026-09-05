from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
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


class AcessoAosPaineisTests(TestCase):
    def setUp(self):
        especialidade = Especialidade.objects.create(nome="Cardiologia")
        self.superadmin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@smarthealth.test",
            password="senha-segura-para-teste",
        )
        usuario_medico = get_user_model().objects.create_user(
            username="medica",
            password="senha-segura-para-teste",
        )
        self.medico = Medico.objects.create(
            nome="Helena Costa",
            crm="SP 987654",
            email="helena@smarthealth.test",
            especialidade=especialidade,
            usuario=usuario_medico,
        )
        self.outro_medico = Medico.objects.create(
            nome="Lucas Freitas",
            crm="SP 456789",
            email="lucas@smarthealth.test",
            especialidade=especialidade,
        )
        self.usuario_sem_perfil = get_user_model().objects.create_user(
            username="sem-perfil",
            password="senha-segura-para-teste",
        )
        paciente_da_medica = Paciente.objects.create(
            nome="Paciente da médica",
            cpf="11122233344",
            email="medica.paciente@smarthealth.test",
            telefone="(11) 98888-0000",
            data_nascimento="1990-01-01",
        )
        paciente_do_outro_medico = Paciente.objects.create(
            nome="Paciente de outro médico",
            cpf="55566677788",
            email="outro.paciente@smarthealth.test",
            telefone="(11) 97777-0000",
            data_nascimento="1992-02-02",
        )
        data_horario = timezone.make_aware(
            datetime.combine(timezone.localdate() + timedelta(days=1), time(10)),
            timezone.get_current_timezone(),
        )
        Consulta.objects.create(
            paciente=paciente_da_medica,
            medico=self.medico,
            data_horario=data_horario,
            observacoes="Paciente relata desconforto leve.",
        )
        Consulta.objects.create(
            paciente=paciente_do_outro_medico,
            medico=self.outro_medico,
            data_horario=data_horario,
        )

    def test_visitante_e_redirecionado_para_login(self):
        resposta = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            resposta,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_superadmin_acessa_painel_administrativo(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.get(reverse("dashboard"))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "core/dashboard.html")

    def test_medico_e_encaminhado_e_ve_somente_suas_consultas(self):
        self.client.force_login(self.medico.usuario)

        resposta = self.client.get(reverse("dashboard"))
        self.assertRedirects(resposta, reverse("medico_dashboard"))

        resposta = self.client.get(reverse("medico_dashboard"))
        self.assertContains(resposta, "Paciente da médica")
        self.assertContains(resposta, "Paciente relata desconforto leve.")
        self.assertNotContains(resposta, "Paciente de outro médico")
        self.assertNotContains(resposta, "medica.paciente@smarthealth.test")
        self.assertNotContains(resposta, "11122233344")

    def test_usuario_sem_perfil_nao_acessa_os_paineis(self):
        self.client.force_login(self.usuario_sem_perfil)

        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("medico_dashboard")).status_code, 403)
