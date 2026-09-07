from django.db import migrations, models
from django.db.models import Q


def migrar_status_e_conclusao(apps, schema_editor):
    Consulta = apps.get_model("core", "Consulta")
    Atendimento = apps.get_model("core", "Atendimento")
    atendimentos_por_consulta = dict(
        Atendimento.objects.values_list("consulta_id", "atualizado_em")
    )

    for consulta in Consulta.objects.filter(
        status__in=("confirmada", "cancelada", "ausente", "concluida")
    ).iterator():
        campos_atualizados = ["status"]
        if consulta.status == "confirmada":
            consulta.status = "confirmado"
        elif consulta.status in ("cancelada", "ausente"):
            consulta.status = "cancelado"
        else:
            consulta.status = "confirmado"
            consulta.concluida_em = atendimentos_por_consulta.get(
                consulta.pk, consulta.criado_em
            )
            campos_atualizados.append("concluida_em")
        consulta.save(update_fields=campos_atualizados)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_reestrutura_prontuario_clinico")]

    operations = [
        migrations.AddField(
            model_name="consulta",
            name="concluida_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="consulta",
            name="medico_horario_ativo_unico",
        ),
        migrations.RunPython(migrar_status_e_conclusao, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="consulta",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("confirmado", "Confirmado"),
                    ("cancelado", "Cancelado"),
                ],
                default="pendente",
                max_length=12,
            ),
        ),
        migrations.AddConstraint(
            model_name="consulta",
            constraint=models.UniqueConstraint(
                condition=Q(
                    status__in=("pendente", "confirmado"),
                    concluida_em__isnull=True,
                ),
                fields=("medico", "data_horario"),
                name="medico_horario_ativo_unico",
            ),
        ),
    ]
