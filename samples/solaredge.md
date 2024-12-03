# Solaredge sample configuration

This is a Home Assistant Custom Integration that provides several Template Values to an MQTT Broker, while emulating the structure of a MECMeter connected to a Fronius Inverter.

Disclaimer: This is an inofficial hobby-project and in no way affiliated with MEC or Solaredge.

## Installation

- Install [SolarEdge Modbus Multi](https://github.com/WillCodeForCats/solaredge-modbus-multi) via [HACS](https://www.hacs.xyz/)
- Install MEC Meter Emulator [README.md](../README.md)
- Add the following Configuration values to your configuration.yaml
  
```yaml
mec_meter_emulator:
  broker: packet.verbund.at
  port: 8883  # Uses TLS per default
  username: username
  password: randompassword
  topic: topicprefix
  client_id: clientid
  update_interval: 30
  templates:
    # Power at the Grid-Meter - Positive = consumption, negative = grid feed in
    grid: >
      {{
        (states('sensor.solaredge_i1_m1_ac_power') | float(default=0) * -1 )
      }}
    # Power consumption of the house: Negative = consumption, positive = invalid
    ld: >
      {{
        (states('sensor.solaredge_i1_m1_ac_power') | float(default=0)) +
        (states('sensor.solaredge_i1_ac_power') | float(default=0) * -1 )
      }}
    # Current PV generation power: Positive = production, negative = invalid
    pv: >
      {{
        (states('sensor.solaredge_i1_dc_power') | float(default=0)) +
        (states('sensor.solaredge_i1_b1_dc_power') | float(default=0))
      }}
    # current battery input / output power: positive: battery discharging, negative: battery charging
    akk: >
      {{
        (states('sensor.solaredge_i1_b1_dc_power') | float(default=0) * -1 )
      }}
    # SOC of the Home Battery, 0-100
    soc: >
      {{
        states('sensor.solaredge_i1_b1_state_of_energy') | default('unavailable')
      }}
```

The five values are all optional, depending on the inverter hardware and available values you have. Leave out any values you cannot provide.

## Remarks

The above sample assumes that besides the inverter an energy meter, eighter separate or bundles with a backup interface is installed, it's power value is accessed with `(states('sensor.solaredge_i1_m1_ac_power')`.

In case no battery is installed, simple remove all `(states('sensor.solaredge_i1_b1_dc_power')` references.
