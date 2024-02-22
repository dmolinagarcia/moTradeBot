sudo apt --assume-yes update
sudo NEEDRESTART_MODE=a apt-get dist-upgrade --yes
sudo NEEDRESTART_MODE=a apt-get --assume-yes install software-properties-common
sudo add-apt-repository --yes universe
sudo NEEDRESTART_MODE=a apt-get --assume-yes install git python3 vim bsdmainutils sqlite3 python3-pip jq nodejs python2 cron whiptail
sudo NEEDRESTART_MODE=a apt-get dist-upgrade --yes
umask 027
sudo ln -s -f /usr/bin/python3.8 /usr/bin/python
sudo pip3 install --target /lib/python3.8 --upgrade testresources Django json2html flask 
## sudo pip3 install git+git://github.com/Lu-Yi-Hsun/iqoptionapi.git
## IQOption no longer supported
echo "Europe/Madrid" | sudo tee /etc/timezone
sudo dpkg-reconfigure --frontend noninteractive tzdata
sudo timedatectl set-timezone "Europe/Madrid"
git clone https://github.com/dmolinagarcia/moTradeBot.git
##################################################
##      AREA TO CONFIGURE SECRETS AND KEYS!
##
##
##
##

## Generate BINGXCFG.py
whiptail --msgbox --title "Please enter your BINGX credentials" "This information won't ever be shared with anyone" 8 80
vAPIKEY=$(whiptail --inputbox "Enter your BINGx APIKEY" 8  80 3>&1 1>&2 2>&3)
vSECRETKEY=$(whiptail --inputbox "Enter your BINGx SECRETKEY" 8  80 3>&1 1>&2 2>&3)
vACCOUNT=$(whiptail --radiolist --title "Use REAL or TEST account?" "Please select your preferred option" 8 80 2 "REAL" "Use your REAL account" OFF  "TEST" "Use your TEST account" ON  3>&1 1>&2 2>&3)

case $vACCOUNT in
    REAL ) vAPIURL="https://open-api.bingx.com"; break;;
    TEST ) vAPIURL="https://open-api-vst.bingx.com";;
esac

cat > BINGXCFG.py << EOF
APIURL = "$vAPIURL"
APIKEY = "$vAPIKEY"
SECRETKEY = "$vSECRETKEY"
EOF


##
##
##
##
##################################################
sudo mkdir -p /home/moTrade
sudo mv moTradeBot/* /home/moTrade
sudo mv moTradeBot/.* /home/moTrade
sudo useradd moTrade -M -s /bin/bash
sudo chown -R moTrade:moTrade /home/moTrade
rm -rf /home/ubuntu/moTradeBot


