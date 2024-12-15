from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.template import loader
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

import math
import logging
import datetime
import pytz

from .models import *
from .forms import *

## Para las notificaciones con django-push
from django.http.response import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
## DISABLE NOTIF from webpush import send_user_notification, send_group_notification
import json
from django.conf import settings

## Notificaciones Telegram
## DISABLE TELEGRAM import telegram

logger = logging.getLogger(__name__)

#@require_POST
@csrf_exempt
def send_push(request):
    try:
        # body = request.body
        # data = json.loads(body)

        #if 'head' not in data or 'body' not in data or 'id' not in data:
        #    return JsonResponse(status=400, data={"message": "Invalid data format"})

        # user_id = data['id']
        #user = get_object_or_404(User, pk=user_id)
        #payload = {'head': data['head'], 'body': data['body']}
        #send_user_notification(user=user, payload=payload, ttl=1000)
        
        #payload = {"head": "Welcome!", "body": "Esto es un test"}
        #send_group_notification(group_name="notificame", payload=payload, ttl=100000)
        
        telegram_settings = settings.TELEGRAM
        bot = telegram.Bot(token=telegram_settings['bot_token'])
        bot.send_message(chat_id="@%s" % telegram_settings['channel_name'],
                     text='Hola', parse_mode=telegram.ParseMode.HTML)
                     
        return JsonResponse(status=200, data={"message": "Web push successful"})
    except TypeError:
        return JsonResponse(status=500, data={"message": "An error occurred"})
        

##############


# Index page
@login_required
def indexView(request):
    ## Notificaciones
    ## DISABLE webpush_settings = getattr(settings, 'WEBPUSH_SETTINGS', {})
    ## DISABLE vapid_key = webpush_settings.get('VAPID_PUBLIC_KEY')
    user = request.user
    #############################
    
    ## DISABLE webpush = {"group": "notificame" } # The group_name should be the name you would define.
    
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    template = loader.get_template('index.html')
    context = {
        'title': 'moTrade Dashboard', 
        user: user, 
        ## DISABLE notificaciones 'vapid_key': vapid_key, 
        ## DISABLE notificaciones "webpush":webpush,
        }
    return HttpResponse(template.render(context, request))
    
# Strategy List Views
@login_required
def strategyListView(request):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    beneficio=0
    strategy_list = Strategy.objects.filter(isRunning=True).order_by('-currentProfit')
    #  = Strategy.objects.order_by('-beneficioTotal')
    template = loader.get_template('strategy/list.html')
    for strategy in strategy_list :
        if strategy.isRunning :
            beneficio=beneficio+(strategy.beneficioTotal if strategy.beneficioTotal is not None else 0)
    context = {
        'strategy_list': strategy_list,
        'beneficio': beneficio,
    }
    return HttpResponse(template.render(context, request))

@login_required
def strategyLastOperationView (request) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    operations=StrategyOperation.objects.filter(timestampClose__isnull=False).order_by('-timestampClose')[:10000]
    context = {
        'operations': operations,
    }
    template = loader.get_template('strategy/operations.html')
    return HttpResponse(template.render(context, request))

@login_required
def strategyOpenOperationView (request) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    operations=StrategyOperation.objects.filter(timestampClose__isnull=True).order_by('-timestampOpen')
    context = {
        'operations': operations,
    }
    template = loader.get_template('strategy/operations.html')
    return HttpResponse(template.render(context, request))

# get History (JSON VIEWS)
@login_required
def getHistoryView(request, strategy_id, operation_id, interval) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))

    data = {[
        {"time": "2024-12-01T00:00:00", "open": 32000, "high": 32300, "low": 31800, "close": 32150},
        {"time": "2024-12-01T04:00:00", "open": 32150, "high": 32400, "low": 31950, "close": 32250},
        {"time": "2024-12-01T08:00:00", "open": 32250, "high": 32500, "low": 32050, "close": 32300},
        {"time": "2024-12-01T12:00:00", "open": 32300, "high": 32700, "low": 32150, "close": 32450},
        {"time": "2024-12-01T16:00:00", "open": 32450, "high": 32800, "low": 32250, "close": 32600},
        {"time": "2024-12-01T20:00:00", "open": 32600, "high": 33000, "low": 32400, "close": 32850},
        {"time": "2024-12-02T00:00:00", "open": 32850, "high": 33200, "low": 32650, "close": 32950},
        {"time": "2024-12-02T04:00:00", "open": 32950, "high": 33400, "low": 32700, "close": 33100},
        {"time": "2024-12-02T08:00:00", "open": 33100, "high": 33500, "low": 32900, "close": 33250},
        {"time": "2024-12-02T12:00:00", "open": 33250, "high": 33650, "low": 33050, "close": 33400},
        {"time": "2024-12-02T16:00:00", "open": 33400, "high": 33800, "low": 33200, "close": 33650},
        {"time": "2024-12-02T20:00:00", "open": 33650, "high": 34000, "low": 33450, "close": 33800},
        {"time": "2024-12-03T00:00:00", "open": 33800, "high": 34200, "low": 33650, "close": 34050},
        {"time": "2024-12-03T04:00:00", "open": 34050, "high": 34400, "low": 33850, "close": 34200},
        {"time": "2024-12-03T08:00:00", "open": 34200, "high": 34600, "low": 34000, "close": 34350},
        {"time": "2024-12-03T12:00:00", "open": 34350, "high": 34750, "low": 34150, "close": 34500},
        {"time": "2024-12-03T16:00:00", "open": 34500, "high": 34900, "low": 34300, "close": 34750},
        {"time": "2024-12-03T20:00:00", "open": 34750, "high": 35100, "low": 34550, "close": 34900},
        {"time": "2024-12-04T00:00:00", "open": 34900, "high": 35300, "low": 34700, "close": 35050},
        {"time": "2024-12-04T04:00:00", "open": 35050, "high": 35400, "low": 34850, "close": 35200},
        {"time": "2024-12-04T08:00:00", "open": 35200, "high": 35600, "low": 35000, "close": 35350},
        {"time": "2024-12-04T12:00:00", "open": 35350, "high": 35750, "low": 35150, "close": 35500},
        {"time": "2024-12-04T16:00:00", "open": 35500, "high": 35900, "low": 35300, "close": 35750},
        {"time": "2024-12-04T20:00:00", "open": 35750, "high": 36100, "low": 35550, "close": 35900},
        {"time": "2024-12-05T00:00:00", "open": 35900, "high": 36300, "low": 35700, "close": 36150},
        {"time": "2024-12-05T04:00:00", "open": 36150, "high": 36500, "low": 35900, "close": 36250},
        {"time": "2024-12-05T08:00:00", "open": 36250, "high": 36600, "low": 36000, "close": 36400},
        {"time": "2024-12-05T12:00:00", "open": 36400, "high": 36800, "low": 36200, "close": 36650},
        {"time": "2024-12-05T16:00:00", "open": 36650, "high": 37000, "low": 36450, "close": 36900},
        {"time": "2024-12-05T20:00:00", "open": 36900, "high": 37300, "low": 36700, "close": 37150},
        {"time": "2024-12-06T00:00:00", "open": 37150, "high": 37500, "low": 36950, "close": 37350},
        {"time": "2024-12-06T04:00:00", "open": 37350, "high": 37700, "low": 37150, "close": 37500},
        {"time": "2024-12-06T08:00:00", "open": 37500, "high": 37900, "low": 37300, "close": 37750},
        {"time": "2024-12-06T12:00:00", "open": 37750, "high": 38100, "low": 37550, "close": 37900},
        {"time": "2024-12-06T16:00:00", "open": 37900, "high": 38300, "low": 37700, "close": 38150},
        {"time": "2024-12-06T20:00:00", "open": 38150, "high": 38500, "low": 37950, "close": 38300},
        {"time": "2024-12-07T00:00:00", "open": 38300, "high": 38700, "low": 38100, "close": 38550},
        {"time": "2024-12-07T04:00:00", "open": 38550, "high": 38900, "low": 38350, "close": 38800},
        {"time": "2024-12-07T08:00:00", "open": 38800, "high": 39200, "low": 38600, "close": 39000},
        {"time": "2024-12-07T12:00:00", "open": 39000, "high": 39400, "low": 38800, "close": 39150},
        {"time": "2024-12-07T16:00:00", "open": 39150, "high": 39500, "low": 38950, "close": 39300},
        {"time": "2024-12-07T20:00:00", "open": 39300, "high": 39700, "low": 39100, "close": 39450},
        {"time": "2024-12-08T00:00:00", "open": 39450, "high": 39800, "low": 39250, "close": 39650},
        {"time": "2024-12-08T04:00:00", "open": 39650, "high": 40000, "low": 39450, "close": 39800},
        {"time": "2024-12-08T08:00:00", "open": 39800, "high": 40200, "low": 39600, "close": 39950},
        {"time": "2024-12-08T12:00:00", "open": 39950, "high": 40300, "low": 39750, "close": 40100},
        {"time": "2024-12-08T16:00:00", "open": 40100, "high": 40500, "low": 39900, "close": 40350},
        {"time": "2024-12-08T20:00:00", "open": 40350, "high": 40700, "low": 40150, "close": 40550}
    ]}


    return JsonResponse(data)


# Strategy Views
@login_required
def strategyView(request, strategy_id, operation_id) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)

    if (operation_id == 0) :
        title='Strategy ' + str(strategy)
        template = loader.get_template('strategy/strategy.html')
    else :
        template = loader.get_template('operation/operation.html')
        title='Operation ' + str(operation_id)

    context = {
        'strategy_id': strategy_id,
        'operation_id': operation_id,
        'title': title, 
    }
    return HttpResponse(template.render(context, request))

@login_required
def strategyClearView(request, strategy_id) :
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    strategy.clear()
    if request.META.get('HTTP_REFERER') :
        return redirect(request.META.get('HTTP_REFERER'))
    else :
        template = loader.get_template('blank.html')
        context = {}
        return HttpResponse(template.render(context, request))
    
@login_required    
def strategyCommentsView(request, strategy_id) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    comments = strategy.getComments()
    
    ## SI se ha posteado el formulario
    if request.method == 'POST' :
        form = strategyCommentsForm(request.POST)
        if form.is_valid() :
            strategy.comments = form.cleaned_data['comments']
            strategy.save()
                
    ## No se ha posteado
    else :
        form = strategyCommentsForm(initial={'comments': comments})
    
    template = loader.get_template('strategy/comments.html')
    context = {
        'form' : form,
        'comments': comments,
        'strategy_id': strategy_id,
    }
    return HttpResponse(template.render(context, request))    

@login_required    
def strategyOperationView (request, strategy_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    operations = strategy.getOperations()
    context = {
        'operations': operations,
    }
    template = loader.get_template('strategy/operations.html')
    return HttpResponse(template.render(context, request))

def getGraphData (strategy, history) :
    data = []
    data1 = []
    data2 = []
    data3 = []
  
    data.append(["Time", "Rate","COMPRAR","VENDER","EMA","EMA20","EMA100"])
    data1.append(["Time", "ADX","+DI","-DI","DIFF","COMPRAR","VENDER"])
    data2.append(["Time", "PROFIT", "STOPLOSS", "COMPRAR", "VENDER"])
    data3.append(["Time", "RECOMMEND", "RECOMMEND240", "COMPRAR", "VENDER"])
 
    estado=0
    estadoNext=0
    avg240=0

    for entry in history:
        
        if entry.accion=="COMPRAR" :
            comprar=500000
            vender=0
        elif entry.accion=="VENDER" :
            comprar=0
            vender=500000
        else:
            comprar=0
            vender=0

        currentProfit=0
        if entry.currentProfit is None :
            currentProfit=0
        else :
            currentProfit=entry.currentProfit

        stopLossCurrent=0
        if entry.stopLossCurrent is None :
            stopLossCurrent=0
        else :
            stopLossCurrent=entry.stopLossCurrent

        ema100=entry.currentRate
        if entry.ema100 is None :
            ema100=entry.currentRate
        else :
            ema100=entry.ema100

        data.append([(entry.timestamp).strftime('%m.%d.%y %H:%M'),
            entry.currentRate,
            comprar,
            vender,
            entry.ema,
            entry.ema20,
            ema100])

        data1.append([(entry.timestamp).strftime('%m.%d.%y %H:%M'),
            entry.adx,
            entry.plusDI,
            entry.minusDI,
            abs(entry.plusDI-entry.minusDI),
            comprar,
            vender,
            ])

        data2.append([(entry.timestamp).strftime('%m.%d.%y %H:%M'),
            currentProfit,
            stopLossCurrent,
            comprar,
            vender,
            ])

        data3.append([(entry.timestamp).strftime('%m.%d.%y %H:%M'),
            entry.recommendMA,
            #(entry.recommendMA240+avg240)/2,
            entry.recommendMA240,
            comprar,
            vender,
            ])

        avg240=(entry.recommendMA240+avg240)/2

    context = {
        'data': data,
        'data1': data1,
        'data2': data2,
        'data3': data3,
        'title': str(strategy),
    }

    return context

@login_required
def strategyGraphView(request, strategy_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    history = strategy.getHistory()

    context = getGraphData ( strategy, history )

    if ( request.user.profile.configLegacyGraph):
        template = loader.get_template('strategy/graph.html')
    else :
        template = loader.get_template('strategy/graphTV.html')
        
    return HttpResponse(template.render(context, request))
    
# Operation Views
@login_required    
def operationDetailView(request, operation_id) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    template = loader.get_template('operation/detail.html')
    context = {
        'operation_id': operation_id,
    }
    return HttpResponse(template.render(context, request))      
    
@login_required
def operationGraphView(request, operation_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    operation = get_object_or_404(StrategyOperation, operID=operation_id)
    
    ## Hay que pillar el strategy_id, las fechas, y sacas los datos apra ellas
    ## Implementamos un operation.getHistory()????
    history = operation.getHistory()
    strategy = operation.getStrategy()

    context = getGraphData ( strategy, history )

    if ( request.user.profile.configLegacyGraph):
        template = loader.get_template('strategy/graph.html')
    else :
        template = loader.get_template('strategy/graphTV.html')
    
    return HttpResponse(template.render(context, request))

@login_required
def operationClearView(request, operation_id):
    operation = get_object_or_404(StrategyOperation, operID=operation_id)
    operation.deleteOperation()
    operation.delete()    
    template = loader.get_template('blank.html')
    context = {
        }
    return redirect(request.META.get('HTTP_REFERER'))
    
# User views

# account data view
@login_required
#eliminaremos esto cuando este ok
def userAccountView(request) :
    headers = {'Content-Type': 'application/json',} 
    data = {}
    response = requests.get(
        'http://127.0.0.1:5000/get_account',
        headers=headers,
        data=json.dumps(data))
    template = loader.get_template('user/account.html')

    # Obtener informacion de las operaciones
    operations = StrategyOperation.objects.filter(operIDClose__isnull=False)
    totalWins=0
    totalLoss=0
    averageWins=0
    averageLoss=0

    for operation in operations :
        if operation.profit is not None :
            if operation.profit < 0 :
                totalLoss=totalLoss+1
                averageLoss=averageLoss+operation.profit
            else :
                totalWins=totalWins+1
                averageWins=averageWins+operation.profit
    
    try :
        averageProfit=(averageLoss+averageWins)/(totalLoss+totalWins)
    except :
        averageProfit = 0

    try :
        averageWins=averageWins/totalWins
    except :
        averageWins = 0

    try :
        averageLoss=averageLoss/totalLoss
    except :
        averageLoss = 0

    try :
        winsLossRatio=totalWins*100/(totalLoss+totalWins)
    except : 
        winsLossRatio = 0
    
    try :
        context = {
            'account'    : response.json(),
            'operations' : {
                'totalOperations' : operations.count(),
                'winsLossRatio'   : winsLossRatio,
                'totalWins'       : totalWins,
                'totalLoss'       : totalLoss,
                'averageWinsPct'  : averageWins,
                'averageLossPct'  : averageLoss, 
                'averageProfit'   : averageProfit,
             }
        }
    except :
        logger.error('Error procesando data de account')
        context = {}

    return HttpResponse(template.render(context, request))

@login_required    
def userTimezoneFormView(request) :
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    TZ=request.user.profile.timezone
    
    ## SI se ha posteado el formulario
    if request.method == 'POST' :
        form = userTimezoneForm(request.POST)
        if form.is_valid() :
            request.user.profile.timezone = form.cleaned_data['timezone']
            request.user.save()
                            
    ## No se ha posteado
    else :
        form = userTimezoneForm(initial={'timezone': TZ})
    
    template = loader.get_template('registration/timezone.html')
    context = {
        'form' : form,
        'timezone': TZ,
    }
    return HttpResponse(template.render(context, request))      


@login_required
def configFormView(request) :
    configMaxBet=request.user.profile.configMaxBet
    configProcessEnabled=request.user.profile.configProcessEnabled
    configGlobalTPEnabled=request.user.profile.configGlobalTPEnabled
    configGlobalTPThreshold=request.user.profile.configGlobalTPThreshold
    configGlobalTPSleepdown=request.user.profile.configGlobalTPSleepdown
    configGlobalTPWakeUp=request.user.profile.configGlobalTPWakeUp

    ## SI se ha posteado el formulario
    if request.method == 'POST' :
        form = configForm(request.POST)
        if form.is_valid() :
            request.user.profile.configMaxBet=form.cleaned_data['configMaxBet']
            request.user.profile.configProcessEnabled=form.cleaned_data['configProcessEnabled']
            request.user.profile.configGlobalTPEnabled=form.cleaned_data['configGlobalTPEnabled']
            request.user.profile.configGlobalTPThreshold=form.cleaned_data['configGlobalTPThreshold']
            request.user.profile.configGlobalTPSleepdown=form.cleaned_data['configGlobalTPSleepdown']
            request.user.profile.configGlobalTPWakeUp=form.cleaned_data['configGlobalTPWakeUp']
            request.user.save()
            updateBetAmount ()

    ## No se ha posteado
    else :
        form = configForm(initial={
            'configMaxBet': configMaxBet, 
            'configProcessEnabled': configProcessEnabled,
            'configGlobalTPEnabled': configGlobalTPEnabled,
            'configGlobalTPThreshold': configGlobalTPThreshold,
            'configGlobalTPSleepdown': configGlobalTPSleepdown,
            'configGlobalTPWakeUp': configGlobalTPWakeUp
        })

    template = loader.get_template('user/config.html')
    context = {
        'form' : form,
        'configMaxBet': configMaxBet,
        'configProcessEnabled': configProcessEnabled,
        'configGlobalTPEnabled': configGlobalTPEnabled,
        'configGlobalTPThreshold': configGlobalTPThreshold,
        'configGlobalTPSleepdown': configGlobalTPSleepdown,
        'configGlobalTPWakeUp': configGlobalTPWakeUp
    }
    return HttpResponse(template.render(context, request))

    
# Global Commands
@login_required
def clearView(request):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy_list = Strategy.objects.all()
    for strategy in strategy_list :
        strategy.clear()
    if request.META.get('HTTP_REFERER') :
        return redirect(request.META.get('HTTP_REFERER'))
    else :
        template = loader.get_template('blank.html')
        context = {}
        return HttpResponse(template.render(context, request))


@login_required
def startView(request):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy_list = Strategy.objects.all()
    for strategy in strategy_list :
        strategy.isRunning=True
        strategy.save()

    return redirect(request.META.get('HTTP_REFERER'))


def processView(request):
    strategyList=Strategy.objects.filter(nextUpdate__lte=timezone.now())
    adminUser=User.objects.filter(username='admin')
    for user in adminUser :
        adminId=user.id
        adminProfile=Profile.objects.filter(user=adminId)
        for profile in adminProfile :
            isProcessEnabled = profile.configProcessEnabled

    if isProcessEnabled :       
        logger.info("Starting Process of " + (str)(strategyList.count()) + " strategies")
        start = time.time()
        visMarketOpen = isMarketOpen()
        # Check if market is open, pass as parameter to operation
        for strategy in strategyList :
            strategy.operation(visMarketOpen)
        end = time.time()
        logger.info("Ending Process in "+(str)(end-start)+" secs.")
    else :
        logger.info("Skipping Process due to configProcessEnabled setting to false")

    if request.META.get('HTTP_REFERER') :
        return redirect(request.META.get('HTTP_REFERER'))
    else :
        template = loader.get_template('blank.html')
        context = {}
        return HttpResponse(template.render(context, request))

def statusView(request):
# Will send a operations summary via telegram to suscriptors

    strategyList=Strategy.objects.filter(isRunning=True)
    
    output = ""
    
    for strategy in strategyList :
        output = output + (strategy.status())

    telegram_settings = settings.TELEGRAM
    bot = telegram.Bot(token=telegram_settings['bot_token'])
    bot.send_message(chat_id="@%s" % telegram_settings['channel_name'],        text=output, parse_mode=telegram.ParseMode.HTML)
    
    if request.META.get('HTTP_REFERER') :
        return redirect(request.META.get('HTTP_REFERER'))
    else :
        template = loader.get_template('blank.html')
        context = {}
        return HttpResponse(template.render(context, request))    

def updateBetAmount():
    strategyList=Strategy.objects.filter(isRunning=True)
    totalBet=0
    for strategy in strategyList :
        totalBet=totalBet+strategy.bet
    headers = {'Content-Type': 'application/json',}
    balance = requests.get('http://127.0.0.1:5000/get_balance', headers=headers).json()
    # Balance is set by user in settings
    adminUser=User.objects.filter(username='admin')
    for user in adminUser :
        adminId=user.id
        adminProfile=Profile.objects.filter(user=adminId)
        for profile in adminProfile :
            maxBalance = profile.configMaxBet

    if maxBalance > balance :
        maxBalance=balance+totalBet
        profile.configMaxBet=balance+totalBet
        profile.save()

    strategyCount=strategyList.count()
    nextAmount=math.floor(maxBalance/strategyCount)
    if nextAmount == 0:
        nextAmount=1

    for strategy in strategyList :
        strategy.setAmount(nextAmount)


def balanceView(request):
    updateBetAmount()
    if request.META.get('HTTP_REFERER') :
        return redirect(request.META.get('HTTP_REFERER'))
    else :
        template = loader.get_template('blank.html')
        context = {}
        return HttpResponse(template.render(context, request))
    
# Strategy Commands
@login_required
def toggleView(request, strategy_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    strategy.toggleIsRunning()
    return redirect(request.META.get('HTTP_REFERER'))

@login_required
def unlockView(request, strategy_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    strategy.unlock()
    return redirect(request.META.get('HTTP_REFERER'))

@login_required
def manualCloseView(request, strategy_id):
    timezone.activate(pytz.timezone(request.user.profile.timezone))
    strategy = get_object_or_404(Strategy, pk=strategy_id)
    strategy.manualClose("Manual ")
    return redirect(request.META.get('HTTP_REFERER'))


# general queries
def isMarketOpen() :

    headers = {
        'authority': 'api.nasdaq.com' ,
        'accept': 'application/json, text/plain, */*' ,
        'accept-language': 'en,es;q=0.9,fr;q=0.8' ,
        'origin': 'https://www.nasdaq.com' ,
        'referer': 'https://www.nasdaq.com/' ,
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"' ,
        'sec-ch-ua-mobile': '?0' ,
        'sec-ch-ua-platform': '"Windows"' ,
        'sec-fetch-dest': 'empty' ,
        'sec-fetch-mode': 'cors' ,
        'sec-fetch-site': 'same-site' ,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(
        'https://api.nasdaq.com/api/quote/AMD/info?assetclass=stocks',
        headers=headers)

    try :
        marketStatus=response.json()['data']['marketStatus']
        if marketStatus == 'Open' :
            isMarketOpen = True
        if marketStatus == 'After-Hours' :
            isMarketOpen = True
        if marketStatus == 'Closed' :
            isMarketOpen = True
        if marketStatus == 'Pre-Market' :
            isMarketOpen = True 
    except :
        logger.info ("Error al pintar isMarketOpen")
        isMarketOpen = True
        # Por defecto devolvemos True

    return isMarketOpen

