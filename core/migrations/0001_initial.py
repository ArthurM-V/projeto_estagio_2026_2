from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Convenio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("cnpj", models.CharField(max_length=18, unique=True, verbose_name="CNPJ")),
                ("telefone", models.CharField(blank=True, max_length=20)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={"ordering": ("nome",), "verbose_name": "convênio", "verbose_name_plural": "convênios"},
        ),
        migrations.CreateModel(
            name="Especialidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("descricao", models.TextField(blank=True)),
            ],
            options={"ordering": ("nome",), "verbose_name": "especialidade", "verbose_name_plural": "especialidades"},
        ),
        migrations.CreateModel(
            name="Exame",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150, unique=True)),
                ("descricao", models.TextField(blank=True)),
                ("preparo", models.TextField(blank=True)),
            ],
            options={"ordering": ("nome",), "verbose_name": "exame", "verbose_name_plural": "exames"},
        ),
        migrations.CreateModel(
            name="Medicamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150, unique=True)),
                ("principio_ativo", models.CharField(blank=True, max_length=150)),
                ("apresentacao", models.CharField(blank=True, max_length=150)),
            ],
            options={"ordering": ("nome",), "verbose_name": "medicamento", "verbose_name_plural": "medicamentos"},
        ),
        migrations.CreateModel(
            name="Paciente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120)),
                ("cpf", models.CharField(max_length=14, unique=True, verbose_name="CPF")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("telefone", models.CharField(max_length=20)),
                ("data_nascimento", models.DateField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("nome",), "verbose_name": "paciente", "verbose_name_plural": "pacientes"},
        ),
        migrations.CreateModel(
            name="Medico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120)),
                ("crm", models.CharField(max_length=20, unique=True, verbose_name="CRM")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("telefone", models.CharField(blank=True, max_length=20)),
                ("ativo", models.BooleanField(default=True)),
                ("especialidade", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="medicos", to="core.especialidade")),
                ("usuario", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="medico", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("nome",), "verbose_name": "médico", "verbose_name_plural": "médicos"},
        ),
        migrations.CreateModel(
            name="Prontuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alergias", models.TextField(blank=True)),
                ("historico_medico", models.TextField(blank=True)),
                ("observacoes", models.TextField(blank=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("paciente", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="prontuario", to="core.paciente")),
            ],
            options={"verbose_name": "prontuário", "verbose_name_plural": "prontuários"},
        ),
        migrations.CreateModel(
            name="PacienteConvenio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_carteirinha", models.CharField(max_length=50)),
                ("validade", models.DateField(blank=True, null=True)),
                ("ativo", models.BooleanField(default=True)),
                ("convenio", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pacientes", to="core.convenio")),
                ("paciente", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="convenios", to="core.paciente")),
            ],
            options={"verbose_name": "convênio do paciente", "verbose_name_plural": "convênios dos pacientes"},
        ),
        migrations.CreateModel(
            name="Consulta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data_horario", models.DateTimeField()),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("confirmada", "Confirmada"), ("cancelada", "Cancelada"), ("ausente", "Ausente"), ("concluida", "Concluída")], default="pendente", max_length=12)),
                ("observacoes", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("medico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consultas", to="core.medico")),
                ("paciente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consultas", to="core.paciente")),
            ],
            options={"ordering": ("data_horario",), "verbose_name": "consulta", "verbose_name_plural": "consultas"},
        ),
        migrations.CreateModel(
            name="Atendimento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sintomas", models.TextField(blank=True)),
                ("diagnostico", models.TextField(blank=True)),
                ("conduta", models.TextField(blank=True)),
                ("observacoes", models.TextField(blank=True)),
                ("registrado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("consulta", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="atendimento", to="core.consulta")),
            ],
            options={"verbose_name": "atendimento", "verbose_name_plural": "atendimentos"},
        ),
        migrations.CreateModel(
            name="Pagamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valor", models.DecimalField(decimal_places=2, max_digits=10)),
                ("metodo", models.CharField(choices=[("dinheiro", "Dinheiro"), ("cartao", "Cartão"), ("pix", "PIX"), ("convenio", "Convênio")], max_length=10)),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("pago", "Pago"), ("estornado", "Estornado")], default="pendente", max_length=10)),
                ("pago_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("consulta", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pagamentos", to="core.consulta")),
            ],
            options={"ordering": ("-criado_em",), "verbose_name": "pagamento", "verbose_name_plural": "pagamentos"},
        ),
        migrations.CreateModel(
            name="Receita",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orientacoes", models.TextField(blank=True)),
                ("emitida_em", models.DateTimeField(auto_now_add=True)),
                ("consulta", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receitas", to="core.consulta")),
            ],
            options={"ordering": ("-emitida_em",), "verbose_name": "receita", "verbose_name_plural": "receitas"},
        ),
        migrations.CreateModel(
            name="ReceitaMedicamento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dosagem", models.CharField(max_length=100)),
                ("frequencia", models.CharField(max_length=100)),
                ("duracao", models.CharField(max_length=100)),
                ("instrucoes", models.TextField(blank=True)),
                ("medicamento", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prescricoes", to="core.medicamento")),
                ("receita", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="itens", to="core.receita")),
            ],
            options={"verbose_name": "medicamento prescrito", "verbose_name_plural": "medicamentos prescritos"},
        ),
        migrations.CreateModel(
            name="SolicitacaoExame",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("solicitado", "Solicitado"), ("realizado", "Realizado"), ("cancelado", "Cancelado")], default="solicitado", max_length=12)),
                ("observacoes", models.TextField(blank=True)),
                ("solicitado_em", models.DateTimeField(auto_now_add=True)),
                ("consulta", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="solicitacoes_exames", to="core.consulta")),
                ("exame", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitacoes", to="core.exame")),
            ],
            options={"verbose_name": "solicitação de exame", "verbose_name_plural": "solicitações de exames"},
        ),
        migrations.AddConstraint(
            model_name="pacienteconvenio",
            constraint=models.UniqueConstraint(fields=("paciente", "convenio"), name="paciente_convenio_unico"),
        ),
        migrations.AddConstraint(
            model_name="consulta",
            constraint=models.UniqueConstraint(condition=Q(("status__in", ("pendente", "confirmada"))), fields=("medico", "data_horario"), name="medico_horario_ativo_unico"),
        ),
        migrations.AddIndex(
            model_name="consulta",
            index=models.Index(fields=["data_horario", "status"], name="consulta_data_status_idx"),
        ),
    ]
