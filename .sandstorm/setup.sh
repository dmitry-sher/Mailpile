#!/bin/bash

# When you change this file, you must take manual action. Read this doc:
# - https://docs.sandstorm.io/en/latest/vagrant-spk/customizing/#setupsh

# i've discarded bash 'strict' mode here because of failing virtualenv
# set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git gnupg openssl python-virtualenv python-pip python-lxml python-dev libjpeg-dev python-pgpdump python-cryptography libssl-dev libffi-dev libxml2-dev libxslt-dev libz-dev wget

mkdir -p /opt/
cd /opt/
# wget https://vocaboo.com/Mailpile.tar.bz2
# tar -jxf Mailpile.tar.bz2

git clone --recursive https://github.com/mailpile/Mailpile.git
# cd Mailpile
# virtualenv -p /usr/bin/python2.7 --system-site-packages mp-virtualenv
# source mp-virtualenv/bin/activate
pip install --upgrade setuptools
pip install -r requirements-with-deps.txt
apt-get --auto-remove --yes remove python-openssl
pip install pyOpenSSL
pip install pycrypto
pip install -U cffi
pip install jinja2
pip install fasteners
./mp S sys.http_host=0.0.0.0
./mp S sys.http_port=8000