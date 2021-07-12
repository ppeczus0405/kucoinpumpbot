# PUMP
COIN_USED_TO_PUMP = "USDT"  # The coin for which you will be buying pumped coin
COINS = 1500  # Amount of coins you want use for a pump
EXPECTED_PROFIT = 100  # If you want to make 3000$ from 1500$ set EXPECTED_PROFIT = 100

# KUCOIN
KUCOIN_HEADER = """POST /_api/trade/orders?c=xx HTTP/1.1
Host: trade.kucoin.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0
Accept: application/json
Accept-Language: pl,en-US;q=0.7,en;q=0.3
Accept-Encoding: gzip, deflate, br
Content-Type: multipart/form-data; boundary=---------------------------xxx
Content-Length: 760
Origin: https://trade.kucoin.com
DNT: 1
Referer: https://trade.kucoin.com/MOON-USDT
Connection: keep-alive
Cookie: xxx """
KUCOIN_KEY = "Kucoin Key"
KUCOIN_SECRET = "Kucoin Secret"
KUCOIN_PASSCODE = "Kucoin Passcode"

# TELEGRAM
TELEGRAM_ID = keys.telegram_api_id
TELEGRAM_HASH = keys.telegram_api_hash
CHAT_NAME = "Patryk Pęczak"