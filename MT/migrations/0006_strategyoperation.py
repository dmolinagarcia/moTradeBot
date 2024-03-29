# Generated by Django 3.1.5 on 2021-01-30 16:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0005_strategy_lastupdated'),
    ]

    operations = [
        migrations.CreateModel(
            name='StrategyOperation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operID', models.IntegerField()),
                ('timestampOpen', models.DateTimeField(auto_now_add=True)),
                ('timestampClose', models.DateTimeField(null=True)),
                ('strategy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='MT.strategy')),
            ],
        ),
    ]
