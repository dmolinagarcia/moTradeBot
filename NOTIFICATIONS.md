# NOTIFICACIONES DJANGO WEBPUSH

Notes to add mobile notification support in moTrade. Limited success so far, but everything is disabled in the code. Just testing.

Seguimos esto para suscribir!!

Experimental. Not working. Not enabled.

https://codelabs.developers.google.com/codelabs/push-notifications#2

Public Key

-- Removed Public Key from repo!

Private Key

-- Removed private key from repo!



https://github.com/safwanrahman/django-webpush >> instalación modulo y uso
https://www.digitalocean.com/community/tutorials/how-to-send-web-push-notifications-from-django-applications-es >> lo mismo pero mejor ??
-----------------------------------------------------


sudo pip install django-webpush

Añadir al installed_apps (settings.py)

INSTALLED_APPS = (
    ...
    'webpush',
)

Y los VAPID a settings.py

WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": "Vapid Public Key",
    "VAPID_PRIVATE_KEY":"Vapid Private Key",
    "VAPID_ADMIN_EMAIL": "admin@example.com"
}

python manage.py migrate

urls.py ---- esto todavia no lo he conseguido

urlpatterns =  [
    url(r'^webpush/', include('webpush.urls'))
]

# NOTIFICACIONES TELEGRAM

https://www.guguweb.com/2019/12/09/automate-your-telegram-channel-with-a-django-telegram-bot/




