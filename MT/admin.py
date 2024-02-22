from django.contrib import admin

from .models import Strategy, StrategyState, StrategyOperation, Profile

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("utility", "cryptoTimeframeADX", "cryptoTimeframeDI", "limitOpen", "limitClose", "limitBuy", "limitSell", "stopLoss", "isRunning")


admin.site.register(StrategyState)
admin.site.register(StrategyOperation)
admin.site.register(Profile)

admin.site.site_header = 'MoTrade Administration'
