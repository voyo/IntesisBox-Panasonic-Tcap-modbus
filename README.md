# IntesisBox-Panasonic-Tcap-modbus
IntesisBox Panasonic-Tcap over modbus, Domoticz plugin
Author: Wojtek Sawasciuk  <voyo@no-ip.pl>


## Requirements:
1. python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
   ```
   pi@raspberrypi:~$ sudo pip3 install minimalmodbus
   ```
2. Communication module Modbus USB to RS485 converter module
3. python module pyModbusTCP
4. 'something' what can act as proxy for Modbus TCP to Modbus RTU (RS-232/485) connectivity. Hardware or software solution.
   I'm using open-source mbusd (https://github.com/3cky/mbusd/), running as docker service on my RBPI

## Features

### Zone 1 Control
- **Zone 1 setpoint temperature** - Set point temperature for Zone 1 (heating curve offset)
  - In Compensation Curve mode: Water shift offset -5..5°C (podbicie krzywej grzewczej)
  - In Direct mode: Direct water/room/pool temperature setting
  - Register: 12 (Modbus protocol address)

- **Zone 1 current temperature** - Actual temperature in Zone 1 (water/room/pool depending on sensor type)
  - Register: 14 (Modbus protocol address)

- **Zone 1 sensor type** - Shows which sensor is being used for Zone 1
  - Types: Water temperature, External room sensor, Internal room sensor, Room thermistor, Pool sensor
  - Register: 10 (Modbus protocol address)

- **Zone 1 temperature setting mode** - Current temperature control mode
  - Modes: Room temperature, Compensation curve (Water), Direct (Water), Pool temperature
  - Register: 16 (Modbus protocol address)

### COP (Coefficient of Performance) Monitoring

The plugin automatically calculates and displays COP values for optimal performance monitoring:

- **Heat COP** - Efficiency in heating mode (Energy Generated / Energy Consumed)
- **Cool COP** - Efficiency in cooling mode
- **Tank COP** - Efficiency in tank heating mode
- **Overall COP** - System-wide efficiency

**COP Values Interpretation:**
- COP < 2.0: Low efficiency - system may need maintenance or optimization
- COP 2.5-4.0: Good efficiency - normal operation
- COP > 4.0: Excellent efficiency - optimal performance

### Performance Optimization

The plugin includes automatic performance monitoring:
- Alerts when overall COP drops below 2.0 (performance warning)
- Logs excellent performance when COP exceeds 4.0
- Real-time efficiency tracking for all operating modes

### Error Monitoring

- **Current error code** - Detailed error descriptions with history
- **Current error status** - Alert sensor (0=OK, 1=Error)
- **Error history** - Last 10 errors stored persistently

## Configuration

All sensors and settings are configured in `config.yaml`. See the file for detailed configuration options.


