# MoTrade

## DISCLAIMER
I offer no guarantee on the outcome of this software. It's under heavy development, and even though its objectives are ambitious, they haven't been fulfilled yet. Consider it a combined exercise in programming and trading all at once. Using it blindly can, and most certaingly will, make you lose money.

1. [Introduction](#introduction)
2. [Objectives](#objectives)
3. [Types of operation](#operation)

<a name="introduction"></a>

## Introduction
MoTrade is an automated/algorithmic trading platform. It's main purpose is to trade on a 24x7 basis with cryptocurrencies with no human intervention at all and yet, make a profit. Of course some human input would, most likely, obtain increased returns, but that's not the goal of this proyect.

This is the user manual. The document is still in a work-in-progress state. Expect 

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
