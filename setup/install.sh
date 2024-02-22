sudo apt --assume-yes update
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update && 
    sudo apt-get -o Dpkg::Options::="--force-confold" upgrade -q -y --force-yes &&
    sudo apt-get -o Dpkg::Options::="--force-confold" dist-upgrade -q -y --force-yes
sudo apt-get --assume-yes install software-properties-common
sudo add-apt-repository universe
sudo apt-get --assume-yes install git python3 vim bsdmainutils sqlite3 python3-pip jq nodejs python cron
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update && 
    sudo apt-get -o Dpkg::Options::="--force-confold" upgrade -q -y --force-yes &&
    sudo apt-get -o Dpkg::Options::="--force-confold" dist-upgrade -q -y --force-yes
umask 027
sudo ln -s -f /usr/bin/python3.8 /usr/bin/python
sudo pip3 install --target /lib/python3.8 --upgrade testresources Django json2html flask 
## sudo pip3 install git+git://github.com/Lu-Yi-Hsun/iqoptionapi.git
## IQOption no longer supported
echo "Europe/Madrid" | sudo tee /etc/timezone
sudo dpkg-reconfigure --frontend noninteractive tzdata
sudo timedatectl set-timezone "Europe/Madrid"