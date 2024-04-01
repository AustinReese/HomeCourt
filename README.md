## HomeCourt

This project powers my home IOT setup. It integrates with homemade temperature sensors, Wiz smart bulbs, and an Adafruit LED sign.

The project is dependant on my local infastructure and won't function properly without it. The LED relies on an install script and python module for Raspberry Pi, the software cannot be installed in a container and no suitable mock modules exist.

You may run the frontend, api, & database using `docker-compose build && docker-compose up` to test certain functionality.
