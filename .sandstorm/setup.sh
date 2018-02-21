#!/bin/bash

# When you change this file, you must take manual action. Read this doc:
# - https://docs.sandstorm.io/en/latest/vagrant-spk/customizing/#setupsh

# i've discarded bash 'strict' mode here because of failing virtualenv
# set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python2.7 git gnupg openssl python-virtualenv python-pip python-lxml python-dev libjpeg-dev python-pgpdump python-cryptography libssl-dev libffi-dev 

mkdir -p /opt/
cd /opt/
git clone --recursive https://github.com/mailpile/Mailpile.git
cd Mailpile
virtualenv -p /usr/bin/python2.7 --system-site-packages mp-virtualenv
source mp-virtualenv/bin/activate
pip install --upgrade setuptools
pip install -r requirements.txt