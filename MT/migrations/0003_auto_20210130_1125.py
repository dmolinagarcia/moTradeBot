# Generated by Django 3.1.5 on 2021-01-30 10:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MT', '0002_strategy_isrunning'),
    ]

    operations = [
        migrations.AddField(
            model_name='strategy',
            name='accion',
            field=models.CharField(max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='adx',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='amount',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='beneficioTotal',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='cryptoTimeframeADX',
            field=models.CharField(max_length=4, null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='cryptoTimeframeDI',
            field=models.CharField(max_length=4, null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='currentRate',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='diffDI',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='estado',
            field=models.IntegerField(choices=[(0, 'Hold'), (1, 'Preoper'), (2, 'Oper'), (3, 'Precierre')], null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='limitBuy',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='limitClose',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='limitOpen',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='limitSell',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='maxCurrentRat',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='minusDI',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='operID',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='plusDI',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='rateSymbol',
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='sleep',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='stopLoss',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='strategy',
            name='tickSymbol',
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AlterField(
            model_name='strategy',
            name='isRunning',
            field=models.BooleanField(null=True),
        ),
        migrations.AlterField(
            model_name='strategy',
            name='operSymbol',
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.AlterField(
            model_name='strategy',
            name='utility',
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.CreateModel(
            name='StrategyState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('operID', models.IntegerField(null=True)),
                ('accion', models.CharField(max_length=10, null=True)),
                ('estado', models.IntegerField(choices=[(0, 'Hold'), (1, 'Preoper'), (2, 'Oper'), (3, 'Precierre')], null=True)),
                ('adx', models.FloatField(null=True)),
                ('plusDI', models.FloatField(null=True)),
                ('minusDI', models.FloatField(null=True)),
                ('diffDI', models.FloatField(null=True)),
                ('currentRate', models.FloatField(null=True)),
                ('maxCurrentRat', models.FloatField(null=True)),
                ('stopLoss', models.FloatField(null=True)),
                ('sleep', models.IntegerField(null=True)),
                ('amount', models.IntegerField(null=True)),
                ('beneficioTotal', models.FloatField(null=True)),
                ('limitOpen', models.IntegerField(null=True)),
                ('limitClose', models.IntegerField(null=True)),
                ('limitBuy', models.IntegerField(null=True)),
                ('limitSell', models.IntegerField(null=True)),
                ('cryptoTimeframeADX', models.CharField(max_length=4, null=True)),
                ('cryptoTimeframeDI', models.CharField(max_length=4, null=True)),
                ('strategy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='MT.strategy')),
            ],
        ),
    ]