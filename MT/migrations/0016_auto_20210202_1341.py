# Generated by Django 3.1.5 on 2021-02-02 12:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0015_auto_20210201_2152'),
    ]

    operations = [
        migrations.AlterField(
            model_name='strategyoperation',
            name='strategy',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MT.strategy'),
        ),
        migrations.AlterField(
            model_name='strategystate',
            name='strategy',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MT.strategy'),
        ),
    ]