# MoTrade

## DISCLAIMER
I offer no guarantee on the outcome of this software. It's under heavy development, and even though its objectives are ambitious, they haven't been fulfilled yet. Consider it a combined exercise in programming and trading all at once. Using it blindly can, and most certaingly will, make you lose money.

1. [Introduction](#introduction)
2. [Setup](#setup)
3. [Objectives](#objectives)
4. [Types of operation](#operation)
5. [Uninstall](#uninstall)

<a name="introduction"></a>

## Introduction
MoTrade is an automated/algorithmic trading platform. It's main purpose is to trade on a 24x7 basis with cryptocurrencies with no human intervention at all and yet, make a profit. Of course some human input would, most likely, obtain increased returns, but that's not the goal of this proyect.

This is the user manual. The document is still in a work-in-progress state. Expect tons of changes.

<a name="setup"></a>

## Setup
### Infrastructure

Sign up for an oracle free account if you don't already have one.

To deploy the infrastructure, open cloud shell on your OCI account and run

    /bin/bash -c "$(curl -fsSL https://github.com/dmolinagarcia/moTradeBot/raw/main/setup/deploy.sh)"
    . ~/.bash_profile

Write down your public ip.    

### Obtain mooo.com subdomain
https://freedns.afraid.org/

Assign the public ip to your subdomain and write down your subdomain.
    
### Software    
Before installing the moTrade Bot, you will need to gather some information :

    PUBLIC_IP
    moTrade SUBDOMAIN NAME
    Your BINGx APIKEY
    Yout BINGx SECRETKEY

Login as user ubuntu (moSSH_<your_motrade_id>) and run the installer

    /bin/bash -c "$(curl -fsSL https://github.com/dmolinagarcia/moTradeBot/raw/main/setup/install.sh)"


<a name="objectives"></a>

## Objectives

- Create a 100% fully automated/autonomous trading bot
- Implement a web interface for easy access
- Make it secure.
- It should be able to provide historic data for the end user
- 100% integration with, at least one, trading platform

<a name="operation"></a>

## Types of operation

### Protected Trade

In protected trade mode, we rely on limits to close operations. A operation is opened if ADX > limitOpen, and the sign is determined by DiffDI. limitBuy and limitSell are also enforced. A trailing stop is set based on the stopLoss value. The operation is closed on DiffDI Crossover, or automatically by the stopLoss.

### Normal Trade
TO-DO

<a name="uninstall"></a>

## Uninstall

Warning! This procedure will completely erase your moTrade installation. Any open positions on BINGX will remain Open and not under control of your moTrade bot.

First, find your MOTRADE_ID. It's the 6 letter identifier at the end of the container name. Then, run the following from your Cloud Shell instance.

    curl -fsSL https://raw.githubusercontent.com/dmolinagarcia/moTradeBot/main/setup/cleanup.sh | bash -s -- <YOUR_MOTRADE_ID>


    

