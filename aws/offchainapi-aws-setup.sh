#!/bin/bash

sudo apt update
sudo apt -y upgrade
sudo apt -y autoremove

# Install tools to remember GitHub credentials.
# This is temporary, until we open source the repo. This also mean we have to
# create a special GitHub API token to upload on the AWS machines and run this
# script manually until then...
git config --global credential.helper store

# Get the repo (the testbed brancha).
git clone https://github.com/calibra/off-chain-api.git

# Install Python and all dependencies.
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.7
sudo apt install -y python3-pip
python3.7 -m pip install pip
(cd off-chain-api && pip install -r requirements.txt)

# Install nginx.
sudo apt -y install nginx
sudo unlink /etc/nginx/sites-enabled/default
sudo openssl dhparam -out /etc/nginx/dhparam.pem 4096
