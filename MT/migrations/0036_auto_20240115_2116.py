# Generated by Django 3.2.8 on 2024-01-15 21:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0035_auto_20240115_2103'),
    ]

    operations = [
        migrations.AlterField(
            model_name='strategy',
            name='sleep',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='strategy',
            name='stopLossCurrent',
            field=models.FloatField(blank=True, null=True),
        ),
    ]