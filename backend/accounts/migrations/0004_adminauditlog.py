from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_tokentransaction_transaction_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('token_grant', 'Token Grant'), ('token_revoke', 'Token Revoke'), ('token_transfer', 'Token Transfer'), ('token_view', 'Token View')], max_length=40)),
                ('resource_type', models.CharField(max_length=60)),
                ('resource_id', models.CharField(blank=True, max_length=120)),
                ('detail', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name='admin_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
