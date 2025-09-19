# -*- coding: utf-8 -*-
from django.db import models

# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY STATE 
# ──────────────────────────────────────────────────────────────────────────────
class StrategyState(models.Model):
    strategy = models.ForeignKey("Strategy", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    operID = models.IntegerField(null=True)
    accion = models.CharField(max_length=10, null=True)

    class StrategyStateStates(models.IntegerChoices):
        HOLD = 0
        PREOPER = 1
        OPER = 2
        PRECIERRE = 3

    estado = models.IntegerField(choices=StrategyStateStates.choices, null=True)
    ema = models.FloatField(null=True)
    ema20 = models.FloatField(null=True)
    ema100 = models.FloatField(null=True)
    adx = models.FloatField(null=True)
    plusDI = models.FloatField(null=True)
    minusDI = models.FloatField(null=True)
    diffDI = models.FloatField(null=True)
    currentRate = models.FloatField(null=True)
    currentProfit = models.FloatField(null=True)
    maxCurrentRate = models.FloatField(null=True)
    stopLoss = models.FloatField(null=True)
    sleep = models.IntegerField(null=True)
    amount = models.IntegerField(null=True)
    beneficioTotal = models.FloatField(null=True)
    limitOpen = models.IntegerField(null=True)
    limitClose = models.IntegerField(null=True)
    limitBuy = models.IntegerField(null=True)
    limitSell = models.IntegerField(null=True)
    cryptoTimeframeADX = models.CharField(max_length=4, null=True)
    cryptoTimeframeDI = models.CharField(max_length=4, null=True)
    isRunning = models.BooleanField(null=True)
    recommendMA = models.FloatField(default=0, null=True, blank=True)
    recommendMA240 = models.FloatField(default=0, null=True, blank=True)
    stopLossCurrent = models.FloatField(null=True, blank=True)
    takeProfitCurrent = models.FloatField(null=True, blank=True)
    atr = models.FloatField(null=True, blank=True) # ATR actual
    
    def __str__(self):
        return str(self.strategy.utility + ":" + str(self.timestamp))
    
    def clear(self):
        self.stopLossCurrent = None
        self.takeProfitCurrent = None
        self.currentProfit = None
        self.estado = 0
        self.accion = "WAIT"
        self.save()
