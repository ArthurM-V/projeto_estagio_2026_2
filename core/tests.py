from io import StringIO

from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Atendimento,
    Consulta,
    Especialidade,
    Exame,
    Medicamento,
    Medico,
    Paciente,
    Prontuario,
    RedefinicaoSenhaMedico,
    Receita,
    SolicitacaoExame,
)
from .scheduling import data_maxima_agendamento, horarios_disponiveis


class PaginasDeErroTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_rota_inexistente_renderiza_pagina_404_personalizada(self):
        resposta = self.client.get("/rota-que-nao-existe/")

        self.assertEqual(resposta.status_code, 404)
        self.assertTemplateUsed(resposta, "core/error_page.html")
        self.assertContains(resposta, "Erro 404", status_code=404)
        self.assertContains(resposta, "Página não encontrada", status_code=404)


class SeedDataTests(TestCase):
    def test_seed_cria_usuario_medico_e_vincula_joao_silva(self):
        call_command("seed_data", stdout=StringIO())

        User = get_user_model()
        usuario_medico = User.objects.get(username="usermedico")
        medico = Medico.objects.get(crm="123")

        self.assertFalse(User.objects.filter(username="admin").exists())
        self.assertFalse(usuario_medico.is_superuser)
        self.assertTrue(usuario_medico.check_password("medicopassword"))
        self.assertEqual(medico.nome, "João Silva")
        self.assertEqual(medico.usuario, usuario_medico)

        call_command("seed_data", stdout=StringIO())
        self.assertEqual(User.objects.filter(username="usermedico").count(), 1)

    def test_seed_nao_altera_superadmin_existente(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@smarthealth.test",
            password="senha-original-segura",
        )
        senha_original = admin.password

        call_command("seed_data", stdout=StringIO())

        admin.refresh_from_db()
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.password, senha_original)


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

    def test_data_posterior_a_seis_meses_nao_pode_ser_agendada(self):
        dados = self.dados_validos()
        dados["data"] = (data_maxima_agendamento() + timedelta(days=1)).isoformat()

        resposta = self.client.post(reverse("home"), dados)

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("data", resposta.context["form"].errors)
        self.assertEqual(Consulta.objects.count(), 0)
        self.assertEqual(
            horarios_disponiveis(
                self.medico,
                data_maxima_agendamento() + timedelta(days=1),
            ),
            [],
        )

    def test_limite_de_seis_meses_respeita_o_ultimo_dia_do_mes(self):
        self.assertEqual(data_maxima_agendamento(date(2026, 8, 31)), date(2027, 2, 28))


class AcessoAosPaineisTests(TestCase):
    def setUp(self):
        especialidade = Especialidade.objects.create(nome="Cardiologia")
        self.exame = Exame.objects.create(nome="Hemograma completo")
        self.medicamento = Medicamento.objects.create(nome="Paracetamol 500 mg")
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
        usuario_outro_medico = get_user_model().objects.create_user(
            username="outro-medico",
            password="senha-segura-para-teste",
        )
        self.outro_medico = Medico.objects.create(
            nome="Lucas Freitas",
            crm="SP 456789",
            email="lucas@smarthealth.test",
            especialidade=especialidade,
            usuario=usuario_outro_medico,
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

    def confirmar_consulta(self, consulta):
        consulta.status = Consulta.Status.CONFIRMADO
        consulta.save(update_fields=("status",))

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

    def test_superadmin_filtra_consultas_sem_carregar_o_painel_completo(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.client.force_login(self.superadmin)

        resposta = self.client.get(
            reverse("consultas_filtradas"),
            {
                "busca": "Paciente da médica",
                "status": Consulta.Status.PENDENTE,
                "medico": self.medico.id,
                "especialidade": self.medico.especialidade_id,
                "data": timezone.localdate(consulta.data_horario).isoformat(),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "core/partials/consultas_lista.html")
        self.assertContains(resposta, consulta.paciente.nome)
        self.assertNotContains(resposta, "Paciente de outro médico")

    def test_medico_nao_acessa_endpoint_de_consultas_filtradas(self):
        self.client.force_login(self.medico.usuario)

        resposta = self.client.get(reverse("consultas_filtradas"))

        self.assertEqual(resposta.status_code, 403)

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

    def test_medico_cria_atendimento_em_consulta_propria(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.confirmar_consulta(consulta)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("consulta_medico_detail", args=[consulta.id]),
            {
                "sintomas": "Dor de cabeça há dois dias.",
                "diagnostico": "",
                "conduta": "Orientado repouso e hidratação.",
                "observacoes": "Retornar caso os sintomas persistam.",
            },
        )

        self.assertRedirects(
            resposta,
            reverse("consulta_medico_detail", args=[consulta.id]),
        )
        atendimento = Atendimento.objects.get(consulta=consulta)
        self.assertEqual(atendimento.sintomas, "Dor de cabeça há dois dias.")
        self.assertEqual(atendimento.diagnostico, "")

    def test_medico_nao_acessa_consulta_de_outro_medico(self):
        consulta_de_outro_medico = Consulta.objects.get(medico=self.outro_medico)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.get(
            reverse("consulta_medico_detail", args=[consulta_de_outro_medico.id])
        )

        self.assertEqual(resposta.status_code, 404)

    def test_medico_solicita_exame_em_consulta_propria(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.confirmar_consulta(consulta)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("solicitar_exame", args=[consulta.id]),
            {
                "exame": self.exame.id,
                "observacoes": "Realizar em jejum, se possível.",
            },
        )

        self.assertRedirects(
            resposta,
            reverse("consulta_medico_detail", args=[consulta.id]),
        )
        solicitacao = SolicitacaoExame.objects.get(consulta=consulta)
        self.assertEqual(solicitacao.exame, self.exame)
        self.assertEqual(solicitacao.status, SolicitacaoExame.Status.SOLICITADO)

    def test_erro_na_solicitacao_de_exame_permanece_no_formulario(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.confirmar_consulta(consulta)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("solicitar_exame", args=[consulta.id]),
            {"exame": ""},
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("exame", resposta.context["form_exame"].errors)
        self.assertFalse(SolicitacaoExame.objects.exists())

    def test_medico_emite_receita_em_consulta_propria(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.confirmar_consulta(consulta)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("emitir_receita", args=[consulta.id]),
            {
                "orientacoes": "Manter repouso e hidratação.",
                "itens-TOTAL_FORMS": "2",
                "itens-INITIAL_FORMS": "0",
                "itens-MIN_NUM_FORMS": "1",
                "itens-MAX_NUM_FORMS": "1000",
                "itens-0-medicamento": self.medicamento.id,
                "itens-0-dosagem": "500 mg",
                "itens-0-frequencia": "A cada 8 horas",
                "itens-0-duracao": "3 dias",
                "itens-0-instrucoes": "Tomar após as refeições.",
                "itens-1-medicamento": "",
                "itens-1-dosagem": "",
                "itens-1-frequencia": "",
                "itens-1-duracao": "",
                "itens-1-instrucoes": "",
            },
        )

        self.assertRedirects(
            resposta,
            reverse("consulta_medico_detail", args=[consulta.id]),
        )
        receita = Receita.objects.get(consulta=consulta)
        item = receita.itens.get()
        self.assertEqual(item.medicamento, self.medicamento)
        self.assertEqual(item.dosagem, "500 mg")

    def test_medico_nao_emite_receita_em_consulta_de_outro_medico(self):
        consulta_de_outro_medico = Consulta.objects.get(medico=self.outro_medico)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("emitir_receita", args=[consulta_de_outro_medico.id]),
            {},
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(Receita.objects.exists())

    def test_medico_nao_solicita_exame_em_consulta_de_outro_medico(self):
        consulta_de_outro_medico = Consulta.objects.get(medico=self.outro_medico)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("solicitar_exame", args=[consulta_de_outro_medico.id]),
            {"exame": self.exame.id},
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(SolicitacaoExame.objects.exists())

    def test_medico_nao_altera_registros_clinicos_fora_de_consulta_confirmada(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.client.force_login(self.medico.usuario)
        dados_receita = {
            "orientacoes": "",
            "itens-TOTAL_FORMS": "1",
            "itens-INITIAL_FORMS": "0",
            "itens-MIN_NUM_FORMS": "1",
            "itens-MAX_NUM_FORMS": "5",
            "itens-0-medicamento": self.medicamento.id,
            "itens-0-dosagem": "500 mg",
            "itens-0-frequencia": "A cada 8 horas",
            "itens-0-duracao": "3 dias",
            "itens-0-instrucoes": "",
        }

        for status, concluida_em in (
            (Consulta.Status.PENDENTE, None),
            (Consulta.Status.CANCELADO, None),
            (Consulta.Status.CONFIRMADO, timezone.now()),
        ):
            with self.subTest(status=status, concluida=bool(concluida_em)):
                consulta.status = status
                consulta.concluida_em = concluida_em
                consulta.save(update_fields=("status", "concluida_em"))

                respostas = (
                    self.client.post(
                        reverse("consulta_medico_detail", args=[consulta.id]),
                        {"sintomas": "Não deve ser salvo."},
                    ),
                    self.client.post(
                        reverse("solicitar_exame", args=[consulta.id]),
                        {"exame": self.exame.id},
                    ),
                    self.client.post(
                        reverse("emitir_receita", args=[consulta.id]),
                        dados_receita,
                    ),
                    self.client.post(reverse("salvar_prontuario", args=[consulta.id])),
                )

                for resposta in respostas:
                    self.assertRedirects(
                        resposta,
                        reverse("consulta_medico_detail", args=[consulta.id]),
                    )
                self.assertFalse(Atendimento.objects.filter(consulta=consulta).exists())
                self.assertFalse(
                    SolicitacaoExame.objects.filter(consulta=consulta).exists()
                )
                self.assertFalse(Receita.objects.filter(consulta=consulta).exists())
                self.assertFalse(Prontuario.objects.filter(paciente=consulta.paciente).exists())

    def test_superadmin_visualiza_detalhes_clinicos_da_consulta(self):
        consulta = Consulta.objects.get(medico=self.medico)
        Atendimento.objects.create(
            consulta=consulta,
            sintomas="Dor de cabeça há dois dias.",
            diagnostico="Cefaleia tensional.",
        )
        SolicitacaoExame.objects.create(consulta=consulta, exame=self.exame)
        receita = Receita.objects.create(consulta=consulta)
        receita.itens.create(
            medicamento=self.medicamento,
            dosagem="500 mg",
            frequencia="A cada 8 horas",
            duracao="3 dias",
        )
        self.client.force_login(self.superadmin)

        resposta = self.client.get(
            reverse("consulta_administrativo_detail", args=[consulta.id])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "core/consulta_administrativo_detail.html")
        self.assertContains(resposta, "Dor de cabeça há dois dias.")
        self.assertContains(resposta, self.exame.nome)
        self.assertContains(resposta, self.medicamento.nome)

    def test_medico_nao_acessa_detalhe_administrativo(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.get(
            reverse("consulta_administrativo_detail", args=[consulta.id])
        )

        self.assertEqual(resposta.status_code, 403)

    def test_superadmin_atualiza_status_da_consulta(self):
        consulta = Consulta.objects.get(medico=self.medico)
        data_consulta = timezone.localdate() + timedelta(days=2)
        while data_consulta.weekday() == 6:
            data_consulta += timedelta(days=1)
        consulta.data_horario = timezone.make_aware(
            datetime.combine(data_consulta, time(10)),
            timezone.get_current_timezone(),
        )
        consulta.save(update_fields=("data_horario",))
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("consulta_administrativo_detail", args=[consulta.id]),
            {
                "acao": "status",
                "status": Consulta.Status.CONFIRMADO,
            },
        )

        self.assertRedirects(
            resposta,
            reverse("consulta_administrativo_detail", args=[consulta.id]),
        )
        consulta.refresh_from_db()
        self.assertEqual(consulta.status, Consulta.Status.CONFIRMADO)

    def test_superadmin_reagenda_consulta_para_horario_disponivel(self):
        consulta = Consulta.objects.get(medico=self.medico)
        data_consulta = timezone.localdate() + timedelta(days=2)
        while data_consulta.weekday() == 6:
            data_consulta += timedelta(days=1)
        consulta.data_horario = timezone.make_aware(
            datetime.combine(data_consulta, time(10)),
            timezone.get_current_timezone(),
        )
        consulta.save(update_fields=("data_horario",))
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("consulta_administrativo_detail", args=[consulta.id]),
            {
                "acao": "reagendar",
                "data": data_consulta.isoformat(),
                "horario": "11:00",
            },
        )

        self.assertRedirects(
            resposta,
            reverse("consulta_administrativo_detail", args=[consulta.id]),
        )
        consulta.refresh_from_db()
        self.assertEqual(
            timezone.localtime(consulta.data_horario).time().replace(tzinfo=None),
            time(11),
        )

    def test_superadmin_nao_reagenda_para_data_posterior_a_seis_meses(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("consulta_administrativo_detail", args=[consulta.id]),
            {
                "acao": "reagendar",
                "data": (data_maxima_agendamento() + timedelta(days=1)).isoformat(),
                "horario": "10:00",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("data", resposta.context["reagendamento_form"].errors)

    def test_superadmin_nao_reagenda_para_horario_ocupado(self):
        consulta = Consulta.objects.get(medico=self.medico)
        data_consulta = timezone.localdate() + timedelta(days=2)
        while data_consulta.weekday() == 6:
            data_consulta += timedelta(days=1)
        consulta.data_horario = timezone.make_aware(
            datetime.combine(data_consulta, time(10)),
            timezone.get_current_timezone(),
        )
        consulta.save(update_fields=("data_horario",))
        paciente = Paciente.objects.create(
            nome="Paciente com horário reservado",
            cpf="99988877766",
            email="horario.reservado@smarthealth.test",
            telefone="(11) 96666-0000",
            data_nascimento="1988-03-10",
        )
        Consulta.objects.create(
            paciente=paciente,
            medico=self.medico,
            data_horario=timezone.make_aware(
                datetime.combine(data_consulta, time(11)),
                timezone.get_current_timezone(),
            ),
        )
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("consulta_administrativo_detail", args=[consulta.id]),
            {
                "acao": "reagendar",
                "data": data_consulta.isoformat(),
                "horario": "11:00",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("horario", resposta.context["reagendamento_form"].errors)
        consulta.refresh_from_db()
        self.assertEqual(
            timezone.localtime(consulta.data_horario).time().replace(tzinfo=None),
            time(10),
        )
        self.assertEqual(consulta.status, Consulta.Status.PENDENTE)

    def test_superadmin_exclui_consulta_cancelada_apos_confirmacao(self):
        consulta = Consulta.objects.get(medico=self.medico)
        consulta.status = Consulta.Status.CANCELADO
        consulta.save(update_fields=("status",))
        self.client.force_login(self.superadmin)

        resposta = self.client.get(
            reverse("consulta_administrativo_detail", args=[consulta.id])
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Excluir consulta cancelada")

        resposta = self.client.post(reverse("excluir_consulta", args=[consulta.id]))

        self.assertRedirects(resposta, reverse("dashboard"))
        self.assertFalse(Consulta.objects.filter(pk=consulta.id).exists())

    def test_superadmin_nao_exclui_consulta_nao_cancelada(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.client.force_login(self.superadmin)

        resposta = self.client.post(reverse("excluir_consulta", args=[consulta.id]))

        self.assertEqual(resposta.status_code, 404)

    def test_medico_filtra_consultas_proprias_e_navega_paginacao(self):
        for indice in range(11):
            paciente = Paciente.objects.create(
                nome=f"Paciente filtro {indice:02d}",
                cpf=f"70000000{indice:03d}",
                email=f"filtro{indice}@smarthealth.test",
                telefone="11988880000",
                data_nascimento="1990-01-01",
            )
            Consulta.objects.create(
                paciente=paciente,
                medico=self.medico,
                data_horario=timezone.make_aware(
                    datetime.combine(
                        timezone.localdate() + timedelta(days=indice + 2),
                        time(9),
                    ),
                    timezone.get_current_timezone(),
                ),
                status=Consulta.Status.CONFIRMADO,
            )
        self.client.force_login(self.medico.usuario)

        resposta = self.client.get(
            reverse("consultas_medico_filtradas"),
            {"busca": "Paciente filtro", "status": Consulta.Status.CONFIRMADO},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "core/partials/consultas_medico_lista.html")
        self.assertEqual(resposta.context["page_obj"].paginator.count, 11)
        self.assertContains(resposta, "Paciente filtro 00")
        self.assertNotContains(resposta, "Paciente de outro médico")

        resposta = self.client.get(
            reverse("consultas_medico_filtradas"),
            {
                "busca": "Paciente filtro",
                "status": Consulta.Status.CONFIRMADO,
                "page": 2,
            },
        )

        self.assertEqual(resposta.context["page_obj"].number, 2)
        self.assertContains(resposta, "Paciente filtro 10")

        resposta = self.client.get(
            reverse("consultas_medico_filtradas"),
            {
                "busca": "Paciente filtro",
                "data": (timezone.localdate() + timedelta(days=12)).isoformat(),
            },
        )

        self.assertContains(resposta, "Paciente filtro 10")
        self.assertNotContains(resposta, "Paciente filtro 09")

    def test_superadmin_nao_acessa_listagem_parcial_do_painel_medico(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.get(reverse("consultas_medico_filtradas"))

        self.assertEqual(resposta.status_code, 403)

    def test_medico_so_conclui_consulta_confirmada_com_atendimento(self):
        consulta = Consulta.objects.get(medico=self.medico)
        consulta.status = Consulta.Status.CONFIRMADO
        consulta.save(update_fields=("status",))
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(
            reverse("concluir_consulta_medico", args=[consulta.id])
        )

        self.assertRedirects(
            resposta, reverse("consulta_medico_detail", args=[consulta.id])
        )
        consulta.refresh_from_db()
        self.assertEqual(consulta.status, Consulta.Status.CONFIRMADO)

        Atendimento.objects.create(consulta=consulta, sintomas="Dor persistente.")
        resposta = self.client.post(
            reverse("concluir_consulta_medico", args=[consulta.id])
        )

        self.assertRedirects(
            resposta, reverse("consulta_medico_detail", args=[consulta.id])
        )
        consulta.refresh_from_db()
        self.assertEqual(consulta.status, Consulta.Status.CONFIRMADO)
        self.assertIsNotNone(consulta.concluida_em)

    def test_prontuario_reune_dados_clinicos_e_nao_muda_apos_conclusao(self):
        consulta = Consulta.objects.get(medico=self.medico)
        self.confirmar_consulta(consulta)
        atendimento = Atendimento.objects.create(
            consulta=consulta,
            sexo=Atendimento.Sexo.FEMININO,
            sintomas="Dor de cabeça há dois dias.",
            diagnostico="Cefaleia tensional.",
            conduta="Repouso e hidratação.",
        )
        SolicitacaoExame.objects.create(consulta=consulta, exame=self.exame)
        receita = Receita.objects.create(
            consulta=consulta,
            orientacoes="Retornar se a dor persistir.",
        )
        receita.itens.create(
            medicamento=self.medicamento,
            dosagem="500 mg",
            frequencia="A cada 8 horas",
            duracao="3 dias",
        )
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(reverse("salvar_prontuario", args=[consulta.id]))

        self.assertRedirects(
            resposta, reverse("consulta_medico_detail", args=[consulta.id])
        )
        prontuario = Prontuario.objects.get(paciente=consulta.paciente)
        self.assertIn("Sexo: Feminino", prontuario.anamnese)
        self.assertIn(atendimento.sintomas, prontuario.anamnese)
        self.assertIn(atendimento.diagnostico, prontuario.evolucao_clinica)
        self.assertIn(self.exame.nome, prontuario.evolucao_clinica)
        self.assertIn(self.medicamento.nome, prontuario.prescricoes)

        consulta.concluida_em = timezone.now()
        consulta.save(update_fields=("concluida_em",))
        prontuario_atualizado_em = prontuario.atualizado_em
        atendimento.conduta = "Conduta que não deve entrar após a conclusão."
        atendimento.save()

        resposta = self.client.post(reverse("salvar_prontuario", args=[consulta.id]))

        self.assertRedirects(
            resposta, reverse("consulta_medico_detail", args=[consulta.id])
        )
        prontuario.refresh_from_db()
        self.assertEqual(prontuario.atualizado_em, prontuario_atualizado_em)
        self.assertNotIn("não deve entrar", prontuario.evolucao_clinica)

    def test_medico_nao_cria_prontuario_para_consulta_de_outro_medico(self):
        consulta = Consulta.objects.get(medico=self.outro_medico)
        self.client.force_login(self.medico.usuario)

        resposta = self.client.post(reverse("salvar_prontuario", args=[consulta.id]))

        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(Prontuario.objects.exists())

    def test_superadmin_cadastra_medico_com_usuario_sem_privilegios(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("cadastrar_medico"),
            {
                "nome": "Beatriz Moura",
                "crm": "RJ 123456",
                "email": "beatriz@smarthealth.test",
                "telefone": "(21) 98888-0000",
                "especialidade": self.medico.especialidade_id,
            },
        )

        senha = self.client.session["credenciais_medico"]["senha"]
        self.assertRedirects(resposta, reverse("dashboard"))
        medico = Medico.objects.get(email="beatriz@smarthealth.test")
        self.assertIsNotNone(medico.usuario)
        self.assertFalse(medico.usuario.is_staff)
        self.assertFalse(medico.usuario.is_superuser)
        self.assertEqual(len(senha), 10)

    def test_detalhe_do_medico_exibe_acao_para_redefinir_senha(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.get(
            reverse("medico_administrativo_detail", args=[self.medico.id])
        )

        self.assertContains(resposta, "Redefinir senha")
        self.assertContains(
            resposta,
            reverse("redefinir_senha_medico", args=[self.medico.id]),
        )

    def test_superadmin_redefine_senha_automatica_com_composicao_esperada(self):
        senha_anterior = self.medico.usuario.password
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("redefinir_senha_medico", args=[self.medico.id]),
            {"usuario": "admin", "senha": "senha-segura-para-teste"},
        )

        senha = self.client.session["credenciais_medico"]["senha"]
        self.assertRedirects(resposta, reverse("dashboard"))
        self.medico.usuario.refresh_from_db()
        self.assertNotEqual(self.medico.usuario.password, senha_anterior)
        self.assertEqual(len(senha), 10)
        self.assertTrue(any(caractere.islower() for caractere in senha))
        self.assertTrue(any(caractere.isupper() for caractere in senha))
        self.assertTrue(any(caractere.isdigit() for caractere in senha))
        self.assertEqual(self.medico.redefinicoes_senha.filter(foi_redefinicao=True).count(), 1)

    def test_redefinicao_de_senha_respeita_intervalo_de_quinze_dias(self):
        RedefinicaoSenhaMedico.objects.create(
            medico=self.medico,
            redefinida_por=self.superadmin,
            senha_hash="hash-de-teste",
            foi_redefinicao=True,
        )
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("redefinir_senha_medico", args=[self.medico.id]),
            {"usuario": "admin", "senha": "senha-segura-para-teste"},
        )

        self.assertRedirects(resposta, reverse("dashboard"))
        self.assertEqual(self.medico.redefinicoes_senha.count(), 1)
