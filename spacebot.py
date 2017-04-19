#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import logging
from time import sleep
import requests
import json
import telegram
from telegram.error import NetworkError, Unauthorized

update_id = None
token = ''
sf = 'subscriber.lst'
subscriber_list = []

def main():
    global sf
    global token
    global update_id

    # Load token from file if undefined
    if not token:
        if os.path.isfile('.token'):
            with open('.token', 'r') as tokenFile:
                token = tokenFile.read().replace('\n', '')

    # Load subscriber list from file
    if os.path.isfile(sf):
        print("Loading subscribers...")
        with open(sf, 'r') as subscribers:
            for id in subscribers.readlines():
                id = id.replace('\n', '')
                try:
                    id = int(id)
                except:
                    continue
                if id not in subscriber_list:
                    subscriber_list.append(int(id))
        print(subscriber_list)

    # Telegram Bot Authorization
    bot = telegram.Bot(token)

    # get the first pending update_id, this is so we can skip over it in case
    # we get an "Unauthorized" exception.
    try:
        update_id = bot.getUpdates()[0].update_id
    except IndexError:
        update_id = None

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    while True:
        try:
            echo(bot)
        except NetworkError:
            sleep(5)
        except Unauthorized:
            # The user has removed or blocked the bot
            update_id += 1


def echo(bot):
    global sf
    global update_id
    # Request updates after the last update_id
    for update in bot.getUpdates(offset=update_id, timeout=10):
        chat_id = int(update.message.chat_id)
        update_id = update.update_id + 1

        if update.message:  # the bot can receive updates without messages
            if update.message.text == '/start':
                if chat_id not in subscriber_list:
                    print(chat_id)
                    subscriber_list.append(chat_id)
                    print(subscriber_list)
                    with open(sf, 'a') as subscribers:
                        subscribers.write('\n' + str(chat_id))
            # Reply to the message
            # update.message.reply_text(update.message.text)


if __name__ == '__main__':
    main()
