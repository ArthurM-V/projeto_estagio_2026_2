from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Convenio, Especialidade, Exame, Medicamento, Medico


ESPECIALIDADES = [
    {
        "nome": "Clínica Geral",
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
]

MEDICOS = [
    {
        "nome": "Marina Alves",
        "crm": "SP 123456",
        "email": "marina.alves@smarthealth.test",
        "telefone": "(11) 4000-1001",
        "especialidade": "Clínica Geral",
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
]

CONVENIOS = [
    {"nome": "Vida Plena Saúde", "cnpj": "12.345.678/0001-90", "telefone": "0800 100 1000"},
    {"nome": "Bem-Estar Assistência", "cnpj": "23.456.789/0001-01", "telefone": "0800 200 2000"},
    {"nome": "Saúde Integral", "cnpj": "34.567.890/0001-12", "telefone": "0800 300 3000"},
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
            especialidades = {}

            for dados in ESPECIALIDADES:
                especialidade, criada = Especialidade.objects.update_or_create(
                    nome=dados["nome"],
                    defaults={"descricao": dados["descricao"]},
                )
                especialidades[especialidade.nome] = especialidade
                self._registrar_resultado(criada, totais)

            for dados in MEDICOS:
                especialidade = especialidades[dados["especialidade"]]
                _, criado = Medico.objects.update_or_create(
                    crm=dados["crm"],
                    defaults={
                        "nome": dados["nome"],
                        "email": dados["email"],
                        "telefone": dados["telefone"],
                        "especialidade": especialidade,
                        "ativo": True,
                    },
                )
                self._registrar_resultado(criado, totais)

            for dados in CONVENIOS:
                _, criado = Convenio.objects.update_or_create(
                    cnpj=dados["cnpj"],
                    defaults={
                        "nome": dados["nome"],
                        "telefone": dados["telefone"],
                        "ativo": True,
                    },
                )
                self._registrar_resultado(criado, totais)

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
