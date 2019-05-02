from flask import Flask, request, jsonify
import twitter
from cfg import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/twitter')
def twitter_route():
    return get_latest_tweets(['binanceliteau', 'binanceacademy', 'binanceresearch'])

@app.route('/twitter_get', methods=['GET'])
def twitter_get():
    user = request.args.getlist('user')
    print(user)
    return get_latest_tweets(user)

def get_latest_tweets(usernames):
    api = twitter.Api(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET)
    twitter_obj = {}
    for username in usernames:
        statuses = api.GetUserTimeline(screen_name=username, count=5)
        twitter_obj[username] = [s.text for s in statuses]
    return jsonify(twitter_obj)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
