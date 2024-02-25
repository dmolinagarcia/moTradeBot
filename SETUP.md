
## Initialize system
```
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
