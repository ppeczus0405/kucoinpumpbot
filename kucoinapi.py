import requests
from enum import Enum, auto
from urllib.parse import urlencode


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()


class OrderSide(Enum):
    BUY = auto()
    SELL = auto()


class BrowserClient:
    BASE_URL_TRADE = "https://trade.kucoin.com"
    BASE_URL_MAIN = "https://www.kucoin.com"

    def __init__(self, template_request, verify=True, timeout=20):
        self.req_verify = verify
        self.req_timeout = timeout
        self.headers_post = dict()
        self.headers_get = dict()
        self.base_params = dict()
        self.prefix_boundary = str()
        self.__process_template(template_request)

    def create_market_order(self, symbol, side, size=0.0, funds=0.0):
        url = "%s/%s?%s" % (BrowserClient.BASE_URL_TRADE, "_api/trade/orders", urlencode(self.base_params))
        if size > 0.0:
            order_body = self._generate_body_trade(symbol, side, OrderType.MARKET, size=size)
        else:
            order_body = self._generate_body_trade(symbol, side, OrderType.MARKET, funds=funds)
        return self._post(url, order_body)

    def create_limit_order(self, symbol, side, size, price):
        url = "%s/%s?%s" % (BrowserClient.BASE_URL_TRADE, "_api/trade/orders", urlencode(self.base_params))
        order_body = self._generate_body_trade(symbol, side, OrderType.LIMIT, size=size, price=price)
        return self._post(url, order_body)

    def cancel_all_orders(self):
        url = "%s/%s?%s" % (BrowserClient.BASE_URL_TRADE, "_api/trade/orders/cancel", urlencode(self.base_params))
        cancel_body = self._generate_body_cancel()
        return self._post(url, cancel_body)

    def get_order(self, order_id):
        url = "%s/%s/%s" % (BrowserClient.BASE_URL_TRADE, "_api/trade-front/orders", order_id)
        return self._get(url, {})

    def get_symbol_price(self, symbol):
        params = dict()
        params['symbols'] = symbol
        url = "%s/%s" % (BrowserClient.BASE_URL_TRADE, "_api/trade-front/market/getSymbolTick")
        request = self._get(url, params)
        if int(request['code']) == 200:
            return float(request['data'][0]['lastTradedPrice'])
        return -1.0

    def get_trading_account(self):
        url = "%s/%s" % (BrowserClient.BASE_URL_MAIN, "_api/account-front/query/trade-account")
        r = self._get(url, {})
        if int(r['code']) == 200:
            return r['data']
        return []

    def get_asset_balance(self, coin):
        trading_account = self.get_trading_account()
        for currency in trading_account:
            if currency['currencyName'] == coin:
                return float(currency['availableBalance'])
        return 0.0

    def _post(self, url, body):
        raw_body = body.encode()
        self.headers_post['Content-Length'] = str(len(raw_body))
        return requests.post(url, headers=self.headers_post, data=raw_body,
                             verify=self.req_verify, timeout=self.req_timeout).json()

    def _get(self, url, params):
        params.update(self.base_params)
        url = "%s?%s" % (url, urlencode(params))
        return requests.get(url, headers=self.headers_get,
                            verify=self.req_verify, timeout=self.req_timeout).json()

    def _generate_body_trade(self, symbol, order_side, order_type, size=0.0, funds=0.0, price=0.0):
        attributes = dict()
        order_side = "buy" if order_side is OrderSide.BUY else "sell"
        if order_type is OrderType.MARKET:
            attributes['type'] = 'market'
        else:
            attributes['type'] = 'limit'
            attributes['price'] = price
        if size > 0.0:
            attributes['size'] = size
        else:
            attributes['funds'] = funds
        attributes['symbol'] = symbol
        attributes['side'] = order_side
        attributes['channel'] = 'WEB'
        attributes['postOnly'] = 'false'
        return self._generate_attributes(attributes)

    def _generate_body_cancel(self):
        attributes = dict()
        attributes['tradeType'] = 'TRADE'
        attributes['type'] = 'limit'
        return self._generate_attributes(attributes)

    def _generate_attributes(self, attributes):
        result = str()
        for attr in attributes:
            s = self.prefix_boundary + '\r\n'
            s += 'Content-Disposition: form-data; name="%s"' % attr + '\r\n\r\n'
            result += s + str(attributes[attr]) + '\r\n'
        result += self.prefix_boundary + '--\r\n'
        return result

    def __process_template(self, template):
        for line in template.split("\n"):
            if self.__line_is_necessary(line):
                if line.find("POST") > -1:
                    url = line.split(" ")[1]
                    self.__transform_parameters(url[url.find('?') + 1:])
                    continue
                if line.find("Content-Type:") > -1:
                    text = "boundary="
                    self.prefix_boundary = "--" + line[line.find(text) + len(text):]
                line_words = line.split(" ")
                header = line_words[0][:-1]
                header_content = line[len(header) + 2:]
                self.headers_post[header] = header_content
                self.headers_get[header] = header_content

    def __line_is_necessary(self, line):
        return (line.find("Referer") == -1 and
                line.find("Content-Length") == -1 and
                line.find("Origin") == -1 and
                line.find("Host") == -1)

    def __transform_parameters(self, url_part):
        start = end = 0
        while end < len(url_part):
            if url_part[end] == '&':
                key, value = self.__get_key_value(url_part[start:end])
                self.base_params[key] = value
                start = end + 1
            end += 1
        last_key, last_value = self.__get_key_value(url_part[start:end])
        self.base_params[last_key] = last_value

    def __get_key_value(self, part):
        eq_index = part.find("=")
        return part[:eq_index], part[eq_index + 1:]
