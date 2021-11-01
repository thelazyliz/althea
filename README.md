# althea

## Requirements
- python 3.6
- pandas 0.25.1
- python-telegram-bot 12.1.1
- tweepy 3.8.0
- requests 2.22.0

## What it does 
forward tweets on twitter to telegram using twitter streaming api.

## Disclaimer
occasionally the bot may be disconnected from the stream. while it will
automatically reconnect on its own, a few tweets may be dropped
in between the time it was disconnected and reconnected. use another
solution if integrity of tweets are important.
