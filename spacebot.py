#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import arrow
from time import sleep
import requests
import telegram
from telegram.error import NetworkError, Unauthorized
from emoji import emojize

update_id = None
the_bot_name = 'SqueedlyspoochBot'
token = ''

# About subscribers...
sf = 'subscriber.lst'
subscriber_list = []

# The logger
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.WARN, format=log_format)

# Start a background scheduler
scheduler = BackgroundScheduler()


def main():
    global bot
    global sf
    global the_bot_name
    global token
    global update_id

    # Load token from file if undefined
    if not token:
        if os.path.isfile('.token'):
            with open('.token', 'r') as tokenFile:
                token = tokenFile.read().replace('\n', '')

    # Load subscriber list from file
    if os.path.isfile(sf):
        logging.info("Loading subscribers...")
        with open(sf, 'r') as subscribers:
            for id in subscribers.readlines():
                id = id.replace('\n', '')
                try:
                    id = int(id)
                except:
                    continue
                if id not in subscriber_list:
                    subscriber_list.append(int(id))

    # Telegram Bot Authorization
    bot = telegram.Bot(token)

    # Get launches
    fetchLaunches()
    scheduler.add_job(fetchLaunches, 'interval', minutes=30, max_instances=1,
                      next_run_time=arrow.now().shift(seconds=5).isoformat())

    # And start the scheduler
    scheduler.start()

    # get the first pending update_id, this is so we can skip over it in case
    # we get an "Unauthorized" exception.
    try:
        update_id = bot.getUpdates()[0].update_id
    except IndexError:
        update_id = None

    while True:
        try:
            listenForUpdates(bot)
        except NetworkError:
            sleep(5)
        except Unauthorized:
            # The user has removed or blocked the bot
            update_id += 1
        except (KeyboardInterrupt, SystemExit):
            logging.info("Quitting")
            scheduler.shutdown()
            exit()


def listenForUpdates(bot):
    global sf
    global update_id

    logging.debug("Listening for updates...")

    # Request updates after the last update_id
    for update in bot.getUpdates(offset=update_id, timeout=10):
        update_id = update.update_id + 1

        try:
            chat_id = int(update.message.chat_id)
        except:
            logging.debug('Unrecongnized message:')
            logging.debug(update.message)
            continue

        if update.message:  # the bot can receive updates without messages
            if update.message.text == '/subscribe' or update.message.text == '/subscribe@' + the_bot_name:
                if chat_id not in subscriber_list:
                    logging.debug("Adding subscriber %i" % chat_id)
                    reply_message = 'Subscribed successfully!'

                    subscriber_list.append(chat_id)
                    with open(sf, 'a') as subscribers:
                        subscribers.write('\n' + str(chat_id))
                else:
                    reply_message = 'You were already subscribed'

                # Reply to the user
                try: 
                    update.message.reply_text('You are already subscribed')
                except Exception as e:
                    logging.error('Failed to reply on subscription')
                    logging.error(e)


def fetchLaunches():
    logging.info("Fetching launches!")
    r = requests.get('https://launchlibrary.net/1.2/launch?mode=verbose')

    if r.status_code == 200:
        for launch in r.json()['launches']:
            if scheduler.get_job(str(launch['id'])):
                job_exists = True
            else:
                job_exists = False

            props = {
                "when": arrow.get(launch['isonet'], "YYYYMMDDTHHmmss?"),
                "name": launch['name'],
                "urls": launch['vidURLs']
            }

            # Shifted time for notification
            when = props['when'].shift(hours=-1).datetime

            if job_exists:
                # Remove launches that became uncertain
                if launch['tbdtime'] == 1 or launch['tbddate'] == 1:
                    logging.debug("Removing job %s" % launch['id'])
                    scheduler.remove_job(str(launch['id']))
                else:
                    logging.debug("Updating job %s" % launch['id'])
                    scheduler.reschedule_job(launch['id'],
                                             trigger='date', run_date=when)
                    scheduler.modify_job(args=[props])

            # Let's add only certain launches
            elif launch['tbdtime'] == 0 and launch['tbddate'] == 0:
                logging.debug("Adding job %s" % launch['id'])
                scheduler.add_job(notifyLaunch, args=[props],
                                  id=str(launch['id']),
                                  trigger='date', run_date=when)
            else:
                logging.debug("Skipped %s because conditions weren't met."
                              % launch['id'])

    else:
        logging.warning("Error fetching launches (" + r.status_code + ")")


def notifyLaunch(props):
    global bot

    message = emojize(":rocket:", use_aliases=True) + \
        ' *' + props['name'] + '*' + '\n' \
        'A launch will happen ' + props['when'].humanize() + '!' \
        ' (at ' + props['when'].format('HH:mm') + ' UTC)' + '\n'

    if len(props['urls']) > 0:
        message += 'Where to watch it: \n'
        for url in props['urls']:
            message += '  • ' + url + '\n'
    else:
        message += 'Unfortunately there are no reported webcasts ' \
                   + emojize(':disappointed_relieved:', use_aliases=True)

    logging.info("Starting broadcast for %s" % props['name'])
    for chat_id in subscriber_list:
        logging.debug("Contacting %s" % chat_id)
        try:
            bot.send_message(chat_id, text=message,
                             parse_mode=telegram.ParseMode.MARKDOWN)
            sleep(0.04)  # Max. 30 reqs/second
        except Exception as e:
            logging.error("Horrible error ahead")
            logging.error(str(e))


if __name__ == '__main__':
    main()
