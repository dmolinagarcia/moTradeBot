# MoTrade

> [!CAUTION]
> DISCLAIMER!!
> 
> I offer no guarantee on the outcome of this software. It's under heavy development, and even though its objectives are ambitious, they haven't been fulfilled yet. Consider it a combined exercise in programming and trading all at once. Using it blindly can, and most certaingly will, make you lose money.

- [MoTrade](#motrade)
  - [Introduction](#introduction)
  - [Objectives](#objectives)
  - [Setup](#setup)
    - [Infrastructure](#infrastructure)
    - [Obtain bot.nu subdomain](#obtain-botnu-subdomain)
    - [Create your BINGX API](#create-your-bingx-api)
    - [Software](#software)
  - [Getting Started](#getting-started)
  - [Global Settings](#global-settings)
    - [Max Margin](#max-margin)
    - [Global Take Profit](#global-take-profit)
  - [Indicators 101](#indicators-101)
  - [Operation](#operation)
    - [Stop Loss](#stop-loss)
  - [Error Codes](#error-codes)
  - [Uninstall](#uninstall)
- [Changelog](#changelog)

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

<a name="globalsettings"></a>
## Global Settings

<a name="maxmargin"></a>
### Max Margin
We call "Margin" to the amount of USDT you have in open trades. moTrade uses your balance in the Perpetual Futures account, but it will only use the amount you set as Max Margin. If the margin is small (Below 300 USDT) the max margin may be exceeded, as there is some heavy rounding involved, specially in cryptos with higher prices. The max margin will be evenly splitted among all enabled strategys. So, if you set your max margin to 100 USDT, with 50 enabled strategies by default, 2 USDT will be used for each of them. For higher priced cryptos, the minimal buy amount is usually higher, so you may end up trading more than your max margin.

After each closed operation, the profit or losses will be added to your max margin.

<a name="globaltp"></a>
### Global Take Profit
The global Take Profit (GTP) pretends to maximize benefits during periods of high market greed. During this periods, is common to have huge price increases, followed by deep dips. This dips try to "close LONGs", and can cause huge losses, and the chances are too quick for the indicators to react on time. We want to avoid operating if this happens.

The GTP triggers when the potential profit represents a big percentaje of our total balance. 10% usually works fine, although it can be adjusted. If GTP is enabled and we hit this percentage, it triggers an auto close on all open positions, and bot operations are interrupted for some amount of time, also configurable. 

<a name="indicators101"></a>
## Indicators 101
TO-DO

<a name="operation"></a>
## Operation
TO-DO

<a name="stoploss"></a>
### Stop Loss
TO-DO Here we explain how stop loss works. Each strategy has a stopLoss property (Must be negative!) which defines the starting stopLoss. This is a trailing stop and each cycle, the stopLoss is set to follow the profit. If stop loss is -25 and profit is 5, stop loss is set to -20. 
When profit reaches 10, stopLoss jumps to 1, to secure some profit.
Each cycle, the gap between profit and stop loss is reduces by 40%. So, if profit does not grow, stopLoss climbs up asymptotically to the profit. This is meant to secure higher profit if the price goes high fast.

<a name="errorcodes"></a>
## Error Codes
TO-DO

<a name="uninstall"></a>
## Uninstall

Warning! This procedure will completely erase your moTrade installation. Any open positions on BINGX will remain Open and not under control of your moTrade bot.

First, find your MOTRADE_ID. It's the 6 letter identifier at the end of the container name. Then, run the following from your Cloud Shell instance.

    curl -fsSL https://raw.githubusercontent.com/dmolinagarcia/moTradeBot/main/setup/cleanup.sh | bash -s -- <YOUR_MOTRADE_ID>

<a name="changelog"></a>
# Changelog
## Unreleased
- **Added Global TakeProfit**. Closes all operations and suspends bot for a given amount of time to prevent falling in big dips after steep price increases.