import tweepy
from tweepy.error import TweepError
from tweepy.models import Status
import json
import logging
import time
import threading
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from urllib3.exceptions import IncompleteRead
import telegram
from cfg import *
from cmc import get_market_quotes
from pgconnector import PostgresConnector
import re
from utils import prettify_position

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

    def on_data(self, raw_data):
        """Called when raw data is received from connection.
        Override this method if you wish to manually handle
        the stream data. Return False to stop stream and close connection.
        """
        try:
            data = json.loads(raw_data)

            if 'in_reply_to_status_id' in data:
                status = Status.parse(self.api, data)
                if self.on_status(status) is False:
                    return False
            elif 'delete' in data:
                delete = data['delete']['status']
                if self.on_delete(delete['id'], delete['user_id']) is False:
                    return False
            elif 'event' in data:
                status = Status.parse(self.api, data)
                if self.on_event(status) is False:
                    return False
            elif 'direct_message' in data:
                status = Status.parse(self.api, data)
                if self.on_direct_message(status) is False:
                    return False
            elif 'friends' in data:
                if self.on_friends(data['friends']) is False:
                    return False
            elif 'limit' in data:
                if self.on_limit(data['limit']['track']) is False:
                    return False
            elif 'disconnect' in data:
                if self.on_disconnect(data['disconnect']) is False:
                    return False
            elif 'warning' in data:
                if self.on_warning(data['warning']) is False:
                    return False
            elif 'scrub_geo' in data:
                if self.on_scrub_geo(data['scrub_geo']) is False:
                    return False
            elif 'status_withheld' in data:
                if self.on_status_withheld(data['status_withheld']) is False:
                    return False
            elif 'user_withheld' in data:
                if self.on_user_withheld(data['user_withheld']) is False:
                    return False
            else:
                insert_logger.error("Unknown message type: %s", raw_data)
        except IncompleteRead as e:
            insert_logger.exception(str(e))
            time.sleep(5)
            return True
        

class Twitter2Tg:

    def __init__(self, chat_name):
        insert_logger.info(f'starting new process for {chat_name}')
        self.chat_id = TG_CHATS[chat_name]
        self.following = {}
        self.my_stream = None
        self.filename = 'files/following.txt'
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
            tg_check_pos_handler = CommandHandler('checkposition', self.check_position)
            dispatcher.add_handler(tg_follow_handler)
            dispatcher.add_handler(tg_unfollow_handler)
            dispatcher.add_handler(tg_check_follow_handler)
            dispatcher.add_handler(tg_open_pos_handler)
            dispatcher.add_handler(tg_close_pos_handler)
            dispatcher.add_handler(tg_check_pos_handler)
            dispatcher.add_error_handler(self.error)
            updater.start_polling()
            updater.idle()
        except Exception as e:
            insert_logger.exception(str(e))

    def error(self, update, context):
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

    ## *** THIS SECTION COMMANDS ARE FOR THE OPEN/CLOSE POSITION FEATURE ***
    def check_position(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        args = update.message.text.split(" ")
        try:
            mode = args[1].lower()
            if mode not in ['user', 'coin']:
                update.message.reply_text(f'This mode does not exist')
                return
            kwargs = {}
            if mode == 'user':
                kwargs['username'] = args[2].lower()
            else:
                kwargs['coin'] = args[2].upper()
            if len(args) == 4:
                if args[3] == 'open':
                    kwargs['open_only'] = True
                elif args[3] == 'close':
                    kwargs['close_only'] = True
            pg = PostgresConnector(ALTHEA_DB_PATH)
            positions = pg.get_positions(self.chat_id, **kwargs)
            pg.close()
            if not positions:
                update.message.reply_text(f'No positions found :(')
                return
            reply_string = prettify_position(positions)
            update.message.reply_text(reply_string)
            return
        except IndexError:
            update.message.reply_text(
                'Your arguments are not correct.'
                'Please type /checkposition [mode] [mode identifier] '
                '[open/close (optional)]\n\n'
                'Possible modes are `user` or `coin` at the moment'
            )
            return

    def open_position(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        args = update.message.text.split(" ")
        if len(args) != 3:
            update.message.reply_text(
                'Only 2 arguments are allowed. '
                'Please type /open [user] [coin]'
            )
            return
        else:
            user = args[1].lower()
            coin = args[2].upper()
        if not re.match('\w+', coin):
            update.message.reply_text('Only alphanumeric tickers are allowed')
            return
        elif not re.match('[\w_]+', user):
            update.message.reply_text(
                'Identifiers can only contain alphanumeric '
                'and underscore characters'
            )
            return
        resp = get_market_quotes([coin])
        if 'error' in resp:
            update.message.reply_text('Cannot find this coin on CMC leh')
            return
        else:
            pg = PostgresConnector(ALTHEA_DB_PATH)
            cur_price = float(resp['data'][coin]['quote']['USD']['price'])
            cur_time = int(time.time())
            added = pg.insert_position([
                user,
                coin,
                cur_price,
                cur_time,
                update.message.from_user.username,
                self.chat_id
            ])
            pg.close()
            if added:
                update.message.reply_text(
                    f'Successfully added your position for {coin} at '
                    f'${cur_price:.2f} USD at time '
                    f'{time.strftime("%Y-%m-%d %H:%M:%S UTC+0", time.gmtime(cur_time))}'
                )
            else:
                update.message.reply_text(
                    'Could not add for some reason! Check logs please.'
                )

    def close_position(self, bot, update):
        if update.message.chat.id != self.chat_id:
            update.message.reply_text('You are not authorized to use this bot.')
            return
        args = update.message.text.split(" ")
        try:
            kwargs = {}
            kwargs['user'] = args[1].lower()
            kwargs['coin'] = args[2].upper()
            if len(args) == 4:
                id = int(args[3])
                kwargs['id'] = id
            pg = PostgresConnector(ALTHEA_DB_PATH)
            positions = pg.get_positions(self.chat_id, **kwargs)
            pg.close()
            if not positions:
                update.message.reply_text(
                    'Could not find your position. '
                    'Try using /checkposition first'
                )
                return
            elif len(positions) > 1:
                reply_string = prettify_position(positions)
                update.message.reply_text(
                    'Multiple positions detected. '
                    'Please enter id as well.\n\n'
                    + reply_string
                )
                return
        except IndexError:
            update.message.reply_text(
                'Only 3 arguments are allowed. '
                'Please type /close [user] [coin] [id (optional)]'
            )
            return
        except ValueError:
            update.message.reply_text(
                'The id provided is not a number.'
            )
            return
        resp = get_market_quotes([kwargs['coin']])
        if 'error' in resp:
            update.message.reply_text('Cannot find this coin on CMC leh')
            return
        cur_price = resp['data'][kwargs['coin']]['quote']['USD']['price']
        cur_time = int(time.time())
        pg = PostgresConnector(ALTHEA_DB_PATH)
        status = pg.close_position(
            positions['id'],
            [
                cur_price,
                cur_time,
                update.message.from_user.username,
                cur_price/positions['open_price'] - 1
            ]
        )
        pg.close()
        if status:
            update.message.reply_text(
                f"Successfully closed your position for {kwargs['coin']} at ${cur_price:.2f} USD at time "
                f"{time.strftime('%Y-%m-%d %H:%M:%S UTC+0', time.gmtime(cur_time))}"
            )
        else:
            update.message.reply_text(
                'Could not close position for some reason! Check logs please.'
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
