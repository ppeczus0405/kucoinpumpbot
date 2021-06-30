import kucoin.exceptions
from telethon import TelegramClient, events
from kucoin.client import Client
from kucoin.exceptions import KucoinAPIException, MarketOrderException
from kucoin.exceptions import LimitOrderException, KucoinRequestException
import config
import logging
import _thread

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

panic_sell_flag = True
pumped_coin = None
symbol = None
kucoin_client = None
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
    message_pattern = "Coin is:"
    ind = message.find(message_pattern)
    if ind == -1:
        return False
    start_pos = ind + len(message_pattern)
    while not message[start_pos].isalnum():
        start_pos += 1
    end_pos = start_pos
    while end_pos < len(message) and message[end_pos].isalnum():
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
def kucoin_initialize():
    global kucoin_client
    global base_coin_amount

    print("Initializing Kucoin client...")
    kucoin_client = Client(config.KUCOIN_KEY, config.KUCOIN_SECRET, config.KUCOIN_PASSCODE,
                           requests_params={"verify": True, "timeout": 20})

    try:
        accounts = [a for a in kucoin_client.get_accounts() if a['type'] == 'trade']
    except KucoinAPIException:
        print("Cannot initialize properly client. Please check your API keys")
        return False

    print("Trading assets available for trade(not blocked):")
    for a in accounts:
        if a['currency'] == config.COIN_USED_TO_PUMP:
            base_coin_amount = float(a['available'])
        print("%s: %f" % (a['currency'], float(a['available'])))

    if base_coin_amount < config.COINS:
        print("You don't have sufficient amount of coin on trading account.")
        print("Check config file or transfer more funds on trading account.")
        return False

    print("Successfully initialize Kucoin client")
    return True


# Pump section
def last_price():
    return float(kucoin_client.get_ticker(symbol)['price'])


def get_panic_sell_start_signal():
    global panic_sell_flag
    input("Press ENTER to start panic selling coins.\n")
    panic_sell_flag = False


def panic_sell_signal_manually(profit):
    want_to_sell = False
    while not want_to_sell:
        inp = input("Actual profit: %f%%. Confirm 's' to sell: " % profit(last_price()))
        if inp == 's':
            want_to_sell = True


def get_coin_amount(coin):
    for a in kucoin_client.get_accounts():
        if a['currency'] == coin and a['type'] == 'trade':
            return float(a['available'])
    return 0.0


def pump():
    print("Pumped coin: %s" % pumped_coin)
    print("Let's pump!")

    # Market buy coins
    print("Trying to market buy %s" % pumped_coin)
    try:
        market_buy = kucoin_client.create_market_order(symbol, Client.SIDE_BUY, funds=config.COINS)
    except (KucoinAPIException, MarketOrderException, KucoinRequestException) as error:
        print("Failed during trying market buy. Error message: %s" % error.message)
        return False
    market_order = kucoin_client.get_order(market_buy['orderId'])
    bought_coins = float(market_order['dealSize'])
    sold_coins = float(market_order['dealFunds'])
    print("Successfully bought %f %s for %f %s" % (bought_coins, pumped_coin,
                                                   sold_coins, config.COIN_USED_TO_PUMP))

    # Limit sell coins
    price = sold_coins / bought_coins
    limit_price = price * (1 + config.EXPECTED_PROFIT / 100.0)
    print(limit_price)
    print("I'm trying to place limit sell order")
    try:
        kucoin_client.create_limit_order(symbol, Client.SIDE_SELL, limit_price, bought_coins)
        print("Successfully placed limit sell with %f%% profit" % config.EXPECTED_PROFIT)
    except (KucoinAPIException, LimitOrderException, KucoinRequestException) as error:
        print("Failed during trying place limit sell. Error message: %s" % error.message)

    def profit(x):
        return (x - price) * 100 / price

    # Multithreading for upgrade panic sell
    try:
        _thread.start_new_thread(get_panic_sell_start_signal, tuple())
        while panic_sell_flag:
            print("Actual profit: %f%%." % profit(last_price()))
    except Exception:
        print("Unable to start new thread.")
        panic_sell_signal_manually(profit)

    # Cancel all orders on pair
    print("I'm trying to cancel all open orders on pair %s" % symbol)
    try:
        kucoin_client.cancel_all_orders(symbol)
        print("All orders on pair %s cancelled" % symbol)
    except (KucoinRequestException, KucoinAPIException) as error:
        print("Cannot cancel orders on pair %s. Error message %s" % (symbol, error.message))

    # Market sell coins
    print("I'm trying to sell remaining amount of coins")
    try:
        kucoin_client.create_market_order(symbol, Client.SIDE_SELL, get_coin_amount(pumped_coin) * 0.99)
        print("Successfully sold remaining coins")
    except (MarketOrderException, KucoinRequestException, KucoinAPIException) as error:
        print("Failed during trying market sell. Error message: %s" % error.message)

    profit_in_percent = (get_coin_amount(config.COIN_USED_TO_PUMP) - base_coin_amount) * 100 / sold_coins
    return "Successfully ended pump with %f%% profit" % profit_in_percent


if __name__ == "__main__":
    if kucoin_initialize():
        get_pumped_coin()
        if pumped_coin is not None:
            pump_results = pump()
            print(pump_results)
