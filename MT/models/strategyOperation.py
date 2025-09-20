# -*- coding: utf-8 -*-
from django.db import models
from django.db.models import Max, Min

# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY OPERATION 
# ──────────────────────────────────────────────────────────────────────────────
class StrategyOperation(models.Model):
    strategy = models.ForeignKey("Strategy", on_delete=models.CASCADE)
    operID = models.IntegerField()
    type = models.CharField(max_length=4)
    timestampOpen = models.DateTimeField(auto_now=False, auto_now_add=True)
    timestampClose = models.DateTimeField(auto_now=False, auto_now_add=False, null=True, blank=True)
    beneficio = models.FloatField(null=True, blank=True)
    buyAmount = models.FloatField(null=True)
    sellAmount = models.FloatField(null=True, blank=True)
    reasonClose = models.CharField(max_length=128, null=True, blank=True)
    operIDClose = models.IntegerField(null=True)
    profit = models.FloatField(null=True, blank=True)

    def __str__(self):
        return str(self.strategy.utility + ":" + str(self.operID))

    def close(self, beneficio, buyAmount, sellAmount, reasonClose, operIDClose, profit):
        self.timestampClose = timezone.now()
        self.beneficio = beneficio
        self.buyAmount = buyAmount
        self.sellAmount = sellAmount
        self.reasonClose = reasonClose
        self.operIDClose = operIDClose
        self.profit = profit
        self.save()

    def getHistory(self):
        history = self.strategy.getHistory()
        startTS = self.strategy.getHistory().exclude(timestamp__gt=self.timestampOpen).order_by('-timestamp')[:20].aggregate(Min('timestamp'))['timestamp__min']

        if startTS:
            history = history.filter(timestamp__gt=startTS)

        if self.timestampClose:
            endTS = self.strategy.getHistory().filter(timestamp__gte=self.timestampClose).order_by('timestamp')[:20].aggregate(Max('timestamp'))['timestamp__max']
            history = history.exclude(timestamp__gt=endTS)

        return history

    def getStrategy(self):
        return self.strategy

    def deleteOperation(self):
        # Clear History
        history = self.strategy.getHistory()
        history = history.filter(timestamp__gte=self.timestampOpen)
        if self.timestampClose:
            history = history.exclude(timestamp__gt=self.timestampClose)

        for entry in history:
            entry.accion = "WAIT"
            entry.currentProfit = 0
            entry.save()

        if self.beneficio:
            self.strategy.beneficioTotal = (self.strategy.beneficioTotal or 0) - self.beneficio
            self.strategy.save()