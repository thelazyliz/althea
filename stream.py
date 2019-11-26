import tweepy
from tweepy.error import TweepError
import logging
import time
from datetime import datetime
import threading
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.ext import DispatcherHandlerStop
from urllib3.exceptions import IncompleteRead, ProtocolError
import telegram
import sys
from cfg import ALTHEA_TOKEN, TG_CHATS
from cfg import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
insert_logger = logging.getLogger('stream.py')
fh = logging.FileHandler(f'./logs/{datetime.now().strftime("%Y-%m-%d")}.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
fh.setFormatter(formatter)
insert_logger.addHandler(fh)


class MyStreamListener(tweepy.StreamListener):

    def __init__(self, chat_id, following_names):
        tweepy.StreamListener.__init__(self)
        self.bot = telegram.Bot(token=ALTHEA_TOKEN)
        self.chat_id = chat_id
        self.following_names = following_names

    def send_telegram_message(self, status):
        link = f'https://www.twitter.com/{status.user.screen_name}' \
               f'/status/{status.id_str}'
        if self.post_criteria(status):
            insert_logger.info(f'PASSED: {status.text}\nLINK: {link}')
            if status.truncated:
                tweet = status.extended_tweet['full_text']
            else:
                tweet = status.text
            status_str = f"<b>Author</b>: {status.author.screen_name}\n" \
                         f"<b>Tweet</b>: {tweet}\n" \
                         f"<b>Link</b>: {link}"
            try:
                self.bot.send_message(
                    chat_id=self.chat_id, text=status_str,
                    parse_mode=telegram.ParseMode.HTML
                    )
            except Exception as e:
                insert_logger.exception(str(e))
        else:
            insert_logger.info(f'SKIPPED: {status.text}\nLINK: {link}')

    def post_criteria(self, status):
        if hasattr(status, 'retweeted_status'):
            return False
        elif status.in_reply_to_screen_name and \
                status.in_reply_to_screen_name != status.author.screen_name:
            return False
        elif status.author.screen_name.lower() not in self.following_names:
            return False
        else:
            return True

    def on_status(self, status):
        threading.Thread(
            target=self.send_telegram_message, args=(status,)
        ).start()

    def on_exception(self, exception):
        insert_logger.exception(exception)
        insert_logger.error('caught exception in thread')
        return True
        # sys.exit()

    def on_error(self, status_code):
        insert_logger.warning(status_code)
        return True


class Twitter2Tg:

    def __init__(self, chat_name, master_name=None):
        insert_logger.info(f'starting new process for {chat_name}')
        self.chat_id = str(TG_CHATS[chat_name])
        if master_name is None:
            self.bot_master_id = str(TG_CHATS[chat_name])
        else:
            self.bot_master_id = str(TG_CHATS[master_name])
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
                following_ids = [
                    user.id_str for user in
                    self.api.lookup_users(screen_names=following_names)
                ]
                self.following = dict(zip(following_names, following_ids))
        except Exception as e:
            insert_logger.exception(str(e))

    def setup_twitter(self):
        try:
            insert_logger.info(list(self.following.keys()))
            my_stream_listener = MyStreamListener(
                self.chat_id, list(self.following.keys())
            )
            self.my_stream = tweepy.Stream(
                auth=self.api.auth, listener=my_stream_listener,
                tweet_mode='extended',
                exclude_replies=True, include_rts=False
            )
            self.my_stream.filter(
                follow=self.following.values(),
                is_async=True,
                stall_warnings=True
            )
        except Exception as twitter_e:
            insert_logger.exception(str(twitter_e))
            insert_logger.warning('Caught exception. Reconnecting...')
            self.my_stream.disconnect()
            self.setup_twitter()

    def setup_tg(self):
        try:
            updater = Updater(
                token=ALTHEA_TOKEN,
                request_kwargs={'read_timeout': 10, 'connect_timeout': 10}
            )
            dispatcher = updater.dispatcher
            tg_follow_handler = CommandHandler('follow', self.follow)
            tg_unfollow_handler = CommandHandler('unfollow', self.unfollow)
            tg_check_follow_handler = CommandHandler(
                'checkfollow', self.check_follow
            )
            dispatcher.add_handler(
                MessageHandler(Filters.all, self.check_allowed), -1
            )
            dispatcher.add_handler(tg_follow_handler)
            dispatcher.add_handler(tg_unfollow_handler)
            dispatcher.add_handler(tg_check_follow_handler)
            dispatcher.add_error_handler(self.error)
            updater.start_polling()
            updater.idle()
        except Exception as e:
            insert_logger.exception(str(e))

    def error(self, update, context):
        insert_logger.exception(
            f'Update {update} caused error {context.error}'
        )

    def check_allowed(self, bot, update):
        if str(update.message.chat.id) != self.bot_master_id:
            raise DispatcherHandlerStop

    def follow(self, bot, update):
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
            update.message.reply_text(
                f'{args} has been added to your following.'
            )
        except TweepError as e:
            if '17' in str(e):
                update.message.reply_text(
                    'Unable to find the username specified.'
                )
        except Exception as e:
            insert_logger.exception(str(e))

    def unfollow(self, bot, update):
        try:
            args = update.message.text.split(" ")[1]
        except IndexError:
            update.message.reply_text(
                'Please type /unfollow [twitter username]'
            )
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
            update.message.reply_text(
                f'You are following: {", ".join(self.following.keys())}'
            )
        except Exception as e:
            insert_logger.exception(str(e))


if __name__ == '__main__':
    from helpers import choose_option
    try:
        choice_send = choose_option(
            list(TG_CHATS.keys()),
            title='Choose a telegram chat to send to.'
        )
        choice_ctrl = choose_option(
            list(TG_CHATS.keys()),
            title='Choose a telegram chat for bot control.'
        )
        t2tg = Twitter2Tg(choice_send, choice_ctrl)
    except Exception as e:
        insert_logger.exception(str(e))
