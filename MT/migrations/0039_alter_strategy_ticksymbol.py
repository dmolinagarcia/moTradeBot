# Generated by Django 3.2.8 on 2024-01-18 20:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0038_auto_20240118_1203'),
    ]

    operations = [
        migrations.AlterField(
            model_name='strategy',
            name='tickSymbol',
            field=models.CharField(max_length=32, null=True),
        ),
    ]