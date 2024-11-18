#!/bin/bash

python3.9 -m venv venv
source venv/bin/activate

curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
pip install -r requirements.txt
python manage.py