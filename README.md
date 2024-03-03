# MoTrade

## DISCLAIMER
I offer no guarantee on the outcome of this software. It's under heavy development, and even though its objectives are ambitious, they haven't been fulfilled yet. Consider it a combined exercise in programming and trading all at once. Using it blindly can, and most certaingly will, make you lose money.

- [Introduction](#introduction)
- [Objectives](#objectives)
- [Setup](#setup)
- [Getting started](#gettingstarted)
- [Indicators 101](#indicators101)
- [Types of operation](#operation)
- [Error codes](#errorcodes)
- [Uninstall](#uninstall)

<a name="introduction"></a>
## Introduction
MoTrade is an automated/algorithmic trading platform. It's main purpose is to trade on a 24x7 basis with cryptocurrencies with no human intervention at all and yet, make a profit. Of course some human input would, most likely, obtain increased returns, but that's not the goal of this proyect.

This is the user manual. The document is still in a work-in-progress state. Expect tons of changes.

<a name="objectives"></a>
## Objectives

- Create a 100% fully automated/autonomous trading bot
- Implement a web interface for easy access
- Make it secure.
- It should be able to provide historic data for the end user
- 100% integration with, at least one, trading platform

<a name="setup"></a>
## Setup
### Infrastructure

Sign up for an oracle free account if you don't already have one.

To deploy the infrastructure, open cloud shell on your OCI account and run

    /bin/bash -c "$(curl -fsSL https://github.com/dmolinagarcia/moTradeBot/raw/main/setup/deploy.sh)"
    . ~/.bash_profile

Write down your public ip.    

### Obtain bot.nu subdomain
https://freedns.afraid.org/

bot.nu is recommended, as it is less demanded and it is easier to get a valid SSL Certificate.

Assign the public ip to your subdomain and write down your subdomain.

### Create your BINGX API

Write down your APIKEY and SECRETKEY. Do not share this! Add your public IP to the whitelist.
    
### Software    
Before installing the moTrade Bot, you will need to gather some information :

    PUBLIC_IP
    moTrade SUBDOMAIN NAME
    Your BINGx APIKEY
    Your BINGx SECRETKEY
    A valid EMAIL

Please make sure your Oracle Cloud Public IP is whitelisted on BINGX API !!

Login as user ubuntu (moSSH_<your_motrade_id>) and run the installer

    /bin/bash -c "$(curl -fsSL https://github.com/dmolinagarcia/moTradeBot/raw/main/setup/install.sh)"

<a name="gettingstarted"></a>
## Getting Started

Once you complete moTrade installation, you need to configure how much you intend to risk. Login to your moTrade Dashboard and enter your desired configuration in the top box:

![image](https://github.com/dmolinagarcia/moTradeBot/assets/30756488/8832f9eb-9aef-40b4-985e-6e55aada7132)

The Max Margin setting determines how much USDT will moTrade use for your positiones. The total amount entered will be split even amongst all running strategies. Then enable the bot to begin operating. When the bot is disabled no operation will be executed at all, so, no new positions will be opened, and existing positions will be closed.

Once this is done, you need to understand how moTrade works to get the most ouf of it. This is not a AI/ML powered bot. It won't learn over time, unless I alter it's code to improve its results. moTrade is bases on trading indicators, mostly extracted from TradingView. Usually, indicator are only meaningful whenever there is a decent market volume for any given asset. Because of this, only cryptos with a high volume are used. Also, no new operations are opened if the US market are closed. The reason behind this is simple. A huge percentage of crypto exchanges comes from US markets, so volume is usually higher when they are opened. This means you can miss good oportunities when the markets are closed, but trust me, this is much better in the long run!

<a name="indicators101"></a>
## Indicators 101
TO-DO

<a name="operation"></a>
## Types of operation
TO-DO

<a name="errorcodes"></a>
## Error Codes
TO-DO

<a name="uninstall"></a>
## Uninstall

Warning! This procedure will completely erase your moTrade installation. Any open positions on BINGX will remain Open and not under control of your moTrade bot.

First, find your MOTRADE_ID. It's the 6 letter identifier at the end of the container name. Then, run the following from your Cloud Shell instance.

    curl -fsSL https://raw.githubusercontent.com/dmolinagarcia/moTradeBot/main/setup/cleanup.sh | bash -s -- <YOUR_MOTRADE_ID>
