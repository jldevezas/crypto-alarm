# crypto-alarm

A cross-platform python daemon to configure crypto sound alarms.

![crypto-alarm screenshot](screenshots/crypto-alarm.png)

-- Powered by CoinGecko API

## Installation

Basic requirements are python 3.x and pip.

```shell
pip install -r requirements.txt
```

## systemd (optional)

Ensure the python binary in `crypto-alarm/etc/systemd/system/crypto-alarm.service` is correct, and then:

```shell
cd crypto-alarm/
sudo cp -i etc/systemd/system/crypto-alarm.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable crypto-alarm # optional
sudo systemctl start crypto-alarm
```

## Examples

Track price for bitcoin in the command line:

```shell
./crypto-alarm.py -c bitcoin -s 1000
```

Launch as a daemon to get audio alerts in the background:

```shell
./crypto-alarm.py -c bitcoin,ethereum -s 1000,100 -d
```

Kill the running daemon:

```shell
./crypto-alarm.py -k
```

Test the alarm sounds:

```shell
./crypto-alarm.py -t
```