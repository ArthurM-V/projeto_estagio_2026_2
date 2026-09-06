from django.conf import settings
from django.db import models
from django.db.models import Q


class Especialidade(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "especialidade"
        verbose_name_plural = "especialidades"

    def __str__(self):
        return self.nome


class Medico(models.Model):
    nome = models.CharField(max_length=120)
    crm = models.CharField("CRM", max_length=20, unique=True)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    especialidade = models.ForeignKey(Especialidade, on_delete=models.PROTECT, related_name="medicos")
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="medico",
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "médico"
        verbose_name_plural = "médicos"

    def __str__(self):
        return f"Dr(a). {self.nome} — {self.especialidade}"


class RedefinicaoSenhaMedico(models.Model):
    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, related_name="redefinicoes_senha")
    redefinida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    senha_hash = models.CharField(max_length=128)
    foi_redefinicao = models.BooleanField(default=True)
    redefinida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-redefinida_em",)
        verbose_name = "redefinição de senha de médico"
        verbose_name_plural = "redefinições de senha de médicos"


class Paciente(models.Model):
    nome = models.CharField(max_length=120)
    cpf = models.CharField("CPF", max_length=14, unique=True)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20)
    data_nascimento = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"

    def __str__(self):
        return self.nome


class Prontuario(models.Model):
    paciente = models.OneToOneField(Paciente, on_delete=models.CASCADE, related_name="prontuario")
    alergias = models.TextField(blank=True)
    historico_medico = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "prontuário"
        verbose_name_plural = "prontuários"

    def __str__(self):
        return f"Prontuário — {self.paciente}"


class Convenio(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "convênio"
        verbose_name_plural = "convênios"

    def __str__(self):
        return self.nome


class PacienteConvenio(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="convenios")
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT, related_name="pacientes")
    numero_carteirinha = models.CharField(max_length=50)
    validade = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("paciente", "convenio"), name="paciente_convenio_unico")
        ]
        verbose_name = "convênio do paciente"
        verbose_name_plural = "convênios dos pacientes"

    def __str__(self):
        return f"{self.paciente} — {self.convenio}"


class Consulta(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADA = "confirmada", "Confirmada"
        CANCELADA = "cancelada", "Cancelada"
        AUSENTE = "ausente", "Ausente"
        CONCLUIDA = "concluida", "Concluída"

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="consultas")
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT, related_name="consultas")
    data_horario = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("data_horario",)
        indexes = [
            models.Index(
                fields=("data_horario", "status"),
                name="consulta_data_status_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("medico", "data_horario"),
                condition=Q(status__in=("pendente", "confirmada")),
                name="medico_horario_ativo_unico",
            )
        ]
        verbose_name = "consulta"
        verbose_name_plural = "consultas"

    def __str__(self):
        return f"{self.paciente} — {self.data_horario:%d/%m/%Y %H:%M}"


class Medicamento(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    principio_ativo = models.CharField(max_length=150, blank=True)
    apresentacao = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "medicamento"
        verbose_name_plural = "medicamentos"

    def __str__(self):
        return self.nome


class Atendimento(models.Model):
    consulta = models.OneToOneField(Consulta, on_delete=models.PROTECT, related_name="atendimento")
    sintomas = models.TextField()
    diagnostico = models.TextField(blank=True)
    conduta = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "atendimento"
        verbose_name_plural = "atendimentos"

    def __str__(self):
        return f"Atendimento — {self.consulta}"


class Receita(models.Model):
    consulta = models.ForeignKey(Consulta, on_delete=models.PROTECT, related_name="receitas")
    orientacoes = models.TextField(blank=True)
    emitida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-emitida_em",)
        verbose_name = "receita"
        verbose_name_plural = "receitas"

    def __str__(self):
        return f"Receita de {self.consulta.paciente} — {self.emitida_em:%d/%m/%Y}"


class ReceitaMedicamento(models.Model):
    receita = models.ForeignKey(Receita, on_delete=models.CASCADE, related_name="itens")
    medicamento = models.ForeignKey(Medicamento, on_delete=models.PROTECT, related_name="prescricoes")
    dosagem = models.CharField(max_length=100)
    frequencia = models.CharField(max_length=100)
    duracao = models.CharField(max_length=100)
    instrucoes = models.TextField(blank=True)

    class Meta:
        verbose_name = "medicamento prescrito"
        verbose_name_plural = "medicamentos prescritos"

    def __str__(self):
        return f"{self.medicamento} — {self.dosagem}"


class Exame(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    descricao = models.TextField(blank=True)
    preparo = models.TextField(blank=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "exame"
        verbose_name_plural = "exames"

    def __str__(self):
        return self.nome


class SolicitacaoExame(models.Model):
    class Status(models.TextChoices):
        SOLICITADO = "solicitado", "Solicitado"
        REALIZADO = "realizado", "Realizado"
        CANCELADO = "cancelado", "Cancelado"

    consulta = models.ForeignKey(Consulta, on_delete=models.CASCADE, related_name="solicitacoes_exames")
    exame = models.ForeignKey(Exame, on_delete=models.PROTECT, related_name="solicitacoes")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SOLICITADO)
    observacoes = models.TextField(blank=True)
    solicitado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "solicitação de exame"
        verbose_name_plural = "solicitações de exames"

    def __str__(self):
        return f"{self.exame} — {self.consulta}"


class Pagamento(models.Model):
    class Metodo(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"
        PIX = "pix", "PIX"
        CONVENIO = "convenio", "Convênio"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        ESTORNADO = "estornado", "Estornado"

    consulta = models.ForeignKey(Consulta, on_delete=models.PROTECT, related_name="pagamentos")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=10, choices=Metodo.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    pago_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-criado_em",)
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"

    def __str__(self):
        return f"R$ {self.valor} — {self.consulta}"
