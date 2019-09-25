import tweepy
from tweepy.error import TweepError
import json
import logging, time
import threading
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram
from cfg import *

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

    def send_telegram_message(self, message):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode=telegram.ParseMode.HTML)
        except Exception as e:
            insert_logger.exception(str(e))

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
            threading.Thread(target=self.send_telegram_message, args=(status_str,)).start()
        else:
            insert_logger.info(f'SKIPPED: {status.text}\nLINK: {link}')


class Twitter2Tg:

    def __init__(self, chat_name):
        insert_logger.info(f'starting new process for {chat_name}')
        self.chat_id = TG_CHATS[chat_name]
        self.following = {}
        self.my_stream = None
        self.filename = 'following.txt'
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
            self.my_stream.filter(follow=self.following.values(), is_async=True)
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
            dispatcher.add_handler(tg_follow_handler)
            dispatcher.add_handler(tg_unfollow_handler)
            dispatcher.add_handler(tg_check_follow_handler)
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