from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Especialidade, Exame, Medicamento, Medico


ESPECIALIDADES = [
    {
        "nome": "Clínica geral",
        "descricao": "Avaliação, prevenção e acompanhamento da saúde do paciente.",
    },
    {
        "nome": "Cardiologia",
        "descricao": "Prevenção, diagnóstico e acompanhamento da saúde cardiovascular.",
    },
    {
        "nome": "Dermatologia",
        "descricao": "Cuidados clínicos e preventivos para a saúde da pele.",
    },
    {
        "nome": "Pediatria",
        "descricao": "Acompanhamento da saúde de crianças e adolescentes.",
    },
    {
        "nome": "Endocrinologia",
        "descricao": "Prevenção e acompanhamento de condições hormonais e metabólicas.",
    },
    {
        "nome": "Gastroenterologia",
        "descricao": "Cuidado especializado para a saúde do sistema digestivo.",
    },
    {
        "nome": "Neurologia",
        "descricao": "Avaliação e acompanhamento da saúde do sistema nervoso.",
    },
    {
        "nome": "Ortopedia e traumatologia",
        "descricao": "Atenção a ossos, articulações, músculos e lesões.",
    },
]

MEDICOS = [
    {
        "nome": "Marina Alves",
        "crm": "SP 123456",
        "email": "marina.alves@smarthealth.test",
        "telefone": "(11) 4000-1001",
        "especialidade": "Clínica geral",
    },
    {
        "nome": "Ricardo Nunes",
        "crm": "SP 123457",
        "email": "ricardo.nunes@smarthealth.test",
        "telefone": "(11) 4000-1002",
        "especialidade": "Cardiologia",
    },
    {
        "nome": "Camila Rocha",
        "crm": "SP 123458",
        "email": "camila.rocha@smarthealth.test",
        "telefone": "(11) 4000-1003",
        "especialidade": "Dermatologia",
    },
    {
        "nome": "João Mendes",
        "crm": "SP 123459",
        "email": "joao.mendes@smarthealth.test",
        "telefone": "(11) 4000-1004",
        "especialidade": "Pediatria",
    },
    {
        "nome": "Renata Lima",
        "crm": "SP 123460",
        "email": "renata.lima@smarthealth.test",
        "telefone": "(11) 4000-1005",
        "especialidade": "Endocrinologia",
    },
    {
        "nome": "Bruno Costa",
        "crm": "SP 123461",
        "email": "bruno.costa@smarthealth.test",
        "telefone": "(11) 4000-1006",
        "especialidade": "Gastroenterologia",
    },
    {
        "nome": "Fernanda Araújo",
        "crm": "SP 123462",
        "email": "fernanda.araujo@smarthealth.test",
        "telefone": "(11) 4000-1007",
        "especialidade": "Neurologia",
    },
    {
        "nome": "Marcos Oliveira",
        "crm": "SP 123463",
        "email": "marcos.oliveira@smarthealth.test",
        "telefone": "(11) 4000-1008",
        "especialidade": "Ortopedia e traumatologia",
    },
    {
        "nome": "João Silva",
        "crm": "123",
        "email": "jemail@email.com",
        "telefone": "123",
        "especialidade": "Clínica geral",
    },
]

EXAMES = [
    {
        "nome": "Hemograma completo",
        "descricao": "Avaliação dos componentes celulares do sangue.",
        "preparo": "Seguir orientação médica ou do laboratório responsável.",
    },
    {
        "nome": "Glicemia em jejum",
        "descricao": "Medição da concentração de glicose no sangue.",
        "preparo": "Seguir orientação médica ou do laboratório responsável.",
    },
    {
        "nome": "Perfil lipídico",
        "descricao": "Avaliação de colesterol e triglicerídeos.",
        "preparo": "Seguir orientação médica ou do laboratório responsável.",
    },
    {
        "nome": "Eletrocardiograma",
        "descricao": "Registro da atividade elétrica do coração.",
        "preparo": "Seguir orientação médica ou do serviço responsável.",
    },
]

MEDICAMENTOS = [
    {
        "nome": "Paracetamol",
        "principio_ativo": "Paracetamol",
        "apresentacao": "Comprimido",
    },
    {
        "nome": "Ibuprofeno",
        "principio_ativo": "Ibuprofeno",
        "apresentacao": "Comprimido",
    },
    {
        "nome": "Loratadina",
        "principio_ativo": "Loratadina",
        "apresentacao": "Comprimido",
    },
    {
        "nome": "Omeprazol",
        "principio_ativo": "Omeprazol",
        "apresentacao": "Cápsula",
    },
]


class Command(BaseCommand):
    help = "Cria ou atualiza os dados fixos de demonstração da SmartHealth."

    def handle(self, *args, **options):
        totais = {"criados": 0, "atualizados": 0}

        with transaction.atomic():
            self._normalizar_nomes_de_especialidades()
            especialidades = {}
            medicos = {}

            for dados in ESPECIALIDADES:
                especialidade, criada = Especialidade.objects.update_or_create(
                    nome=dados["nome"],
                    defaults={"descricao": dados["descricao"]},
                )
                especialidades[especialidade.nome] = especialidade
                self._registrar_resultado(criada, totais)

            for dados in MEDICOS:
                especialidade = especialidades[dados["especialidade"]]
                medico, criado = Medico.objects.update_or_create(
                    crm=dados["crm"],
                    defaults={
                        "nome": dados["nome"],
                        "email": dados["email"],
                        "telefone": dados["telefone"],
                        "especialidade": especialidade,
                        "ativo": True,
                    },
                )
                medicos[medico.crm] = medico
                self._registrar_resultado(criado, totais)

            self._criar_usuario_medico_de_demonstracao(medicos["123"], totais)

            for dados in EXAMES:
                _, criado = Exame.objects.update_or_create(
                    nome=dados["nome"],
                    defaults={
                        "descricao": dados["descricao"],
                        "preparo": dados["preparo"],
                    },
                )
                self._registrar_resultado(criado, totais)

            for dados in MEDICAMENTOS:
                _, criado = Medicamento.objects.update_or_create(
                    nome=dados["nome"],
                    defaults={
                        "principio_ativo": dados["principio_ativo"],
                        "apresentacao": dados["apresentacao"],
                    },
                )
                self._registrar_resultado(criado, totais)

        self.stdout.write(
            self.style.SUCCESS(
                "Dados fixos processados: "
                f"{totais['criados']} criados e {totais['atualizados']} atualizados."
            )
        )

    def _registrar_resultado(self, criado, totais):
        totais["criados" if criado else "atualizados"] += 1

    def _criar_usuario_medico_de_demonstracao(self, medico, totais):
        """Cria uma conta local previsível para demonstrar o painel médico."""
        User = get_user_model()

        usuario_medico, criado = User.objects.get_or_create(username="usermedico")
        usuario_medico.email = "usermedico@smarthealth.test"
        usuario_medico.is_staff = False
        usuario_medico.is_superuser = False
        usuario_medico.is_active = True
        usuario_medico.set_password("medicopassword")
        usuario_medico.save()
        self._registrar_resultado(criado, totais)

        Medico.objects.filter(usuario=usuario_medico).exclude(pk=medico.pk).update(
            usuario=None
        )
        medico.usuario = usuario_medico
        medico.ativo = True
        medico.save(update_fields=("usuario", "ativo"))

    def _normalizar_nomes_de_especialidades(self):
        """Mantém os dados antigos compatíveis com a capitalização atual."""
        nome_antigo = "Clínica Geral"
        nome_atual = "Clínica geral"
        especialidade_antiga = Especialidade.objects.filter(nome=nome_antigo).first()
        especialidade_atual = Especialidade.objects.filter(nome=nome_atual).first()

        if not especialidade_antiga:
            return
        if especialidade_atual:
            Medico.objects.filter(especialidade=especialidade_antiga).update(
                especialidade=especialidade_atual
            )
            especialidade_antiga.delete()
            return

        especialidade_antiga.nome = nome_atual
        especialidade_antiga.save(update_fields=("nome",))
