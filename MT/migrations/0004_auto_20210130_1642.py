# Generated by Django 3.1.5 on 2021-01-30 15:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0003_auto_20210130_1125'),
    ]

    operations = [
        migrations.RenameField(
            model_name='strategy',
            old_name='maxCurrentRat',
            new_name='maxCurrentRate',
        ),
        migrations.RenameField(
            model_name='strategystate',
            old_name='maxCurrentRat',
            new_name='maxCurrentRate',
        ),
    ]
