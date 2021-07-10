import kucoin.exceptions
from telethon import TelegramClient, events
from kucoin.client import Client
from kucoin.exceptions import KucoinAPIException, MarketOrderException
from kucoin.exceptions import LimitOrderException, KucoinRequestException
from kucoinapi import BrowserClient, OrderSide
import config
import logging
import _thread

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

panic_sell_flag = True
pumped_coin = None
symbol = None
kucoin_client = None
browser_client = None
all_symbols = dict()
base_coin_amount = 0.0
telegram_client = TelegramClient("peczi", config.TELEGRAM_ID, config.TELEGRAM_HASH)


# Telegram section
async def get_last_messages(chat_id, n):
    messages_list = [message.text async for message in telegram_client.iter_messages(chat_id, n)]
    messages_list.reverse()
    return messages_list


async def get_chat_id():
    async for dialog in telegram_client.iter_dialogs():
        if dialog.name == config.CHAT_NAME:
            return dialog.id
    return None


async def is_pumped_coin_inside(message):
    global pumped_coin
    global symbol
    message_pattern = "https://trade.kucoin.com/"
    ind = message.find(message_pattern)
    if ind == -1:
        return False
    start_pos = end_pos = ind + len(message_pattern)
    while message[end_pos].isalnum():
        end_pos += 1
    pumped_coin = message[start_pos:end_pos]
    symbol = "%s-%s" % (pumped_coin, config.COIN_USED_TO_PUMP)
    return True


async def message_handler(event):
    if await is_pumped_coin_inside(event.raw_text):
        await telegram_client.disconnect()


async def telegram_initialize():
    chat_id = await get_chat_id()
    if chat_id is None:
        print("Given chat name('%s') is invalid. Please verify config file" % config.CHAT_NAME)
        return

    # Chat validation(last 3 messages)
    messages = tuple(await get_last_messages(chat_id, 3))
    c = input("3.'%s'\n2.'%s'\n1.'%s'\nThat 3 messages are last in your chat box?(y or n): " % messages)
    if c != "y":
        print("You expect another chat than '%s'. Please verify config file" % config.CHAT_NAME)
        return

    telegram_client.add_event_handler(message_handler, events.NewMessage(chats=chat_id))
    print("Waiting for a pump message...")
    await telegram_client.run_until_disconnected()


def get_pumped_coin():
    with telegram_client:
        telegram_client.loop.run_until_complete(telegram_initialize())


# Kucoin section
def get_symbol_dict():
    # Correction function for integer precisions
    def correct(x):
        if x.find(".") == -1:
            return -len(x) + 1
        return len(x) - 2

    result = {}
    for d in kucoin_client.get_symbols():
        result[d['symbol']] = (correct(d['priceIncrement']),
                               correct(d['baseIncrement']))
    return result


def kucoin_initialize():
    global kucoin_client
    global base_coin_amount
    global all_symbols
    global browser_client
    print("Initializing Kucoin client...")
    kucoin_client = Client(config.KUCOIN_KEY, config.KUCOIN_SECRET, config.KUCOIN_PASSCODE,
                           requests_params={"verify": True, "timeout": 20})
    browser_client = BrowserClient(config.KUCOIN_HEADER, verify=True, timeout=4)

    try:
        [a for a in kucoin_client.get_accounts() if a['type'] == 'trade']
    except KucoinAPIException:
        print("Cannot initialize properly client. Please check your API keys")
        return False

    trading_account = browser_client.get_trading_account()
    if len(trading_account) == 0:
        print("Cannot initialize properly browser client. Please try generate new HEADER")
        return False

    print("Trading assets available for trade(not blocked):")
    for currency in trading_account:
        if currency['currencyName'] == config.COIN_USED_TO_PUMP:
            base_coin_amount = float(currency['availableBalance'])
        if float(currency['availableBalance']) > 0:
            print("%s: %f" % (currency['currencyName'], float(currency['availableBalance'])))

    if base_coin_amount < config.COINS:
        print("You don't have sufficient amount of coin on trading account.")
        print("Check config file or transfer more funds on trading account.")
        return False

    all_symbols = get_symbol_dict()
    test_limit = browser_client.create_limit_order("BTC-USDT", OrderSide.BUY, 0.001, 10000)
    if int(test_limit['code']) == 200:
        print("Created test limit buy on pair BTC-USDT. Check if it's true and cancel this order.")
    else:
        print("Cannot create test-limit order. %s" % (test_limit['msg']))
    response = input("Everything is ok? (y or n): ")

    if response != 'y':
        print("Cannot initialize properly browser client. Please try generate new HEADER")
        return False

    print("Successfully initialize Kucoin client")
    return True


# Pump section
def include_precision(amount, precision):
    r = 10 ** (-precision)
    to_truncate = str(int(amount / r) * r)
    dot_pos = to_truncate.find('.')
    if dot_pos == -1:
        return float(to_truncate)
    return float(to_truncate[:dot_pos + precision + 1])


def last_price():
    return float(kucoin_client.get_ticker(symbol)['price'])


def get_panic_sell_start_signal():
    global panic_sell_flag
    input("Press ENTER to start panic selling coins.\n")
    panic_sell_flag = False


def panic_sell_signal_manually(profit):
    want_to_sell = False
    while not want_to_sell:
        inp = input("Actual profit: %f%%. Confirm 's' to sell: " % profit(browser_client.get_symbol_price(symbol)))
        if inp == 's':
            want_to_sell = True


def get_bought_sold():
    bought = 1
    sold = 2
    trading_account = browser_client.get_trading_account()
    for currency in trading_account:
        if currency['currencyName'] == pumped_coin:
            bought = float(currency['availableBalance'])
        if currency['currencyName'] == config.COIN_USED_TO_PUMP:
            sold = base_coin_amount - float(currency['availableBalance'])
    return bought, sold


def pump():
    market_buy = browser_client.create_market_order(symbol, OrderSide.BUY, funds=config.COINS)
    if int(market_buy['code']) != 200:
        print("Failed during trying market buy. Error message: %s" % market_buy['msg'])
        return False

    price_precision, pumped_coin_precision = all_symbols[symbol]
    bought_coins, sold_coins = get_bought_sold()
    bought_coins = include_precision(bought_coins, pumped_coin_precision)
    print("Successfully bought %f %s for %f %s" % (bought_coins, pumped_coin,
                                                   sold_coins, config.COIN_USED_TO_PUMP))

    # Limit sell coins
    price = sold_coins / bought_coins
    limit_price = include_precision(price * (1 + config.EXPECTED_PROFIT / 100.0),
                                    price_precision)
    print("I'm trying to place limit sell order")
    limit_sell = browser_client.create_limit_order(symbol, OrderSide.SELL, bought_coins, limit_price)
    if int(limit_sell['code']) == 200:
        print("Successfully placed limit sell with %f%% profit" % config.EXPECTED_PROFIT)
    else:
        print("Failed during trying place limit sell. Error message: %s" % limit_sell['msg'])

    def profit(x):
        return (x - price) * 100 / price

    # Multithreading for upgrade panic sell
    try:
        _thread.start_new_thread(get_panic_sell_start_signal, tuple())
        while panic_sell_flag:
            print("Actual profit: %f%%." % profit(browser_client.get_symbol_price(symbol)))
    except Exception:
        print("Unable to start new thread.")
        panic_sell_signal_manually(profit)

    # Cancel all orders on pair
    print("I'm trying to cancel all open orders on pair %s" % symbol)
    cancel_orders = browser_client.cancel_all_orders()
    if int(cancel_orders['code']) == 200:
        print("All orders on pair %s cancelled" % symbol)
    else:
        print("Cannot cancel orders on pair %s. Error message %s" % (symbol, cancel_orders['msg']))

    # Market sell coins
    print("I'm trying to sell remaining amount of coins")
    market_sell_amount = include_precision(browser_client.get_asset_balance(pumped_coin),
                                           pumped_coin_precision)
    market_sell = browser_client.create_market_order(symbol, OrderSide.SELL, size=market_sell_amount)
    if int(market_sell['code']) == 200:
        print("Successfully sold remaining coins")
    else:
        print("Failed during trying market sell. Error message: %s" % market_sell['msg'])

    profit = (browser_client.get_asset_balance(config.COIN_USED_TO_PUMP) - base_coin_amount) * 100 / sold_coins
    print("Successfully ended pump with %f%% profit" % profit)
    return True


if __name__ == "__main__":
    if kucoin_initialize():
        get_pumped_coin()
        pump()
