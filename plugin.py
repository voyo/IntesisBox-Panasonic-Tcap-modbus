#!/usr/bin/env python
"""
Panasonic-IntesisBox. Domoticz plugin.
Author: Wojtek Sawasciuk  <voyo@no-ip.pl>

Requirements: 
    1.python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
        (pi@raspberrypi:~$ sudo pip3 install minimalmodbus)
    2.Communication module Modbus USB to RS485 converter module
    3.python module pyModbusTCP
    4.'something' what can act as proxy for Modbus TCP to Modbus RTU (RS-232/485) connectivity. Hardware or software solution.
      I'm using open-source mbusd (https://github.com/3cky/mbusd/ , running as docker service on my RBPI
      
"""
"""
<plugin key="Panasonic-IntesisBox" name="Panasonic-IntesisBox" version="0.9" author="voyo@no-ip.pl">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="30px" required="true" default="502"/>
        <param field="SerialPort" label="Modbus Port" width="200px" required="true" default="/dev/ttyUSB0" />
        <param field="Mode1" label="Baud rate" width="40px" required="true" default="9600"  />
        <param field="Mode2" label="Device ID" width="40px" required="true" default="1" />
        <param field="Mode3" label="Reading Interval * 10s." width="40px" required="true" default="1" />
        <param field="Mode4" label="Modbus type" width="75px">
            <description><h2>Modbus type</h2>Select the desired type of modbus connection</description>
            <options>
                <option label="TCP" value="TCP" default="true" />
                <option label="RTU" value="RTU" />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="false" />
            </options>
        </param>
    </params>
</plugin>

"""

import minimalmodbus
import serial
import Domoticz
from time import sleep
import yaml
import os
import json
import time

# Improved retry configuration
INITIAL_RETRY_DELAY = 0.5  # Start with 500ms instead of 5s
MAX_RETRY_DELAY = 5.0      # Cap at 5 seconds
MAX_RETRIES = 3            # Maximum number of retry attempts
MODBUS_TIMEOUT_RTU = 2.0   # Increased from 1s for RTU
MODBUS_TIMEOUT_TCP = 3.0   # Increased from 2s for TCP

# Legacy compatibility
sleepInterval = INITIAL_RETRY_DELAY

# for TCP modbus connection
from pyModbusTCP.client import ModbusClient

def retry_with_backoff(func, max_retries=MAX_RETRIES, operation_name="Modbus operation"):
    """
    Retry a function with exponential backoff

    Args:
        func: Function to retry (should be a lambda or callable)
        max_retries: Maximum number of retry attempts
        operation_name: Name of operation for logging

    Returns:
        Result of func() if successful

    Raises:
        Last exception if all retries fail
    """
    retry_delay = INITIAL_RETRY_DELAY
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                Domoticz.Debug(f"{operation_name} failed (attempt {attempt + 1}/{max_retries}): {e}")
                Domoticz.Debug(f"Retrying in {retry_delay:.1f}s...")
                sleep(retry_delay)
                # Exponential backoff: 0.5s → 1s → 2s → 4s (capped at MAX_RETRY_DELAY)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
            else:
                Domoticz.Error(f"{operation_name} failed after {max_retries} attempts: {e}")

    # If we get here, all retries failed
    raise last_exception

# Error code mapping from IntesisBox manual (page 20-21)
ERROR_CODES = {
    0: "No abnormality detected",
    112: "H12: Indoor/Outdoor capacity unmatched",
    115: "H15: Outdoor compressor temperature sensor abnormality",
    120: "H20: Water pump abnormality",
    123: "H23: Indoor refrigerant liquid temperature sensor abnormality",
    127: "H27: Service valve error",
    128: "H28: Abnormal solar sensor",
    131: "H31: Abnormal swimming pool sensor",
    136: "H36: Abnormal buffer tank sensor",
    138: "H38: Brand code not match",
    142: "H42: Compressor low pressure abnormality",
    143: "H43: Abnormal Zone 1 sensor",
    144: "H44: Abnormal Zone 2 sensor",
    162: "H62: Water flow switch abnormality",
    163: "H63: Refrigerant low pressure abnormality",
    164: "H64: Refrigerant high pressure abnormality",
    165: "H65: Deice circulation error",
    167: "H67: Abnormal External Thermistor 1",
    168: "H68: Abnormal External Thermistor 2",
    170: "H70: Back-up heater OLP abnormality",
    172: "H72: Tank sensor abnormal",
    174: "H74: PCB communication error",
    175: "H75: Low water temperature control",
    176: "H76: Indoor - control panel communication abnormality",
    190: "H90: Indoor/outdoor abnormal communication",
    191: "H91: Tank heater OLP abnormality",
    195: "H95: Indoor/Outdoor wrong connection",
    198: "H98: Outdoor high pressure overload protection",
    199: "H99: Indoor heat exchanger freeze prevention",
    212: "F12: Pressure switch activate",
    214: "F14: Outdoor compressor abnormal revolution",
    215: "F15: Outdoor fan motor lock abnormality",
    216: "F16: Total running current protection",
    220: "F20: Outdoor compressor overheating protection",
    222: "F22: IPM (power transistor) overheating protection",
    223: "F23: Outdoor Direct Current (DC) peak detection",
    224: "F24: Refrigeration cycle abnormality",
    225: "F25: Cooling/Heating cycle changeover abnormality",
    227: "F27: Pressure switch abnormality",
    229: "F29: Low Discharge Superheat",
    230: "F30: Water outlet sensor 2 abnormality",
    232: "F32: Abnormal Internal Thermostat",
    236: "F36: Outdoor air temperature sensor abnormality",
    237: "F37: Indoor water inlet temperature sensor abnormality",
    240: "F40: Outdoor discharge pipe temperature sensor abnormality",
    241: "F41: PFC control",
    242: "F42: Outdoor heat exchanger temperature sensor abnormality",
    243: "F43: Outdoor defrost sensor abnormality",
    245: "F45: Indoor water outlet temperature sensor abnormality",
    246: "F46: Outdoor Current Transformer open circuit",
    248: "F48: Outdoor EVA outlet temperature sensor abnormality",
    249: "F49: Outdoor bypass outlet temperature sensor abnormality",
    295: "F95: Cooling high pressure overload protection"
}

def getErrorDescription(error_code):
    """Convert error code to human-readable description"""
    return ERROR_CODES.get(error_code, f"Unknown error code: {error_code}")

def saveErrorHistory(plugin):
    """Save error history to file"""
    try:
        historyPath = os.path.join(os.path.dirname(__file__), 'error_history.json')
        with open(historyPath, 'w') as f:
            json.dump({
                'errorHistory': plugin.errorHistory,
                'lastErrorCode': plugin.lastErrorCode
            }, f, indent=2)
    except Exception as e:
        Domoticz.Error(f"Failed to save error history: {e}")

def loadErrorHistory(plugin):
    """Load error history from file"""
    try:
        historyPath = os.path.join(os.path.dirname(__file__), 'error_history.json')
        if os.path.exists(historyPath):
            with open(historyPath, 'r') as f:
                data = json.load(f)
                plugin.errorHistory = data.get('errorHistory', [])
                plugin.lastErrorCode = data.get('lastErrorCode', 0)
                Domoticz.Log(f"Loaded {len(plugin.errorHistory)} error history entries")
        else:
            Domoticz.Log("No error history file found, starting fresh")
    except Exception as e:
        Domoticz.Error(f"Failed to load error history: {e}")
        plugin.errorHistory = []
        plugin.lastErrorCode = 0

def addToErrorHistory(plugin, error_code):
    """Add error code to error history list"""
    import datetime
    if error_code != 0 and error_code != plugin.lastErrorCode:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_desc = getErrorDescription(error_code)
        error_entry = f"{timestamp}: {error_desc}"

        # Add to history
        plugin.errorHistory.insert(0, error_entry)

        # Keep only last N entries
        if len(plugin.errorHistory) > plugin.maxErrorHistory:
            plugin.errorHistory = plugin.errorHistory[:plugin.maxErrorHistory]

        plugin.lastErrorCode = error_code
        Domoticz.Log(f"Error logged: {error_entry}")

        # Save to file
        saveErrorHistory(plugin)

def getErrorHistoryString(plugin):
    """Get error history as formatted string"""
    if not plugin.errorHistory:
        return "No previous errors"

    history_str = "Recent errors:\n" + "\n".join(plugin.errorHistory[:5])
    return history_str

def getZoneSensorTypeText(sensor_value):
    """Convert zone sensor type value to text"""
    sensor_types = {
        1: "Water temperature",
        2: "External room sensor",
        3: "Internal room sensor",
        4: "Room thermistor",
        5: "Pool Sensor"
    }
    return sensor_types.get(sensor_value, f"Unknown ({sensor_value})")

def getZoneTempSettingModeText(mode_value):
    """Convert zone temperature setting mode value to text"""
    modes = {
        1: "Room temperature",
        2: "Compensation curve (Water)",
        3: "Direct (Water)",
        4: "Pool temperature"
    }
    return modes.get(mode_value, f"Unknown ({mode_value})")

def saveDefrostHistory(plugin):
    """Save defrost history to file"""
    try:
        historyPath = os.path.join(os.path.dirname(__file__), 'defrost_history.json')
        with open(historyPath, 'w') as f:
            json.dump({
                'defrostHistory': plugin.defrostHistory,
                'defrostCycleCount': plugin.defrostCycleCount,
                'totalDefrostDuration': plugin.totalDefrostDuration,
                'lastDefrostDuration': plugin.lastDefrostDuration
            }, f, indent=2)
    except Exception as e:
        Domoticz.Error(f"Failed to save defrost history: {e}")

def loadDefrostHistory(plugin):
    """Load defrost history from file"""
    try:
        historyPath = os.path.join(os.path.dirname(__file__), 'defrost_history.json')
        if os.path.exists(historyPath):
            with open(historyPath, 'r') as f:
                data = json.load(f)
                plugin.defrostHistory = data.get('defrostHistory', [])
                plugin.defrostCycleCount = data.get('defrostCycleCount', 0)
                plugin.totalDefrostDuration = data.get('totalDefrostDuration', 0)
                plugin.lastDefrostDuration = data.get('lastDefrostDuration', 0)
                Domoticz.Log(f"Loaded {len(plugin.defrostHistory)} defrost history entries, {plugin.defrostCycleCount} total cycles")
        else:
            Domoticz.Log("No defrost history file found, starting fresh")
    except Exception as e:
        Domoticz.Error(f"Failed to load defrost history: {e}")
        plugin.defrostHistory = []
        plugin.defrostCycleCount = 0
        plugin.totalDefrostDuration = 0
        plugin.lastDefrostDuration = 0

def detectDefrost(plugin):
    """
    Detect if the heat pump is in defrost mode.
    Defrost is occurring when heat energy is being consumed but not generated.
    This means the compressor is working but the heat is being used to defrost the outdoor coil.
    """
    # Defrost condition: heat energy consumption > 0 AND heat energy generation == 0
    isDefrosting = plugin.heatEnergyConsumed > 0 and plugin.heatEnergyGenerated == 0

    import datetime
    currentTime = datetime.datetime.now()

    # Defrost cycle started
    if isDefrosting and not plugin.isDefrosting:
        plugin.isDefrosting = True
        plugin.defrostStartTime = currentTime
        plugin.defrostCycleCount += 1
        timestamp = currentTime.strftime("%Y-%m-%d %H:%M:%S")
        Domoticz.Log(f"🔵 DEFROST STARTED at {timestamp} (Cycle #{plugin.defrostCycleCount})")

    # Defrost cycle ended
    elif not isDefrosting and plugin.isDefrosting:
        plugin.isDefrosting = False
        if plugin.defrostStartTime:
            duration = (currentTime - plugin.defrostStartTime).total_seconds()
            plugin.lastDefrostDuration = duration
            plugin.totalDefrostDuration += duration
            timestamp = currentTime.strftime("%Y-%m-%d %H:%M:%S")

            # Add to history
            defrost_entry = {
                'start': plugin.defrostStartTime.strftime("%Y-%m-%d %H:%M:%S"),
                'end': timestamp,
                'duration': duration
            }
            plugin.defrostHistory.insert(0, defrost_entry)

            # Keep only recent entries
            if len(plugin.defrostHistory) > plugin.maxDefrostHistory:
                plugin.defrostHistory = plugin.defrostHistory[:plugin.maxDefrostHistory]

            Domoticz.Log(f"🟢 DEFROST ENDED at {timestamp} (Duration: {duration:.0f}s / {duration/60:.1f}min)")

            # Save history
            saveDefrostHistory(plugin)
            plugin.defrostStartTime = None

    return isDefrosting

def calculateCOP(energy_generated, energy_consumed):
    """Calculate Coefficient of Performance (COP)

    COP = Energy Generated / Energy Consumed
    Higher COP means better efficiency
    Typical values: 2.5 - 5.0 for heat pumps
    """
    if energy_consumed is None or energy_consumed <= 0:
        return 0.0
    if energy_generated is None or energy_generated < 0:
        return 0.0

    cop = energy_generated / energy_consumed
    # Sanity check - COP should typically be between 0 and 10
    if cop > 10:
        Domoticz.Debug(f"COP value seems unusually high: {cop:.2f} (Generated: {energy_generated}, Consumed: {energy_consumed})")
    return round(cop, 2)

def loadConfig(configPath):
    """Load configuration from YAML file"""
    try:
        with open(configPath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        Domoticz.Error("Failed to load config file: "+str(e))
        return None

class ModbusDevice:
    """Base class for Modbus devices with common functionality (DRY principle)"""
    def __init__(self, ID, name, register, functioncode=3, nod=0, options=None, Used=1,
                 Description=None, TypeName=None, Type=0, SubType=0, SwitchType=0, signed=False):
        self.ID = ID
        self.name = name
        self.register = register
        self.functioncode = functioncode
        self.nod = nod
        self.value = 0
        self.signed = signed
        self.options = options if options is not None else None
        self.TypeName = TypeName if TypeName is not None else ""
        self.Type = Type
        self.SubType = SubType
        self.SwitchType = SwitchType
        self.Used = Used
        self.Description = Description if Description is not None else ""

        self._create_device()

    def _create_device(self):
        """Create device in Domoticz if it doesn't exist"""
        if self.ID not in Devices:
            Domoticz.Log(f"Registering device: {self.name} {self.ID}")
            if self.TypeName != "":
                Domoticz.Log(f"Adding device: {self.name} {self.ID} {self.TypeName} Description: {self.Description}")
                Domoticz.Device(Name=self.name, Unit=self.ID, TypeName=self.TypeName,
                              Used=self.Used, Options=self.options, Description=self.Description).Create()
            else:
                Domoticz.Device(Name=self.name, Unit=self.ID, Type=self.Type, Subtype=self.SubType,
                              Switchtype=self.SwitchType, Used=self.Used, Options=self.options,
                              Description=self.Description).Create()
                Domoticz.Log(f"Adding device: name {self.name}, Type: {self.Type} SubType: {self.SubType} SwitchType: {self.SwitchType}")
        else:
            Domoticz.Log(f"Device already exists: {self.name} {self.ID}")

    def _read_modbus_register(self, RS485):
        """Read value from modbus register - common implementation"""
        if RS485.MyMode == "minimalmodbus":
            if self.functioncode in [3, 4]:
                payload = retry_with_backoff(
                    lambda: RS485.read_register(self.register, number_of_decimals=self.nod,
                                               functioncode=self.functioncode, signed=self.signed),
                    operation_name=f"Read '{self.name}' (reg {self.register})"
                )
                return payload

        elif RS485.MyMode == "pymodbus":
            if self.functioncode == 3:
                def read_holding():
                    registers = RS485.read_holding_registers(self.register, 1)
                    if registers:
                        value = registers[0]
                        if value > 32767 and self.signed:
                            value -= 65536
                        return value / 10 ** self.nod
                    return 0
                return retry_with_backoff(read_holding, operation_name=f"Read '{self.name}' (reg {self.register})")

            elif self.functioncode == 4:
                def read_input():
                    registers = RS485.read_input_registers(self.register, 1)
                    if registers:
                        value = registers[0]
                        if value > 32767 and self.signed:
                            value -= 65536
                        return value / 10 ** self.nod
                    return 0
                return retry_with_backoff(read_input, operation_name=f"Read '{self.name}' (reg {self.register})")

        Domoticz.Error("Unknown Modbus mode or function code")
        return 0


class Switch(ModbusDevice):
    """Modbus device with write capability (settings/controls)"""
    def __init__(self, ID, name, register, functioncode=3, options=None, Used=1,
                 Description=None, TypeName=None, Type=0, SubType=0, SwitchType=0, nod=0):
        # Call parent constructor - eliminates duplication
        super().__init__(ID, name, register, functioncode, nod, options, Used,
                        Description, TypeName, Type, SubType, SwitchType)

    def LevelValueConversion2Data(self,command,level):
        Domoticz.Debug("command2data, command:"+str(command)+" register: "+str(self.register)+" level: "+str(level) )
        if command=='On':
            return 1
        if command=='Off':
            return 0

        # Temperature setpoint devices (Type 242, SubType 1) - use direct value
        # Registers: 33 (Tank set temp), 12 (Zone 1 setpoint)
        if self.Type == 242 and self.SubType == 1:
            # Direct temperature value, no conversion needed
            value = int(level)
            Domoticz.Debug(f"Temperature setpoint conversion: level={level} -> value={value} (register {self.register})")
        # Selector switches (Type 244) - convert Domoticz level to device value
        # Registers: 4 (OperatingMode), 5 (Heat temp method), 6 (Cool temp method), 85 (Valve direction)
        elif self.Type == 244 and (self.SubType == 62 or self.SubType == 0):
            # Special handling for Valve direction (register 85) - 0-based values
            if self.register == 85:
                # Valve direction is read-only, but if write attempted: level 10(Tank)->0, 20(Room)->1
                value = int(level / 10) - 1
                Domoticz.Debug(f"Valve direction conversion: level={level} -> value={value} (register {self.register})")
            else:
                # Standard selector: level (10, 20, 30...) to device value (1, 2, 3...)
                value = int(level / 10)
                Domoticz.Debug(f"Selector conversion: level={level} -> value={value} (register {self.register})")
        else:
            # Fallback - this shouldn't normally be reached
            if command=='Set Level':
                value = int(level / 10)
                Domoticz.Log(f"Warning: Using fallback conversion for register {self.register}, Type {self.Type}, SubType {self.SubType}")
            else:
                value = int(level)
        return value           
   
    def LevelValueConversion2Level(self,data):
        Domoticz.Debug("value2level, data:"+str(data)+" register:"+str(self.register))
        if self.register==0:
                # For On/Off switches, return numeric value directly
                value = data
        elif self.register==4:
                # For OperatingMode, convert to selector level (0->0, 1->10, 2->20, etc.)
                value = (data ) * 10
        elif self.register==5 or self.register==6:
                # For Heat/Cool temp method, convert to selector level (1->10, 2->20)
                value = data * 10
        elif self.register==85:
                # For Valve direction, convert to selector level (0->10, 1->20)
                # Device returns 0-based values: 0=Tank, 1=Room
                value = (data + 1) * 10
        else:
            value = data
            Domoticz.Debug("Level value conversion - data MIGHT be not valid: "+str(data)+" register: "+str(self.register))
        Domoticz.Debug("Conversion mapping from "+str(data)+" to "+str(value))
        return value



    def UpdateSettingValue(self, RS485):
        """Read setting value from Modbus and update Domoticz device"""
        # Use common read method from parent class (DRY)
        data = self._read_modbus_register(RS485)
# 	for devices with 'level' we need to do conversion on domoticz levels, like 0->10, 1->20, 2->30 etc        
        value = self.LevelValueConversion2Level(data)
        self.value = value
        Domoticz.Debug("UPDATING switch: "+self.name+" wartosc: "+str(value) )
        if self.TypeName == "Switch" or (self.Type == 244 and self.SubType == 73):
            if value == 0:
                Devices[self.ID].Update(nValue=0, sValue = "Off")
            elif value > 0:
                Devices[self.ID].Update(nValue=1, sValue = "On")
        elif self.TypeName == "Selector Switch" or  (self.Type == 244 and self.SubType == 62):
            if value == 0:
                Devices[self.ID].Update(nValue=0, sValue = "Off")
            elif value > 0:
                Devices[self.ID].Update(nValue=1, sValue = str(value))
        else: 
            Devices[self.ID].Update(nValue=int(value),sValue=str(value))  # force update, even if the value has no changed.


    def UpdateRegister(self,RS485,command,level):
        if command == "Set Level":
            value = self.LevelValueConversion2Data(command,level)
        else:
            if command == "On":
                value = 1
            elif command == "Off":
                value = 0

        Domoticz.Log(f"Writing to register {self.register} ('{self.name}'): command={command}, level={level}, value={value}")

        if RS485.MyMode == "minimalmodbus":
            retry_with_backoff(
                lambda: RS485.write_register(self.register, value, functioncode=self.functioncode),
                operation_name=f"Write '{self.name}' (reg {self.register}) = {value}"
            )
        elif RS485.MyMode == "pymodbus":
            retry_with_backoff(
                lambda: RS485.write_single_register(self.register, int(value)),
                operation_name=f"Write '{self.name}' (reg {self.register}) = {int(value)}"
            )
        else:
            Domoticz.Error("Unknown Modbus mode")
            return

        Domoticz.Log(f"✓ Successfully wrote {value} to register {self.register} ('{self.name}')")

        

class Dev(ModbusDevice):
    """Modbus device for read-only sensors"""
    def __init__(self, ID, name, nod, register, functioncode=3, options=None, Used=1,
                 Description=None, signed=False, TypeName=None, Type=0, SubType=0, SwitchType=0):
        # Call parent constructor - eliminates duplication
        super().__init__(ID, name, register, functioncode, nod, options, Used,
                        Description, TypeName, Type, SubType, SwitchType, signed)
                      

    def UpdateSensorValue(self, RS485):
        """Read sensor value from Modbus and update Domoticz device"""
        # Use common read method from parent class (DRY)
        data = self._read_modbus_register(RS485)
        Devices[self.ID].Update(0, str(data)+';'+str(data), True)
        Domoticz.Debug(f"Device: {self.name} data={data} from register: {hex(self.register)}")



class BasePlugin:
    def __init__(self):
        self.runInterval = 1
        self.RS485 = ""
        self.connectionHealthy = True
        self.errorHistory = []  # Store error history (max 10 entries)
        self.maxErrorHistory = 10
        self.currentErrorCode = 0
        self.lastErrorCode = 0
        # Energy values for COP calculation
        self.heatEnergyGenerated = 0
        self.heatEnergyConsumed = 0
        self.coolEnergyGenerated = 0
        self.coolEnergyConsumed = 0
        self.tankEnergyGenerated = 0
        self.tankEnergyConsumed = 0
        # Defrost cycle monitoring
        self.isDefrosting = False
        self.defrostStartTime = None
        self.defrostCycleCount = 0
        self.totalDefrostDuration = 0  # in seconds
        self.lastDefrostDuration = 0
        self.defrostHistory = []  # Store recent defrost events
        self.maxDefrostHistory = 20
        return

    def onStart(self):
        if Parameters["Mode6"] == 'Debug':
            Domoticz.Debugging(1)
            DumpConfigToLog()
            Domoticz.Debug("Debugging enabled")

        # Load error history from file
        loadErrorHistory(self)

        # Load defrost history from file
        loadDefrostHistory(self)

        DeviceID=int(Parameters["Mode2"])
        if Parameters["Mode4"] == "RTU" or Parameters["Mode4"] == "ASCII":
            Domoticz.Debug("Using minimalmodbus library")
            self.RS485 = minimalmodbus.Instrument(Parameters["SerialPort"], DeviceID)
            self.RS485.serial.baudrate = Parameters["Mode1"]
            self.RS485.serial.bytesize = 8
            self.RS485.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.RS485.serial.stopbits = 1
            self.RS485.serial.timeout = MODBUS_TIMEOUT_RTU  # Increased from 1s to 2s
            self.RS485.MyMode = 'minimalmodbus'
            self.RS485.mode = minimalmodbus.MODE_RTU
            Domoticz.Log(f"RTU Modbus configured: {Parameters['SerialPort']}, baudrate={Parameters['Mode1']}, timeout={MODBUS_TIMEOUT_RTU}s")
        elif Parameters["Mode4"] == "TCP":
            Domoticz.Debug("TCP mode is not supported by minimalmodbus, so we use pymodbus instead")
            Domoticz.Debug("Using pymodbus, connecting to "+Parameters["Address"]+":"+Parameters["Port"]+" unit ID"+ str(DeviceID))
            try:
                Domoticz.Debug("Using pymodbus, connecting to "+Parameters["Address"]+":"+Parameters["Port"]+" unit ID"+ str(DeviceID))
                self.RS485 = ModbusClient(host=Parameters["Address"], port=int(Parameters["Port"]), unit_id=DeviceID, auto_open=True, auto_close=True, timeout=MODBUS_TIMEOUT_TCP)  # Increased from 2s to 3s
                self.RS485.MyMode = 'pymodbus'
                Domoticz.Log(f"TCP Modbus configured: {Parameters['Address']}:{Parameters['Port']}, unit_id={DeviceID}, timeout={MODBUS_TIMEOUT_TCP}s")
            except Exception as e:
                Domoticz.Error(f"pyModbus connection failure: {e}")
        else:
            Domoticz.Log("Unknown mode: "+Parameters["Mode4"])

        if Parameters["Mode6"] == 'Debug':
                self.RS485.debug = True
        devicecreated = []
        Domoticz.Log("Panasonic-IntesisBox-Modbus plugin start")

        # Load configuration from external file
        configPath = os.path.join(os.path.dirname(__file__), 'config.yaml')
        config = loadConfig(configPath)

        if config is None:
            Domoticz.Error("Failed to load config, using default configuration")
            # Fallback to hardcoded configuration
            self.sensors = [
                     Dev(1,"outdoor_temp",0,1,functioncode=3,TypeName="Temperature",Description="Outside temperature",signed=True),
                     Dev(2,"outlet_water_temp",0,2,functioncode=3,TypeName="Temperature",Description="Outlet temperature",signed=True),
                     Dev(3,"inlet_temp",0,3,functioncode=3,TypeName="Temperature",Description="Inlet temperature",signed=True),
                     Dev(4,"tank_water_temp",0,32,functioncode=3,TypeName="Temperature",Description="Tank water temperature",signed=True),
                     Dev(5,"Tank energy consumption",0,45,functioncode=3,TypeName="kWh",Description="Tank mode energy consumption"),
                     Dev(6,"Heat energy consumption",0,46,functioncode=3,TypeName="kWh",Description="Heat mode energy consumption"),
                     Dev(7,"Cool energy consumption",0,47,functioncode=3,TypeName="kWh",Description="Cool mode energy consumption"),
                     Dev(8,"Tank Energy Generation",0,187,functioncode=3,TypeName="kWh",Description="Tank mode energy consumption"),
                     Dev(9,"Heat Energy Generation",0,188,functioncode=3,TypeName="kWh",Description="Heat mode energy consumption"),
                     Dev(10,"Cool Energy Generation",0,189,functioncode=3,TypeName="kWh",Description="Cool mode energy consumption"),
                     Dev(11,"Current error code",0,52,functioncode=3,TypeName="Text",Description="Current error code with description"),
                     Dev(12,"Connection Health",0,0,functioncode=3,TypeName="Text",Description="Modbus connection health status"),
                     Dev(13,"Current error status",0,70,functioncode=3,TypeName="Alert",Description="Current error status (0=OK, 1=Error)")
                ]

            self.settings = [
                     Switch(51,"System On/Off",0,functioncode=3),
                     Switch(52,"OperatingMode",4,functioncode=3,Type=244,SwitchType=18,SubType=0,options={"LevelActions": "|act1| |act2|","LevelNames": "|" + "Heat" + "|" + "Heat Tank" + "|" + "Tank"+ "|" + "Cool Tank"+ "|" + "Cool"+ "|" + "Auto"+ "|" + "Auto Tank"+ "|" + "Auto Heat"+ "|" + "Auto Heat Tank"+ "|" + "Auto Cool"+ "|" + "Auto Cool Tank", "LevelOffHidden": "true", "SelectorStyle": "1"}),
                     Switch(53,"Heat temp method",5,functioncode=3,Description="Heat mode temperature setting method",Type=244,SwitchType=18,SubType=62,options={"LevelActions": "|||","LevelNames": "|" + "Compensation Curve" + "|" + "Direct", "LevelOffHidden": "true", "SelectorStyle": "1"}),
                     Switch(54,"Cool temp method",6,functioncode=3,Description="Cool mode temperature setting method",Type=244,SwitchType=18,SubType=62,options={"LevelActions": "|||","LevelNames": "|" + "Compensation Curve" + "|" + "Direct", "LevelOffHidden": "true", "SelectorStyle": "1"}),
                     Switch(55,"Tank set temp",33,functioncode=3,Description="Tank set temperature point", Type=242 , SubType=1),
                     Switch(56,"Valve direction",85,functioncode=3,Description="Valve direction (read-only)",Type=244,SwitchType=18,SubType=62,options={"LevelActions": "|||","LevelNames": "|" + "Tank" + "|" + "Room", "LevelOffHidden": "true", "SelectorStyle": "1"})
                      ]
        else:
            # Build sensors from config
            Domoticz.Log("Loading sensors and settings from config.yaml")
            self.sensors = []
            for sensor in config.get('sensors', []):
                self.sensors.append(Dev(
                    sensor['id'],
                    sensor['name'],
                    sensor.get('decimals', 0),
                    sensor['register'],
                    functioncode=sensor.get('functioncode', 3),
                    TypeName=sensor.get('typename', ''),
                    Description=sensor.get('description', ''),
                    signed=sensor.get('signed', False),
                    Type=sensor.get('type', 0),
                    SubType=sensor.get('subtype', 0),
                    SwitchType=sensor.get('switchtype', 0),
                    options=sensor.get('options', None)
                ))

            # Build settings from config
            self.settings = []
            for setting in config.get('settings', []):
                self.settings.append(Switch(
                    setting['id'],
                    setting['name'],
                    setting['register'],
                    functioncode=setting.get('functioncode', 3),
                    Description=setting.get('description', ''),
                    Type=setting.get('type', 0),
                    SubType=setting.get('subtype', 0),
                    SwitchType=setting.get('switchtype', 0),
                    options=setting.get('options', None),
                    nod=setting.get('decimals', 0)
                ))


    def onStop(self):
        Domoticz.Log("Panasonic-IntesisBox Modbus plugin stop")

    def readErrorCode(self, RS485):
        """Read error code from register 52"""
        try:
            if RS485.MyMode == "pymodbus":
                data = retry_with_backoff(
                    lambda: RS485.read_holding_registers(52, 1),
                    operation_name="Read error code (reg 52)"
                )
                if data:
                    return data[0]
                else:
                    return 0
            elif RS485.MyMode == "minimalmodbus":
                error_code = retry_with_backoff(
                    lambda: RS485.read_register(52, number_of_decimals=0, functioncode=3),
                    operation_name="Read error code (reg 52)"
                )
                return error_code
            return 0
        except Exception as e:
            Domoticz.Error(f"Failed to read error code after all retries: {e}")
            return 0

    def readHistoricalErrors(self, RS485):
        """Try to read historical error codes from additional modbus registers.

        This function attempts to read registers 53-57 to check if historical
        errors are stored there. You may need to consult your IntesisBox modbus
        documentation to find the correct registers for error history.
        """
        historical_errors = []
        # Try reading registers 53-57 (adjust based on your device's modbus map)
        error_registers = [53, 54, 55, 56, 57]

        for reg in error_registers:
            try:
                if RS485.MyMode == "pymodbus":
                    data = RS485.read_holding_registers(reg, 1)
                    if data and data[0] != 0:
                        error_code = data[0]
                        Domoticz.Debug(f"Found error code {error_code} in register {reg}")
                        historical_errors.append(error_code)
                elif RS485.MyMode == "minimalmodbus":
                    error_code = RS485.read_register(reg, number_of_decimals=0, functioncode=3)
                    if error_code != 0:
                        Domoticz.Debug(f"Found error code {error_code} in register {reg}")
                        historical_errors.append(error_code)
            except Exception as e:
                # Register might not exist, skip silently
                Domoticz.Debug(f"Could not read register {reg}: {e}")
                continue

        return historical_errors

    def onHeartbeat(self):
        self.runInterval -= 1
        if self.runInterval <= 0:
            anyFailure = False
            errorCode = 0

            for i in self.sensors:
                # Skip the connection health sensor itself
                if i.ID == 12:
                    continue

                try:
                    # Get data from modbus
                    Domoticz.Debug("Getting data from modbus for device:"+i.name+" ID:"+str(i.ID))

                    # Special handling for error code sensor (ID 11 - register 52)
                    if i.ID == 11:
                        errorCode = self.readErrorCode(self.RS485)
                        self.currentErrorCode = errorCode

                        # Add to error history if new error
                        if errorCode != 0:
                            addToErrorHistory(self, errorCode)

                        # Try to read historical errors from additional registers
                        # This will check registers 53-57 for potential error history
                        # Enable Debug mode to see which registers contain data
                        historical_errors = self.readHistoricalErrors(self.RS485)
                        if historical_errors:
                            Domoticz.Log(f"Found {len(historical_errors)} historical error(s) in modbus registers")
                            for hist_error in historical_errors:
                                # Add historical errors to our history if not already there
                                if hist_error != errorCode:  # Don't duplicate current error
                                    error_exists = any(getErrorDescription(hist_error) in entry for entry in self.errorHistory)
                                    if not error_exists:
                                        import datetime
                                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        error_desc = getErrorDescription(hist_error)
                                        error_entry = f"{timestamp}: {error_desc} (from modbus history)"
                                        self.errorHistory.append(error_entry)
                                        Domoticz.Log(f"Added historical error: {error_entry}")
                            # Save updated history
                            saveErrorHistory(self)

                        # Display current error with description and history
                        error_desc = getErrorDescription(errorCode)
                        display_text = f"Current: {error_desc}"

                        # Add recent error history
                        if self.errorHistory:
                            history_preview = "\nPrevious: " + "; ".join(self.errorHistory[:3])
                            display_text += history_preview

                        Devices[i.ID].Update(nValue=0, sValue=display_text)
                        Domoticz.Debug(f"Error code sensor updated: {display_text}")

                    # Special handling for current error status (ID 13 - register 70)
                    elif i.ID == 13:
                        # This is an Alert sensor that shows 0=OK, 1=Error
                        if self.RS485.MyMode == "pymodbus":
                            data = self.RS485.read_holding_registers(70, 1)
                            error_status = data[0] if data else 0
                        else:
                            error_status = self.RS485.read_register(70, number_of_decimals=0, functioncode=3)

                        # Update Alert sensor
                        if error_status == 0:
                            Devices[i.ID].Update(nValue=0, sValue="No Error")
                        else:
                            Devices[i.ID].Update(nValue=4, sValue="Error Active")
                        Domoticz.Debug(f"Error status sensor updated: {error_status}")

                    # Special handling for Zone 1 sensor type (ID 15 - register 10)
                    elif i.ID == 15:
                        if self.RS485.MyMode == "pymodbus":
                            data = self.RS485.read_holding_registers(10, 1)
                            sensor_type = data[0] if data else 0
                        else:
                            sensor_type = self.RS485.read_register(10, number_of_decimals=0, functioncode=3)

                        sensor_text = getZoneSensorTypeText(sensor_type)
                        Devices[i.ID].Update(nValue=0, sValue=sensor_text)
                        Domoticz.Debug(f"Zone 1 sensor type updated: {sensor_text}")

                    # Special handling for Zone 1 temp setting mode (ID 16 - register 16)
                    elif i.ID == 16:
                        if self.RS485.MyMode == "pymodbus":
                            data = self.RS485.read_holding_registers(16, 1)
                            mode_value = data[0] if data else 0
                        else:
                            mode_value = self.RS485.read_register(16, number_of_decimals=0, functioncode=3)

                        mode_text = getZoneTempSettingModeText(mode_value)
                        Devices[i.ID].Update(nValue=0, sValue=mode_text)
                        Domoticz.Debug(f"Zone 1 temp setting mode updated: {mode_text}")

                    # COP sensors (ID 17-20) - will be calculated after all energy values are read
                    elif i.ID in [17, 18, 19, 20]:
                        # Skip COP sensors for now, will update them later
                        pass

                    # Defrost sensors (ID 21-23) - will be calculated after energy values are read
                    elif i.ID in [21, 22, 23]:
                        # Skip defrost sensors for now, will update them later
                        pass

                    else:
                        # Normal sensor update
                        self.sensors[i.ID-1].UpdateSensorValue(self.RS485)

                        # Store energy values for COP calculation
                        if i.ID == 6:  # Heat energy consumption
                            self.heatEnergyConsumed = float(Devices[i.ID].sValue.split(';')[0])
                        elif i.ID == 7:  # Cool energy consumption
                            self.coolEnergyConsumed = float(Devices[i.ID].sValue.split(';')[0])
                        elif i.ID == 5:  # Tank energy consumption
                            self.tankEnergyConsumed = float(Devices[i.ID].sValue.split(';')[0])
                        elif i.ID == 9:  # Heat Energy Generation
                            self.heatEnergyGenerated = float(Devices[i.ID].sValue.split(';')[0])
                        elif i.ID == 10:  # Cool Energy Generation
                            self.coolEnergyGenerated = float(Devices[i.ID].sValue.split(';')[0])
                        elif i.ID == 8:  # Tank Energy Generation
                            self.tankEnergyGenerated = float(Devices[i.ID].sValue.split(';')[0])

                except Exception as e:
                    Domoticz.Log("Update failure: "+str(e))
                    anyFailure = True
                else:
                    if i.ID != 11:  # Already logged for error sensor
                        Domoticz.Debug("in HeartBeat "+i.name+": "+format(i.value))

            # Calculate and update COP sensors (ID 17-20)
            try:
                # Heat COP (ID 17)
                heatCOP = calculateCOP(self.heatEnergyGenerated, self.heatEnergyConsumed)
                if 17 in Devices:
                    Devices[17].Update(nValue=0, sValue=str(heatCOP))
                    Domoticz.Debug(f"Heat COP updated: {heatCOP} (Generated: {self.heatEnergyGenerated}W, Consumed: {self.heatEnergyConsumed}W)")

                # Cool COP (ID 18)
                coolCOP = calculateCOP(self.coolEnergyGenerated, self.coolEnergyConsumed)
                if 18 in Devices:
                    Devices[18].Update(nValue=0, sValue=str(coolCOP))
                    Domoticz.Debug(f"Cool COP updated: {coolCOP} (Generated: {self.coolEnergyGenerated}W, Consumed: {self.coolEnergyConsumed}W)")

                # Tank COP (ID 19)
                tankCOP = calculateCOP(self.tankEnergyGenerated, self.tankEnergyConsumed)
                if 19 in Devices:
                    Devices[19].Update(nValue=0, sValue=str(tankCOP))
                    Domoticz.Debug(f"Tank COP updated: {tankCOP} (Generated: {self.tankEnergyGenerated}W, Consumed: {self.tankEnergyConsumed}W)")

                # Overall COP (ID 20) - total energy generated / total energy consumed
                totalGenerated = self.heatEnergyGenerated + self.coolEnergyGenerated + self.tankEnergyGenerated
                totalConsumed = self.heatEnergyConsumed + self.coolEnergyConsumed + self.tankEnergyConsumed
                overallCOP = calculateCOP(totalGenerated, totalConsumed)
                if 20 in Devices:
                    Devices[20].Update(nValue=0, sValue=str(overallCOP))
                    Domoticz.Debug(f"Overall COP updated: {overallCOP} (Total Generated: {totalGenerated}W, Total Consumed: {totalConsumed}W)")

                # Performance optimization alerts
                if overallCOP > 0 and overallCOP < 2.0:
                    Domoticz.Log(f"PERFORMANCE WARNING: Overall COP is low ({overallCOP}). Consider checking system settings or maintenance.")
                elif overallCOP >= 4.0:
                    Domoticz.Debug(f"PERFORMANCE EXCELLENT: Overall COP is high ({overallCOP}). System is running efficiently.")

            except Exception as e:
                Domoticz.Log(f"Failed to calculate COP: {e}")

            # Detect and track defrost cycles
            try:
                isDefrosting = detectDefrost(self)

                # Update Defrost Status sensor (ID 21)
                if 21 in Devices:
                    if isDefrosting:
                        Devices[21].Update(nValue=1, sValue="Defrosting")
                        Domoticz.Debug("Defrost status: ACTIVE")
                    else:
                        Devices[21].Update(nValue=0, sValue="Normal")
                        Domoticz.Debug("Defrost status: Normal")

                # Update Defrost Cycle Count sensor (ID 22)
                if 22 in Devices:
                    Devices[22].Update(nValue=0, sValue=str(self.defrostCycleCount))
                    Domoticz.Debug(f"Defrost cycle count: {self.defrostCycleCount}")

                # Update Defrost Statistics sensor (ID 23)
                if 23 in Devices:
                    # Calculate average defrost duration
                    avgDuration = 0
                    if self.defrostCycleCount > 0 and self.totalDefrostDuration > 0:
                        avgDuration = self.totalDefrostDuration / self.defrostCycleCount

                    stats_text = f"Total cycles: {self.defrostCycleCount} | "
                    stats_text += f"Last: {self.lastDefrostDuration/60:.1f}min | "
                    stats_text += f"Avg: {avgDuration/60:.1f}min | "
                    stats_text += f"Total: {self.totalDefrostDuration/3600:.1f}h"

                    Devices[23].Update(nValue=0, sValue=stats_text)
                    Domoticz.Debug(f"Defrost statistics: {stats_text}")

            except Exception as e:
                Domoticz.Log(f"Failed to update defrost monitoring: {e}")

            # Update connection health status (ID 12) - now as Text sensor
            if anyFailure:
                self.connectionHealthy = False
                Devices[12].Update(nValue=0, sValue="Disconnected")
            else:
                self.connectionHealthy = True
                Devices[12].Update(nValue=1, sValue="Connected")

            self.runInterval = int(Parameters["Mode3"])

            for i in self.settings:
                l = len(self.settings)
                dev_len=len(self.sensors)
                try:
                         # Get data from modbus
                        Domoticz.Debug("Getting data from modbus for device:"+i.name+" ID:"+str(i.ID))
                        self.settings[i.ID-1-50].UpdateSettingValue(self.RS485)
                except Exception as e:
                        Domoticz.Log("Update failure: "+str(e))
                else:
                        Domoticz.Debug("in HeartBeat "+i.name+": "+format(i.value))
            self.runInterval = int(Parameters["Mode3"]) 



    def onCommand(self, u, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(u) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        if Parameters["Mode6"] == 'Debug':
                Domoticz.Debug(str(Devices[u].Name) + ": onCommand called: Parameter '" + str(Command) + "', Level: " + str(Level))
        dev_len=len(self.sensors)
        try:
            Domoticz.Debug("onCommand: Parameter " + str(u-1-50) )
            # onCommand and then UpdateRegister makes sense only for settings devices (switches) , not for sensors
            self.settings[u-1-50].UpdateRegister(self.RS485,Command,Level)
            # update the domoticz device value as well
            Devices[u].Update(nValue=Devices[u].nValue, sValue=str(Level))
      
        except Exception as e:
            Domoticz.Log("Connection failure: "+str(e))
    


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    Domoticz.Log("onCommand called")
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    """Handle Domoticz notifications to prevent 'NOT handled' warnings"""
    Domoticz.Debug(f"onNotification called: Name={Name}, Subject={Subject}, Text={Text}, Status={Status}")
    # We don't need to do anything with notifications, but this handler prevents the warning
    pass


# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Log("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Log("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Log("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Log("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Log("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Log("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Log("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Log("Device LastLevel: " + str(Devices[x].LastLevel))
    return

