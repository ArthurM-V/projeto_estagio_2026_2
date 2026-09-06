from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="RedefinicaoSenhaMedico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("senha_hash", models.CharField(max_length=128)),
                ("foi_redefinicao", models.BooleanField(default=True)),
                ("redefinida_em", models.DateTimeField(auto_now_add=True)),
                ("medico", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="redefinicoes_senha", to="core.medico")),
                ("redefinida_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-redefinida_em",), "verbose_name": "redefinição de senha de médico", "verbose_name_plural": "redefinições de senha de médicos"},
        )
    ]
