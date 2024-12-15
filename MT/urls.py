from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path ('', views.indexView, name='indexView'),

    path ('strategyOperations/', views.strategyLastOperationView, name='strategyLastOperationsView'),
    path ('strategyOpen/', views.strategyOpenOperationView, name='strategyOpenOperationView'),

    path ('strategy/list/', views.strategyListView, name='strategyListView'),
    path ('strategy/<int:strategy_id>/<int:operation_id>/', views.strategyView, name='strategyView'),
    path ('strategy/graph/<int:strategy_id>/', views.strategyGraphView, name='strategyGraphView'),
    path ('strategy/operations/<int:strategy_id>/', views.strategyOperationView, name='strategyOperationView'),
    path ('strategy/comments/<int:strategy_id>/', views.strategyCommentsView, name='strategyCommentsView'),
    path ('strategy/clear/<int:strategy_id>/', views.strategyClearView, name='strategyClearView'),

    path ('operation/graph/<int:operation_id>/', views.operationGraphView, name='operationGraphView'),
    path ('operation/detail/<int:operation_id>/', views.operationDetailView, name='operationDetailView'),
    path ('operation/clear/<int:operation_id>/', views.operationClearView, name='operationClearView'),
    path ('getHistory/<int:strategy_id>/<int:operation_id>/<str:interval>', views.getHistoryView, name='getHistoryView'),
    path ('toggle/<int:strategy_id>/', views.toggleView, name='toggleView'),
    path ('unlock/<int:strategy_id>/', views.unlockView, name='unlockView'),
    path ('manualClose/<int:strategy_id>/', views.manualCloseView, name='manualCloseView'),
    
    path ('registration/timezone/', views.userTimezoneFormView, name='timezoneFormView'),
    path ('user/config/', views.configFormView, name='configFormView'),
    path ('account/', views.userAccountView, name='userAccountView'),

    path ('clear/', views.clearView, name='clearView'),
    path ('start/', views.startView, name='startView'),
    path ('process/', views.processView, name='processView'),
    path ('balance/', views.balanceView, name='balanceView'),
    path ('status/', views.statusView, name='statusView'),
    
    ## NOTIFICACIONES
    ## DISABLED!
    ## path('webpush/', include('webpush.urls')),
    ## path('send_push/', views.send_push),
    ## path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/x-javascript'))
    ##


]


