#!/bin/bash
echo "Rebuilding Angular app..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 20
cd /home/winner/HomeCourt/pi-ui && npx ng build

echo "Restarting services..."
sudo systemctl restart pi-led.service pi-ui.service pi-api.service wiz-poke.service

echo "Done. Service status:"
sudo systemctl is-active pi-led.service pi-ui.service pi-api.service wiz-poke.service
