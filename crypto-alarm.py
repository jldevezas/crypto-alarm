#!/usr/bin/env python
#
# crypto-alarm.py
# José Devezas <joseluisdevezas@gmail.com>
# 2021-01-07

import argparse
import logging
import math
import os
import signal
import sys
from configparser import ConfigParser
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from daemonize import Daemonize
from playsound import playsound
from systemd.journal import JournalHandler
from termcolor import cprint

log = logging.getLogger('crypto-alarm')
log.addHandler(JournalHandler())
log.setLevel(logging.INFO)

PID_FILE = '/tmp/crypto-alarm.pid'
CONFIG_FILE = '~/.config/crypto-alarm.conf'


class ConfigException(Exception):
    pass


def clog(msg, color='white'):
    cprint(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, {msg}", color=color)
    log.info(msg)


def csep(color='white'):
    cprint(f"---", color=color)


def build_get_price(args):
    from pycoingecko import CoinGeckoAPI
    cg = CoinGeckoAPI()
    cg_lst = cg.get_coins_list()

    def get_price_from_coingecko():
        symbols = set(map(str.lower, args.coins.split(',')))

        coin_ids = {}
        for coin in cg_lst:
            if coin['symbol'] in symbols:
                coin_ids[coin['id']] = coin['symbol'].upper()

        prices = cg.get_price(ids=','.join(coin_ids.keys()), vs_currencies='usd')
        return {coin_ids[k]: v['usd'] for k, v in prices.items()}

    def get_price_from_binance():
        from binance.client import Client

        config = ConfigParser()
        config.read_file(open(args.config))

        if 'binance' not in config.sections():
            raise ConfigException("Configuration file does not contain a '[binance]' section")

        if 'api_key' not in config['binance'] or config['binance']['api_key'].strip() == "":
            raise ConfigException("Binance configuration section does not contain an 'api_key'")

        if 'api_secret' not in config['binance'] or config['binance']['api_secret'].strip() == "":
            raise ConfigException("Binance configuration section does not contain an 'api_secret'")

        client = Client(config['binance']['api_key'], config['binance']['api_secret'])

        coin_prices = {}
        for coin in args.coins.split(','):
            try:
                coin_prices[coin] = float(client.get_symbol_ticker(symbol=f"{coin}USDT")['price'])
            except Exception as e:
                clog(f"ERROR: {coin} is not supported by the {args.api} API", color="red")
                raise e

        return coin_prices

    if args.api == 'binance':
        return get_price_from_binance
    else:
        return get_price_from_coingecko


def build_track_coin(args):
    get_price = build_get_price(args)

    last_price = {}
    for coin in args.coins.split(','):
        price = get_price()
        last_price[coin] = price[coin]
        clog(f"{coin} price @ {last_price[coin]} USD")

    def track_coin():
        price = get_price()
        csep()

        for coin, step in zip(args.coins.split(','), map(float, args.steps.split(','))):
            if price[coin] >= math.ceil(last_price[coin] / step) * step:
                clog(f"{coin} price target increased to {price[coin]} USD", color='green')
                playsound(args.up_alert)

            elif price[coin] <= math.floor(last_price[coin] / step) * step:
                clog(f"{coin} price target decreased to {price[coin]} USD", color='red')
                playsound(args.down_alert)

            last_price[coin] = price[coin]
            clog(f"{coin} price @ {last_price[coin]} USD")

    return track_coin


def build_service(args):
    def run_service():
        scheduler = BlockingScheduler(timezone='UTC')
        scheduler.add_job(build_track_coin(args), 'interval', seconds=args.interval)
        scheduler.start()

    return run_service


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="JLD Crypto Alarm")

    parser.add_argument(
        '-d', '--daemon',
        action='store_true',
        default=False,
        help="daemonize as a background service")

    parser.add_argument(
        '-a', '--api',
        choices=['coingecko', 'binance'],
        default='coingecko',
        help="API name (coingecko, binance)")

    parser.add_argument(
        '--config',
        type=str,
        default=os.path.join(os.path.expanduser("~"), ".config/crypto-alarm.conf"),
        help="configuration file containing API keys and secrets (default: ~/.config/crypto-alarm.conf")

    parser.add_argument(
        '-c', '--coins',
        type=str,
        required=False,
        help="symbol of the coin to track (e.g., BTC, ETH, etc.)")

    parser.add_argument(
        '-s', '--steps',
        type=str,
        required=False,
        help=("comma-separated target price steps for alarm to sound"
              "(e.g., 1000 will ring every 1000 USD, like 12000 USD)"))

    parser.add_argument(
        '-i', '--interval',
        type=int,
        required=False,
        default=300,
        help="price check interval in seconds (default: 5 min, according to CoinGecko API updates)")

    parser.add_argument(
        '-k', '--kill',
        action='store_true',
        default=False,
        help="kill daemon background service")

    parser.add_argument(
        '-ua', '--up-alert',
        type=str,
        default=os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'audio/Cha_Ching_Register-Muska666-173262285.wav'),
        help="alert audio file path for price increase")

    parser.add_argument(
        '-da', '--down-alert',
        type=str,
        default=os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'audio/VOXScrm_Wilhelm scream (ID 0477)_BSB.wav'),
        help="alert audio file path for price decrease")

    parser.add_argument(
        '-t', '--test',
        action='store_true',
        default=False,
        help="test alert sound")

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.test:
        print(f"Playing price increase alert: {args.up_alert}")
        playsound(args.up_alert)
        print(f"Playing price decrease alert: {args.down_alert}")
        playsound(args.down_alert)
        sys.exit(0)

    if args.kill:
        print("Killing daemon")
        os.kill(int(open(PID_FILE).read()), signal.SIGTERM)

    if args.coins and args.steps:
        try:
            coin_info = [f"{coin}[{step}]" for coin, step in zip(args.coins.split(','), args.steps.split(','))]
            print(f"Running sound alarm monitoring for {', '.join(coin_info)}")

            if args.daemon:
                daemon = Daemonize(app="crypto-alarm", pid=PID_FILE, action=build_service(args))
                daemon.start()
                print("Launched as daemon")
            else:
                service = build_service(args)
                service()

        except KeyboardInterrupt:
            print("Interrupted by user, exiting...")
