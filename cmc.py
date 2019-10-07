import requests
import time
import logging
from cfg import CMC_API_KEY

insert_logger = logging.getLogger('stream.py')

CMC_URLS = {
    'market_quotes':
        'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
}


def get_market_quotes(symbol_list):
    '''
    :param symbol_list: a list of tickers/symbols, eg ['BTC','ETH']
    :return: dict with either error response or correct response from cmc
    '''
    try:
        headers = {
            'X-CMC_PRO_API_KEY': CMC_API_KEY,
            'Accept': 'application/json'
        }
        resp = requests.get(
            CMC_URLS['market_quotes'],
            headers=headers,
            params={'symbol': ','.join(symbol_list)}
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            error_msg = resp.json()['status']['error_message']
            insert_logger.info(error_msg)
            # this applies to list with some invalid and some valid values
            # if ['BTC' , 'DSAJDS'] is sent, CMC will return error saying
            # that DSAJDS is invalid
            # we then strip all the invalid symbols from original list
            # and send to cmc to get a 200 response for the valid symbols
            if 'Invalid value' in error_msg:
                invalid_symbols = (
                    error_msg
                    .split(':')[1]
                    .strip()
                    .replace('"', '')
                )
                invalid_list = invalid_symbols.split(',')
                valid_set = set(symbol_list) - set(invalid_list)
                if valid_set:
                    return get_market_quotes(valid_set)
                else:
                    return {
                        'error':
                            'There are no valid symbols in the list provided'
                    }
            else:
                insert_logger.debug(resp.status_code, resp.text)
                return {'error': f'{resp.status_code} {resp.text}'}
        # SLEEP IF RATE-LIMITED!
        elif resp.status_code == 429:
            time.sleep(15)
            return get_market_quotes(symbol_list)
        else:
            insert_logger.debug(resp.status_code, resp.text)
            return {'error': f'{resp.status_code} {resp.text}'}
    except Exception as e:
        insert_logger.exception(str(e))
