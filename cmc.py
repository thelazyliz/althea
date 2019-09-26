import requests
import time
import logging
from cfg import CMC_API_KEY

insert_logger = logging.getLogger('stream.py')

CMC_URLS = {
    'market_quotes': 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
}

def get_market_quotes(symbol_list):
    print(','.join(symbol_list))
    headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json'}
    resp = requests.get(CMC_URLS['market_quotes'], headers=headers, params={'symbol': ','.join(symbol_list)})
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 400:
        error_msg = resp.json()['status']['error_message']
        insert_logger.info(error_msg)
        if 'Invalid value' in error_msg:
            invalid_symbols = error_msg.split(':')[1].strip().replace('"', '')
            invalid_list = invalid_symbols.split(',')
            valid_set = set(symbol_list) - set(invalid_list)
            if valid_set:
                return get_market_quotes(valid_set)
            else:
                return {'error': 'There are no valid symbols in the list provided'}
        else:
            insert_logger.debug(f'Something went wrong: {resp.status_code} - {resp.content}')
            return None
    # SLEEP IF RATE-LIMITED!
    elif resp.status_code == 429:
        time.sleep(15)
        return get_market_quotes(symbol_list)
    else:
        insert_logger.debug(resp.status_code, resp.text)