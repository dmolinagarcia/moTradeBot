# How to Install MoTrade

## Infrastructure

Sign up for an oracle free account if you don't already have one.

To deploy the infrastructure, open cloud shell on your OCI account and run

    /bin/bash -c "$(curl -fsSL https://github.com/dmolinagarcia/moTradeBot/raw/main/setup/deploy.sh)"
    . ~/.bash_profile

Write down your public ip.    

## Obtain mooo.com subdomain
https://freedns.afraid.org/

Assign the public ip to your subdomain and write down your subdomain.
    
## Software    
Before installing the moTrade Bot, you will need to gather some information :

    PUBLIC_IP
Login as user ubuntu (moSSH_<your_motrade_id>)
    
    sudo apt update
    sudo apt --assume-yes upgrade
    sudo apt-get --assume-yes install software-properties-common
    sudo add-apt-repository universe
    sudo apt-get --assume-yes install git python3 vim bsdmainutils sqlite3 python3-pip jq nodejs python cron 
    sudo apt --assume-yes upgrade
    umask 027
    sudo ln -s -f /usr/bin/python3.8 /usr/bin/python
    sudo pip3 install --target /lib/python3.8 --upgrade testresources Django json2html flask git+git://github.com/Lu-Yi-Hsun/iqoptionapi.git
    echo "Europe/Madrid" | sudo tee /etc/timezone
    sudo dpkg-reconfigure --frontend noninteractive tzdata
    sudo timedatectl set-timezone "Europe/Madrid"
    
## Registro contra github    
 (Es esto necesario una vez que el repo es publico?)

    sudo useradd moTrade -m -s /bin/bash
    sudo su - moTrade
   
## moTrade

    git clone git@github.com:dmolinagarcia/moTrade.git
    cd moTrade
    nohup ./manage.py runserver 8080 > django.log &
    curl http://localhost:8080/clear/
    sqlite3 db.sqlite3
    vacuum;
    .quit

(Aqui tengo que obtener una BD lista para arrancar desde el repo)

## install.ksh

Esto debe configurar.

Secret KEY en MoTrade/settings.py
allowed hosts en MoTrade/settings.py
BINGX keys en BINGXCFG.py
Cuenta real o demo en BINGXCFG.py
    
## Deploy under HTTPS server
(Todo esto, se debe desplegar tambien con el install.ksh, los ficheros al menos!)

mkdir /var/log/moTrade
chown www-data:www-data /var/log/moTrade

Connectivity

    Add ingress rule (pending cmd. add to setup.md) (80 y 443)
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
    sudo netfilter-persistent save

Install apache

    sudo apt-get install apache2
    sudo systemctl restart apache2
    
Set up VirtualHost

    sudo mkdir /var/www/<your domain>
    sudo chown -R moTrade:moTrade <your domain>
    sudo chmod -R 755 <your domain>
    sudo vi /var/www/<your domain>/index.html
    <html>
    <head>
        <title>Welcome to Your_domain!</title>
    </head>
    <body>
        <h1>Success!  The your_domain virtual host is working!</h1>
    </body>
    </html>
    sudo vi /etc/apache2/sites-available/<your domain>.conf
    <VirtualHost *:80>
        ServerAdmin webmaster@localhost
        ServerName <your domain>
        DocumentRoot /var/www/<your domain>
        ErrorLog ${APACHE_LOG_DIR}/<your domain>_error.log
        CustomLog ${APACHE_LOG_DIR}&<your domain>_access.log combined
        Alias /static/ /home/moTrade/moTrade/MT/static
        
        WSGIDaemonProcess www-motrade processes=2 threads=12 python-path=/home/moTrade/moTrade
        WSGIApplicationGroup %{GLOBAL}
        WSGIProcessGroup www-motrade
        WSGIScriptAlias / /home/moTrade/moTrade/MoTrade/wsgi.py

        <Directory /home/moTrade/moTrade/MoTrade >
            Require all granted
        </Directory>

        <Directory /home/moTrade/moTrade/MT/static >
            Require all granted
        </Directory>
    </VirtualHost>

    Añadir al virtualhost 000-default.conf
    y al default-ssl

    Redirect 404 /
    ErrorDocument 404 "  "

    Añadir al apache2.conf

    WSGIRestrictEmbedded On
    WSGILazyInitialization On    

    sudo a2ensite <your domain>.conf
    sudo a2ensite 000-default.conf
    sudo a2ensite default-ssl.conf
    sudo a2enmod wsgi

    Añadir usuario apache al grupo de motrade
    sudo usermod www-data -G www-data,moTrade

    Restart apache
    sudo systemctl restart apache2

Certificado SSL

    sudo apt install certbot python3-certbot-apache
    comentar las lineas wsgi del <your domain>.conf
    sudo certbot --apache
    sudo systemctl status certbot.timer
    sudo certbot renew --dry-run
    descomentar del <your domain>-le
    
BINGX as a service
    
    sudo vi /lib/systemd/system/BINGX.service
    
[Unit]
Description=BINGX API service
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
User=moTrade
Group=moTrade
Type=simple
ExecStart=/usr/bin/python3 /home/moTrade/moTrade/BINGX.py
StandardInput=tty-force
StandardOutput=append:/home/moTrade/moTrade/BINGX.log
StandardError=append:/home/moTrade/moTrade/BINGX.error.log

[Install]
WantedBy=multi-user.target
    
    sudo systemctl daemon-reload
    sudo systemctl enable BINGX.service
    sudo systemctl start BINGX.service

## Initialize system
```
Edit BINGXCFG.py to set APIKEY and APYSECRET
Edit APIURL to set demo or real account
Set admin password
    python manage.py changepassword admin
./manage.py makemigrations
./manage.py migrate
invoke clear (<domaing>/clear)
In main page, stop all unwanted strategies
Call for balance
In main page, unlock all wanted strategies
Add the following into moTrade crontab
    */5 * * * * curl -k https://motrade.mooo.com/process/
    1 1 * * * curl -k https://motrade.mooo.com/balance/
All set!
```

## Update from GITHUB

As moTrade user
    cd ~/moTrade
    git pull

As ubuntu user
    sudo systemctl restart apache2
    sudo systemctl restart BINGX.service
    
    
## Cleanup

Warning! This procedure will completely erase your moTrade installation. Any open positions on BINGX will remain Open and not under control of your moTrade bot.

First, find your MOTRADE_ID. It's the 6 letter identifier at the end of the container name

    curl -fsSL https://raw.githubusercontent.com/dmolinagarcia/moTradeBot/main/setup/cleanup.sh | bash -s -- <YOUR_MOTRADE_ID>


    
