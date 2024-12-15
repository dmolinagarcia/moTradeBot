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

    data = {
    "15m": [
        {"time": 1640995200, "open": 45000, "high": 45500, "low": 44500, "close": 45200},
        {"time": 1640996700, "open": 45200, "high": 45700, "low": 44800, "close": 45500},
        {"time": 1640998200, "open": 45500, "high": 46000, "low": 45300, "close": 45800},
        {"time": 1640999700, "open": 45800, "high": 46300, "low": 45500, "close": 46000},
        {"time": 1641001200, "open": 46000, "high": 46500, "low": 45700, "close": 46200},
        {"time": 1641002700, "open": 46200, "high": 46700, "low": 46000, "close": 46500},
        {"time": 1641004200, "open": 46500, "high": 47000, "low": 46200, "close": 46800},
        {"time": 1641005700, "open": 46800, "high": 47300, "low": 46500, "close": 47000},
        {"time": 1641007200, "open": 47000, "high": 47500, "low": 46800, "close": 47200},
        {"time": 1641008700, "open": 47200, "high": 47800, "low": 47000, "close": 47500},
        {"time": 1641010200, "open": 47500, "high": 48000, "low": 47200, "close": 47800},
        {"time": 1641011700, "open": 47800, "high": 48300, "low": 47500, "close": 48000},
        {"time": 1641013200, "open": 48000, "high": 48500, "low": 47800, "close": 48200},
        {"time": 1641014700, "open": 48200, "high": 48700, "low": 48000, "close": 48500},
        {"time": 1641016200, "open": 48500, "high": 49000, "low": 48300, "close": 48700},
        {"time": 1641017700, "open": 48700, "high": 49200, "low": 48500, "close": 49000},
        {"time": 1641019200, "open": 49000, "high": 49500, "low": 48700, "close": 49300},
        {"time": 1641020700, "open": 49300, "high": 49800, "low": 49000, "close": 49500},
        {"time": 1641022200, "open": 49500, "high": 50000, "low": 49300, "close": 49800},
        {"time": 1641023700, "open": 49800, "high": 50300, "low": 49500, "close": 50000},
        {"time": 1641025200, "open": 50000, "high": 50500, "low": 49800, "close": 50200},
        {"time": 1641026700, "open": 50200, "high": 50700, "low": 50000, "close": 50500},
        {"time": 1641028200, "open": 50500, "high": 51000, "low": 50200, "close": 50700},
        {"time": 1641029700, "open": 50700, "high": 51200, "low": 50500, "close": 51000},
        {"time": 1641031200, "open": 51000, "high": 51500, "low": 50700, "close": 51200}
    ],
    "4h": [
        {"time": 1640995200, "open": 45000, "high": 45500, "low": 44500, "close": 45200},
        {"time": 1641016800, "open": 45200, "high": 45700, "low": 44800, "close": 45500},
        {"time": 1641038400, "open": 45500, "high": 46000, "low": 45300, "close": 45800},
        {"time": 1641060000, "open": 45800, "high": 46300, "low": 45500, "close": 46000},
        {"time": 1641081600, "open": 46000, "high": 46500, "low": 45700, "close": 46200},
        {"time": 1641103200, "open": 46200, "high": 46700, "low": 46000, "close": 46500},
        {"time": 1641124800, "open": 46500, "high": 47000, "low": 46200, "close": 46800},
        {"time": 1641146400, "open": 46800, "high": 47300, "low": 46500, "close": 47000},
        {"time": 1641168000, "open": 47000, "high": 47500, "low": 46800, "close": 47200},
        {"time": 1641189600, "open": 47200, "high": 47800, "low": 47000, "close": 47500},
        {"time": 1641211200, "open": 47500, "high": 48000, "low": 47200, "close": 47800},
        {"time": 1641232800, "open": 47800, "high": 48300, "low": 47500, "close": 48000},
        {"time": 1641254400, "open": 48000, "high": 48500, "low": 47800, "close": 48200},
        {"time": 1641276000, "open": 48200, "high": 48700, "low": 48000, "close": 48500},
        {"time": 1641297600, "open": 48500, "high": 49000, "low": 48300, "close": 48700},
        {"time": 1641319200, "open": 48700, "high": 49200, "low": 48500, "close": 49000},
        {"time": 1641340800, "open": 49000, "high": 49500, "low": 48700, "close": 49300},
        {"time": 1641362400, "open": 49300, "high": 49800, "low": 49000, "close": 49500},
        {"time": 1641384000, "open": 49500, "high": 50000, "low": 49300, "close": 49800},
        {"time": 1641405600, "open": 49800, "high": 50300, "low": 49500, "close": 50000},
        {"time": 1641427200, "open": 50000, "high": 50500, "low": 49800, "close": 50200},
        {"time": 1641448800, "open": 50200, "high": 50700, "low": 50000, "close": 50500},
        {"time": 1641470400, "open": 50500, "high": 51000, "low": 50200, "close": 50700},
        {"time": 1641492000, "open": 50700, "high": 51200, "low": 50500, "close": 51000},
        {"time": 1641513600, "open": 51000, "high": 51500, "low": 50700, "close": 51200}
    ],
    "1d": [
        {"time": 1640995200, "open": 45000, "high": 45500, "low": 44500, "close": 45200},
        {"time": 1641081600, "open": 45200, "high": 45700, "low": 44800, "close": 45500},
        {"time": 1641168000, "open": 45500, "high": 46000, "low": 45300, "close": 45800},
        {"time": 1641254400, "open": 45800, "high": 46300, "low": 45500, "close": 46000},
        {"time": 1641340800, "open": 46000, "high": 46500, "low": 45700, "close": 46200},
        {"time": 1641427200, "open": 46200, "high": 46700, "low": 46000, "close": 46500},
        {"time": 1641513600, "open": 46500, "high": 47000, "low": 46200, "close": 46800},
        {"time": 1641600000, "open": 46800, "high": 47300, "low": 46500, "close": 47000},
        {"time": 1641686400, "open": 47000, "high": 47500, "low": 46800, "close": 47200},
        {"time": 1641772800, "open": 47200, "high": 47800, "low": 47000, "close": 47500},
        {"time": 1641859200, "open": 47500, "high": 48000, "low": 47200, "close": 47800},
        {"time": 1641945600, "open": 47800, "high": 48300, "low": 47500, "close": 48000},
        {"time": 1642032000, "open": 48000, "high": 48500, "low": 47800, "close": 48200},
        {"time": 1642118400, "open": 48200, "high": 48700, "low": 48000, "close": 48500},
        {"time": 1642204800, "open": 48500, "high": 49000, "low": 48300, "close": 48700},
        {"time": 1642291200, "open": 48700, "high": 49200, "low": 48500, "close": 49000},
        {"time": 1642377600, "open": 49000, "high": 49500, "low": 48700, "close": 49300},
        {"time": 1642464000, "open": 49300, "high": 49800, "low": 49000, "close": 49500},
        {"time": 1642550400, "open": 49500, "high": 50000, "low": 49300, "close": 49800},
        {"time": 1642636800, "open": 49800, "high": 50300, "low": 49500, "close": 50000},
        {"time": 1642723200, "open": 50000, "high": 50500, "low": 49800, "close": 50200},
        {"time": 1642809600, "open": 50200, "high": 50700, "low": 50000, "close": 50500},
        {"time": 1642896000, "open": 50500, "high": 51000, "low": 50200, "close": 50700},
        {"time": 1642982400, "open": 50700, "high": 51200, "low": 50500, "close": 51000},
        {"time": 1643068800, "open": 51000, "high": 51500, "low": 50700, "close": 51200}
    ],
    "1w": [
        {"time": 1640995200, "open": 45000, "high": 45500, "low": 44500, "close": 45200},
        {"time": 1641600000, "open": 45200, "high": 45700, "low": 44800, "close": 45500},
        {"time": 1642204800, "open": 45500, "high": 46000, "low": 45300, "close": 45800},
        {"time": 1642809600, "open": 45800, "high": 46300, "low": 45500, "close": 46000},
        {"time": 1643414400, "open": 46000, "high": 46500, "low": 45700, "close": 46200},
        {"time": 1644019200, "open": 46200, "high": 46700, "low": 46000, "close": 46500},
        {"time": 1644624000, "open": 46500, "high": 47000, "low": 46200, "close": 46800},
        {"time": 1645228800, "open": 46800, "high": 47300, "low": 46500, "close": 47000},
        {"time": 1645833600, "open": 47000, "high": 47500, "low": 46800, "close": 47200},
        {"time": 1646438400, "open": 47200, "high": 47800, "low": 47000, "close": 47500},
        {"time": 1647043200, "open": 47500, "high": 48000, "low": 47200, "close": 47800},
        {"time": 1647648000, "open": 47800, "high": 48300, "low": 47500, "close": 48000},
        {"time": 1648252800, "open": 48000, "high": 48500, "low": 47800, "close": 48200},
        {"time": 1648857600, "open": 48200, "high": 48700, "low": 48000, "close": 48500},
        {"time": 1649462400, "open": 48500, "high": 49000, "low": 48300, "close": 48700},
        {"time": 1650067200, "open": 48700, "high": 49200, "low": 48500, "close": 49000},
        {"time": 1650672000, "open": 49000, "high": 49500, "low": 48700, "close": 49300},
        {"time": 1651276800, "open": 49300, "high": 49800, "low": 49000, "close": 49500},
        {"time": 1651881600, "open": 49500, "high": 50000, "low": 49300, "close": 49800},
        {"time": 1652486400, "open": 49800, "high": 50300, "low": 49500, "close": 50000}
      ]
    }

    return JsonResponse(data['4h'], safe=False)


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

