# MEC Meter Emulator
This is a Home Assistant Custom Integration that provides several Template Values to an MQTT Broker, while emulating the structure of a MECMeter connected to a Fronius Inverter.

To install: copy the mecmeter_emulator folder to your custom_components folder.

Add the following Configuration values to your configuration.yaml
```
mqtt_template_publisher:
  broker: host.of.the.mqtt.broker
  port: 8883  # Uses TLS per default
  username: username
  password: randompassword
  topic: topicprefix
  client_id: clientid
  templates:
    grid: "{{ states('sensor.grid_meter_power') | default('unavailable') }}"
    # Power at the Grid-Meter - Positive = consumption, negative = grid feed in
    ld: "{{ (0-(states('sensor.total_home_power')| float)) | default('unavailable') }}"
    # Power consumption of the house: Negative = consumption, positive = invalid
    pv: "{{ states('sensor.solarpower') | default('unavailable') }}"
    # Current PV generation power: Positive = production, negative = invalid
    akk: "{{ states('sensor.bat_power') | default('unavailable') }}"
    # current battery input / output power: positive: battery discharging, negative: battery charging
    soc: "{{ states('sensor.bat_soc') | default('unavailable') }}" 
    # SOC of the Home Battery, 0-100
  update_interval: 30
```
The five values are all optional, depending on the inverter hardware and available values you have. Leave out any values you cannot provide.
