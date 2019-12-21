# althea

## requirements
- python 3.6
- pandas 0.25.1
- python-telegram-bot 12.1.1
- tweepy 3.8.0
- requests 2.22.0

## what it does 
Forward tweets on twitter to telegram using twitter streaming API.

## disclaimer
Occasionally the bot may be disconnected from the stream. While it will
automatically reconnect on its own, a few tweets may be dropped
in between the time it was disconnected and reconnected. Use another
solution if integrity of tweets are important.