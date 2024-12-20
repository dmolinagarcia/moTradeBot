# Generated by Django 3.2.8 on 2024-11-17 17:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0051_strategystate_stoplosscurrent'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='configGlobalTPEnabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='configGlobalTPSleepdown',
            field=models.IntegerField(default=100),
        ),
        migrations.AddField(
            model_name='profile',
            name='configGlobalTPThreshold',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
    ]
