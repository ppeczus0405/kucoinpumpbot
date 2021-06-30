from telethon import TelegramClient, events
from kucoin.client import Client
from kucoin.exceptions import KucoinAPIException
import config
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

pumped_coin = None
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
    message_pattern = "Coin is:"
    ind = message.find(message_pattern)
    if ind == -1:
        return False
    start_pos = ind + len(message_pattern)
    while not message[start_pos].isalnum():
        start_pos += 1
    end_pos = start_pos
    while end_pos < len(message) and end_pos.isalnum():
        end_pos += 1
    pumped_coin = message[start_pos:end_pos]
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


if __name__ == "__main__":
    if kucoin_initialize():
        print("Successfully initialize kucoin client")
        get_pumped_coin()
        if pumped_coin is not None:
            print(pumped_coin)
