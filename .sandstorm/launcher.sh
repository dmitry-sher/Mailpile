#!/bin/bash

# set -euo pipefail

cd /opt/Mailpile
# source mp-virtualenv/bin/activate
./mp S sys.http_host=0.0.0.0
./mp S sys.http_port=8000
./mp
# exit 0