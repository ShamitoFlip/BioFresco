from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('AppInventario', '0006_estilista_serviciorealizado_email_cliente_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Estilista',
            new_name='Empleado',
        ),
    ]
