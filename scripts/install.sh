#!/bin/bash

echo "Installing Kingdom v40.1"

python -m venv venv

source venv/bin/activate

pip install -r requirements.txt

cd frontend

npm install

echo "Installation Complete"
