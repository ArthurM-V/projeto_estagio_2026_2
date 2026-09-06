from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_rename_alergias_prontuario_avaliacao_and_more")]

    operations = [
        migrations.RenameField(model_name="prontuario", old_name="avaliacao", new_name="anamnese"),
        migrations.RenameField(model_name="prontuario", old_name="objetivo", new_name="evolucao_clinica"),
        migrations.RenameField(model_name="prontuario", old_name="plano", new_name="prescricoes"),
        migrations.RemoveField(model_name="prontuario", name="subjetivo"),
        migrations.AddField(
            model_name="atendimento",
            name="sexo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("feminino", "Feminino"),
                    ("masculino", "Masculino"),
                    ("outro", "Outro"),
                    ("nao_informado", "Prefiro não informar"),
                ],
                max_length=15,
            ),
        ),
    ]
