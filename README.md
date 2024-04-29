# MEC Meter Emulator
This is a Home Assistant Custom Integration that provides several Template Values to an MQTT Broker, while emulating the structure of a MECMeter connected to a Fronius Inverter.

Disclaimer: This is an inofficial hobby-project and in no way affiliated with MEC or Fronius. 

To install: copy the mecmeter_emulator folder to your custom_components folder.

Add the following Configuration values to your configuration.yaml
```
mec_meter_emulator:
  broker: host.of.the.mqtt.broker
  port: 8883  # Uses TLS per default
  username: username
  password: randompassword
  topic: topicprefix
  client_id: clientid
  templates:
    # Power at the Grid-Meter - Positive = consumption, negative = grid feed in
    grid: "{{ states('sensor.grid_meter_power') | default('unavailable') }}"
    # Power consumption of the house: Negative = consumption, positive = invalid
    ld: "{{ (0-(states('sensor.total_home_power')| float)) | default('unavailable') }}"
    # Current PV generation power: Positive = production, negative = invalid
    pv: "{{ states('sensor.solarpower') | default('unavailable') }}"
    # current battery input / output power: positive: battery discharging, negative: battery charging
    akk: "{{ states('sensor.bat_power') | default('unavailable') }}"
    # SOC of the Home Battery, 0-100
    soc: "{{ states('sensor.bat_soc') | default('unavailable') }}" 
  update_interval: 30
```
The five values are all optional, depending on the inverter hardware and available values you have. Leave out any values you cannot provide.
