# Generated by Django 3.1.5 on 2021-01-29 20:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='isRunning',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]
