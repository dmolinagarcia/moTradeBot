# Generated by Django 3.2.8 on 2024-02-08 21:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0044_auto_20240208_2105'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='inError',
            field=models.BooleanField(default=False),
        ),
    ]
