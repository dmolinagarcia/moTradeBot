# Generated by Django 3.2.8 on 2024-01-16 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0036_auto_20240115_2116'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategystate',
            name='currentProfit',
            field=models.FloatField(null=True),
        ),
    ]
