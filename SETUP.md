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
Set admin password
    python manage.py changepassword admin
./manage.py makemigrations
./manage.py migrate
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
