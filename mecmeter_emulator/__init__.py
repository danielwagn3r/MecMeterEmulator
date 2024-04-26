import json
import ssl
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, event
from datetime import timedelta
from datetime import datetime
import time
import pytz
import paho.mqtt.client as mqtt
DOMAIN = 'mqtt_template_publisher'
# Define schema for configuration validation
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
    vol.Required('broker'): cv.string,
    vol.Required('port'): cv.port,
    vol.Required('username'): cv.string,
    vol.Required('password'): cv.string,
    vol.Required('topic'): cv.string,
    vol.Required('client_id'): cv.string,
    vol.Optional('templates'): {
        vol.Optional('soc'): cv.template,
        vol.Optional('akk'): cv.template,
        vol.Optional('grid'): cv.template,
        vol.Optional('ld'): cv.template,
        vol.Optional('pv'): cv.template
    },
    vol.Required('update_interval', default=60): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass: HomeAssistant, config: dict):
    conf = config['mqtt_template_publisher']
    broker = conf['broker']
    port = conf['port']
    username = conf['username']
    password = conf['password']
    topic = conf['topic']
    client_id = conf.get('client_id')
    templates = conf.get('templates', {})
    inv_number = 1
    update_interval = conf['update_interval']


    # Setup MQTT client
    client = mqtt.Client(client_id=client_id)
    client.username_pw_set(username, password)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.connect(broker, port)
    client.loop_start()
    def update_data(event_time):
        data = {
            "timestampDevice": int(time.time() * 1000),
            "qos": "good",
            "payload": {
                "inv": {inv_number: {}},
                "sit": {},
                "ts": datetime.now(pytz.UTC).isoformat(timespec='seconds')
            }
        }

        # Process each template and only add if available and valid
        for key, value in templates.items():
            rendered = value.async_render()
            if rendered not in ['unknown', 'unavailable', None]:
                if key == 'soc':
                    data['payload']['inv'][inv_number][key] = float(rendered)
                else:
                    data['payload']['sit'][key] = float(rendered)

        # Publish if there is valid data in the payload
        if data['payload']['inv'][inv_number] or data['payload']['sit']:
            json_data = json.dumps(data)
            client.publish(topic+'/solar-api', json_data)

    # Schedule the periodic update
    event.track_time_interval(hass, update_data, timedelta(seconds=update_interval))
    return True
