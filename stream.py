import tweepy
from tweepy.error import TweepError
import json
import logging, time
import threading
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram
from cfg import *
from cmc import get_market_quotes
import re
import os
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
insert_logger = logging.getLogger('stream.py')
fh = logging.FileHandler(f'./logs/stream.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
insert_logger.addHandler(fh)


class MyStreamListener(tweepy.StreamListener):

    def __init__(self, chat_id, following_names):
        tweepy.StreamListener.__init__(self)
        self.bot = telegram.Bot(token=ALTHEA_TOKEN)
        self.chat_id = chat_id
        self.following_names = following_names

    def send_telegram_message(self, status):
        link = f'https://www.twitter.com/{status.user.screen_name}/status/{status.id_str}'
        if self.post_criteria(status):
        # if not hasattr(status, 'retweeted_status') and status.author.screen_name.lower() in self.following_names:
            insert_logger.info(f'PASSED: {status.text}\nLINK: {link}')
            if status.truncated:
                tweet = status.extended_tweet['full_text']
            else:
                tweet = status.text
            status_str = f"<b>Author</b>: {status.author.screen_name}\n" \
                         f"<b>Tweet</b>: {tweet}\n" \
                         f"<b>Link</b>: {link}"
            try:
                self.bot.send_message(chat_id=self.chat_id, text=status_str, parse_mode=telegram.ParseMode.HTML)
            except Exception as e:
                insert_logger.exception(str(e))
        else:
            insert_logger.info(f'SKIPPED: {status.text}\nLINK: {link}')

    def post_criteria(self, status):
        if hasattr(status, 'retweeted_status'):
            return False
        elif status.in_reply_to_screen_name and status.in_reply_to_screen_name != status.author.screen_name:
            return False
        elif status.author.screen_name.lower() not in self.following_names:
            return False
        else:
            return True

    def on_status(self, status):
            threading.Thread(target=self.send_telegram_message, args=(status,)).start()


class Twitter2Tg:

    def __init__(self, chat_name):
        insert_logger.info(f'starting new process for {chat_name}')
        self.chat_id = TG_CHATS[chat_name]
        self.following = {}
        self.my_stream = None
        self.filename = 'files/following.txt'
        self.positions_csv = 'files/positions.csv'
        self.positions_df = pd.read_csv(self.positions_csv, index_col='index')
        self.bot = telegram.Bot(token=ALTHEA_TOKEN)
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
        self.api = tweepy.API(auth)
        self.init_following_ids()
        if self.following:
            self.setup_twitter()
        else:
            insert_logger.info(f'following.txt is empty')
        self.setup_tg()
        if not os.path.exists(self.positions_csv):
            with open(self.positions_csv, 'w') as f:
                f.write('index,username,coin,open_price,open_time,close_price,close_time,open_recorded_by,close_recorded_by,return_rate')

    def init_following_ids(self):
        try:
            with open(self.filename, 'r') as f:
                following_names = f.read().splitlines()
            if following_names:
                following_ids = [user.id_str for user in self.api.lookup_users(screen_names=following_names)]
                self.following = dict(zip(following_names, following_ids))
        except Exception as e:
            insert_logger.exception(str(e))

    def setup_twitter(self):
        try:
            my_stream_listener = MyStreamListener(self.chat_id, list(self.following.keys()))
            self.my_stream = tweepy.Stream(
                auth=self.api.auth, listener=my_stream_listener, tweet_mode='extended',
                exclude_replies=True, include_rts=False
            )
            insert_logger.info(self.following)
            self.my_stream.filter(follow=self.following.values(), is_async=True, stall_warnings=True)
            # self.my_stream.filter(track=['binance'], is_async=True)
        except Exception as e:
            insert_logger.exception(str(e))

    def setup_tg(self):
        try:
            updater = Updater(token=ALTHEA_TOKEN, request_kwargs={'read_timeout': 10, 'connect_timeout': 10})
            dispatcher = updater.dispatcher
            tg_follow_handler = CommandHandler('follow', self.follow)
            tg_unfollow_handler = CommandHandler('unfollow', self.unfollow)
            tg_check_follow_handler = CommandHandler('checkfollow', self.check_follow)
            tg_open_pos_handler = CommandHandler('open', self.open_position)
            tg_close_pos_handler = CommandHandler('close', self.close_position)
            dispatcher.add_handler(tg_follow_handler)
            dispatcher.add_handler(tg_unfollow_handler)
            dispatcher.add_handler(tg_check_follow_handler)
            dispatcher.add_handler(tg_open_pos_handler)
            dispatcher.add_handler(tg_close_pos_handler)
            dispatcher.add_error_handler(self.error)
            updater.start_polling()
            updater.idle()
        except Exception as e:
            insert_logger.exception(str(e))

    def error(update, context):
        insert_logger.exception('Update "%s" caused error "%s"', update, context.error)

    def follow(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        try:
            args = update.message.text.split(" ")[1]
        except IndexError:
            update.message.reply_text('Please type /follow [twitter username]')
            return
        try:
            if args.lower() in self.following.keys():
                update.message.reply_text(f'You are already following {args}.')
                return
            user = self.api.lookup_users(screen_names=[args])
            with open(self.filename, 'a+') as f:
                f.write(f'{args.lower()}\n')
            self.following[args.lower()] = user[0].id_str
            if self.my_stream:
                self.my_stream.disconnect()
            self.setup_twitter()
            update.message.reply_text(f'{args} has been added to your following.')
        except TweepError as e:
            if '17' in str(e):
                update.message.reply_text('Unable to find the username specified.')
        except Exception as e:
            insert_logger.exception(str(e))

    def unfollow(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        try:
            args = update.message.text.split(" ")[1]
        except IndexError:
            update.message.reply_text('Please type /unfollow [twitter username]')
            return
        try:
            if args.lower() not in self.following.keys():
                update.message.reply_text(f'You are not following {args}.')
                return
            with open(self.filename, 'r+') as f:
                d = f.readlines()
                f.seek(0)
                for i in d:
                    if i.lower() != f'{args.lower()}\n':
                        f.write(i)
                    f.truncate()
            del self.following[args.lower()]
            self.my_stream.disconnect()
            self.setup_twitter()
            update.message.reply_text(f'{args} has been unfollowed.')
        except Exception as e:
            insert_logger.exception(str(e))

    def check_follow(self, bot, update):
        try:
            if update.message.chat.id != self.chat_id:
                update.message.reply_text('You are not authorized to use this bot.')
                return
            update.message.reply_text(f'You are following: {", ".join(self.following.keys())}')
        except Exception as e:
            insert_logger.exception(str(e))

    def open_position(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        try:
            args = update.message.text.split(" ")
            user = args[1].lower()
            coin = args[2].upper()
        except IndexError:
            update.message.reply_text('Please type /open [twitter username] [coin ticker]')
            return
        if not re.match('\w+', coin):
            update.message.reply_text('Only alphanumeric tickers are allowed')
            return
        if user not in self.following.keys():
            update.message.reply_text('You are not following this person')
            return
        resp = get_market_quotes([coin])
        if 'error' in resp:
            update.message.reply_text('Cannot find this coin on CMC leh')
            return
        else:
            cur_price = resp['data'][coin]['quote']['USD']['price']
            cur_time = int(time.time())
            self.positions_df.append({
                'username': user,
                'coin': coin,
                'open_price': cur_price,
                'open_time': cur_time,
                'close_price': None,
                'close_time': None,
                'open_recorded_by': update.message.from_user.username,
                'close_recorded_by': None,
                'return_rate': None
            })
            self.positions_df.to_csv(self.positions_csv, index_label='index')
            update.message.reply_text(
                f"Successfully added your position for {coin} at ${cur_price} USD at time "
                f"{time.strftime('%Y-%m-%d %H:%M:%S UTC+0', time.gmtime(cur_time))}"
            )
            self.bot.send_message(
                chat_id=self.chat_id, text=self.positions_df.to_html(), parse_mode=telegram.ParseMode.HTML
            )

    def close_position(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        try:
            args = update.message.text.split(" ")
            user = args[1].lower()
            coin = args[2].upper()
        except IndexError:
            update.message.reply_text('Please type /close [twitter username] [coin ticker] [index number (optional)]')
            return
        if len(args) > 3:
            try:
                index_number = int(args[3])
            except Exception as e:
                insert_logger.exception(str(e))
                update.message.reply_text('Are you sure you entered a valid number?')
                return
        else:
            index_number = None
        if not re.match('\w+', coin):
            update.message.reply_text('Only alphanumeric tickers are allowed')
            return
        if user not in self.following.keys():
            update.message.reply_text('You are not following this person')
            return
        open_positions = self.positions_df[self.positions_df['coin'] == coin and self.positions_df['close'] is None]
        if len(open_positions) == 0:
            update.message.reply_text("I can't find an open position with this ticker.")
            return
        elif len(open_positions) > 1:
            if not index_number:
                update.message.reply_text(
                    'Hm there are more than 1 open trades involving this coin. '
                    'Please repeat the command and include index number.'
                )
                self.bot.send_message(
                    chat_id=self.chat_id, text=open_positions.to_html(), parse_mode=telegram.ParseMode.HTML
                )
                return
        else:
            index_number = open_positions.index[0]
        resp = get_market_quotes([coin])
        if 'error' in resp:
            update.message.reply_text('Cannot find this coin on CMC leh')
            return
        else:
            cur_price = resp['data'][coin]['quote']['USD']['price']
            cur_time = int(time.time())
            open_price = self.positions_df.loc[[index_number]]['open_price']
            self.positions_df.loc[[index_number]]['close_price'] = cur_price
            self.positions_df.loc[[index_number]]['close_time'] = cur_time
            self.positions_df.loc[[index_number]]['close_recorded_by'] = update.message.from_user.username
            self.positions_df.loc[[index_number]]['return_rate'] = 1 - (cur_price/open_price).round(4)
            self.positions_df.to_csv(self.positions_csv, index_label='index')
            update.message.reply_text(
                f"Successfully closed your position for {coin} at ${cur_price} USD at time "
                f"{time.strftime('%Y-%m-%d %H:%M:%S UTC+0', time.gmtime(cur_time))}"
            )
            self.bot.send_message(
                chat_id=self.chat_id, text=self.positions_df.to_html(), parse_mode=telegram.ParseMode.HTML
            )


if __name__ == '__main__':
    try:
        chat = input('Which chat are you posting to? Press 1 for nhb and 2 for test: ')
        if chat == '1':
            t2tg = Twitter2Tg('nhb')
        elif chat == '2':
            t2tg = Twitter2Tg('test')
        else:
            print('Invalid option.')
    except Exception as e:
        insert_logger.exception(str(e))