#!/bin/bash

cd /home/ubuntu
date
rm -rf moTradeBot
git clone https://github.com/dmolinagarcia/moTradeBot.git >> /dev/null 2>&1
cd moTradeBot
vLATESTTAG=$(git tag --sort=creatordate | tail -1)
vCURRENTTAG=$(sudo -u moTrade sh -c "cd /home/moTrade; git tag | tail -1")

cd /home/ubuntu/moTradeBot
git checkout $vLATESTTAG >> /dev/null 2>&1

if [ "$vCURRENTTAG" == "$vLATESTTAG" ]
then
        echo Current: $vCURRENTTAG Latest: $vLATESTTAG
        echo moTrade is up to date!
else
        echo Current: $vCURRENTTAG Latest: $vLATESTTAG
        echo Updating moTrade ...
        sudo rm -rf /home/moTrade/.git
        sudo rsync -a /home/ubuntu/moTradeBot/ /home/moTrade
        sudo chown -R moTrade:moTrade /home/moTrade
        cd /home/ubuntu
        rm -rf /home/ubuntu/moTradeBot
        echo Updated
        sudo systemctl stop apache2
        sudo -u moTrade sh -c "cd /home/moTrade; python ./manage.py makemigrations" >> /dev/null 2>&1
        sudo -u moTrade sh -c "cd /home/moTrade; python ./manage.py migrate"  >> /dev/null 2>&1
        sudo systemctl start apache2
        sudo systemctl restart BINGX.service
        vCURRENTTAG=$(sudo -u moTrade sh -c "cd /home/moTrade; git tag | tail -1")
        echo Current: $vCURRENTTAG Latest: $vLATESTTAG
fi
