# Generated by Django 3.2.8 on 2024-01-12 17:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0032_strategy_currentprofit'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='stopLossCurrent',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='takeProfitCurrent',
            field=models.FloatField(null=True),
        ),
    ]
