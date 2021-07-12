# Kucoin pump bot

It's a kucoin bot for earn money on pumps.

To start earn money (: you have to:
- install all dependencies: telethon, requests, python-kucoin (for example with 'pip3 install dependency')
- generate telegram and kucoin api keys and paste in config
- generate trade request header(It's working on the latest version of Mozilla Firefox, I have no idea how with other browsers):
    - Go to trade section on kucoin(you have to be logged in)
    - Choose any cryptocurrency you are able to buy
    - Open Web Developpers Tools and select network tab
    - Buy cryptocurrency and find request associated
    - Copy requests header and paste into config file(You have example request header in config)
- set expected profit
- before the pump message execute bot(python3 main.py)