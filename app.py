from flask import Flask, request, jsonify
import twitter
from cfg import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET

app = Flask(__name__)

@app.route('/twitter', methods=['GET'])
def twitter_get():
    kwargs = request.args.copy()
    users = kwargs.poplist('user')
    full = kwargs.pop('full', None)
    resp_obj = get_latest_tweets(users, full, **kwargs.to_dict())
    resp = jsonify(resp_obj)
    if 'error' in resp_obj:
        resp.status_code = 500
    else:
        resp.status_code = 200
    return resp

def get_latest_tweets(users, full, **kwargs):
    '''
    Accepted kwargs are here: https://python-twitter.readthedocs.io/en/latest/twitter.html#twitter.api.Api.GetUserTimeline
    :param users: list of screen_name
    :param full: to view full response or not
    :return:
    '''
    api = twitter.Api(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET, tweet_mode='extended')
    api.SetCacheTimeout(0)
    twitter_obj = {}
    for k, v in kwargs.items():
        if v == '1':
            kwargs[k] = True
        elif v == '0':
            kwargs[k] = False
    try:
        for user in users:
            statuses = api.GetUserTimeline(screen_name=user, **kwargs)
            if full == '1':
                twitter_obj[user] = [s.AsDict() for s in statuses]
            else:
                twitter_obj[user] = [s.full_text for s in statuses]
    except TypeError as e:
        twitter_obj = {'error': str(e)}
    return twitter_obj


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001)
