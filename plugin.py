#!/usr/bin/env python
"""
Panasonic-IntesisBox. Domoticz plugin.

Author: Wojtek Sawasciuk  <voyo@no-ip.pl>

Requirements: 
    1.python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
        (pi@raspberrypi:~$ sudo pip3 install minimalmodbus)
    2.Communication module Modbus USB to RS485 converter module
"""
"""
<plugin key="Panasonic-IntesisBox" name="Panasonic-IntesisBox" version="0.8.1" author="voyo@no-ip.pl">
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

# for TCP modbus connection
from pyModbusTCP.client import ModbusClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

class Switch:
    def __init__(self,ID,name,register,functioncode: int = 3,options=None, Used: int = 1, Description=None, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0):
        self.ID = ID
        self.name = name
#        self.type = type
#        self.Type = Type
#        self.Subtype = Subtype
#        self.Switchtype=Switchtype
        self.register = register
        self.functioncode = functioncode
        self.Used=Used
        self.nod = 0
        self.value = 0
        self.options = options if options is not None else None        
        
        self.TypeName = TypeName if TypeName is not None else ""
        self.Type = Type
        self.SubType = SubType
        self.SwitchType = SwitchType
        self.Description = Description if Description is not None else ""

        if self.ID not in Devices:
            msg = "Registering device: "+self.name+" "+str(self.ID)
            Domoticz.Log(msg)        
            if self.TypeName != "":
                 Domoticz.Log("adding Dev with TypeName, "+self.TypeName)
                 Domoticz.Device(Name=self.name, Unit=self.ID, TypeName=self.TypeName,Used=self.Used,Options=self.options,Description=self.Description).Create()
            else:
                 Domoticz.Device(Name=self.name, Unit=self.ID,Type=self.Type, Subtype=self.SubType, SwitchType=self.SwitchType, Used=self.Used,Options=self.options,Description=self.Description).Create()
                 Domoticz.Log("adding Dev with Type, "+str(self.Type))
        else:
            msg = "Device already exists: "+self.name+" "+str(self.ID)
            Domoticz.Log(msg)

    def CommandLevelConversion2data(self,command,level):
        Domoticz.Log("command2data, command:"+str(command)+" register: "+str(self.register)+" level: "+str(level) )
        if command=='On':
            return 1
        if command=='Off':
            return 0
        if self.register == 33:
            value = level
        else:          
          if command=='Set Level':
             value = int(level / 10)
        return value           
   
    def LevelValueConversion2Level(self,data):
        Domoticz.Log("value2level, data:"+str(data)+" register:"+str(self.register))   
        if self.register==0:
                if data == 0:
                    value = 'Off'
                if data == 1:
                    value = 'On'    
        if self.register==4:
                value = (data ) * 10
        else:
            value = data
            Domoticz.Log("Level value conversion - data MIGHT be not valid: "+str(data)+" register: "+str(self.register))    
        if Parameters["Mode6"] == 'Debug':                    
               Domoticz.Log("Conversion mapping from "+str(data)+" to "+str(value))
        return value



    def UpdateSettingValue(self,RS485):
        if RS485.MyMode == "minimalmodbus":
            payload = RS485.read_register(self.register,functioncode=self.functioncode)
            if self.functioncode == 3 or self.functioncode == 4:
                while True:
                    try:
                        payload = RS485.read_register(self.register,number_of_decimals=self.nod,functioncode=self.functioncode)                       
                    except Exception as e:
    #                    Domoticz.Log("Connection failure: "+str(e))
                        Domoticz.Log("Modbus connection failure")
                        Domoticz.Log("retry updating register in 2 s") 
                        sleep(2.0)
                        continue
                    break
        elif RS485.MyMode == "pymodbus":
            if self.functioncode == 3:
                 while True:
                    try:
                        payload = RS485.read_holding_registers(self.register,1,unit=1).registers[0]
                    except Exception as e:
                        Domoticz.Log("Modbus connection failure")
                        Domoticz.Log("retry updating register in 2 s") 
                        sleep(2.0)
                        continue
                    break
            elif self.functioncode == 4:
                    while True:
                        try:
                            payload = RS485.read_input_registers(self.register,1,unit=1).registers[0]
                        except Exception as e:
                            Domoticz.Log("Modbus connection failure")
                            Domoticz.Log("retry updating register in 2 s") 
                            sleep(2.0)
                            continue
                        break
        else:
            Domoticz.Log("Unknown Modbus mode")

        Domoticz.Log("Switch.UPDATUJE wartosc z rejestru: "+str(self.register)+" value: "+str(payload) )
        data = payload
# 	for devices with 'level' we need to do conversion on domoticz levels, like 0->10, 1->20, 2->30 etc
        value = self.LevelValueConversion2Level(data)
        self.value = value
        Domoticz.Log("data: "+str(data)+" value: "+str(value))
#        Devices[self.ID].sValue=str(value)
#        Domoticz.Log("nValue")
#        Devices[self.ID].nValue=int(data)
#        Domoticz.Log("Update")
#        Devices[self.ID].Update(Log=True)  # force update, even if the value has no changed.
#        Devices[self.ID].Update(0,str(data)+';0',True) # force update
#        Devices[self.ID].Update(nValue=0, sValue = "Off")
        Devices[self.ID].Update(nValue=data, sValue=str(value))
        if Parameters["Mode6"] == 'Debug':
                 Domoticz.Log("Updating switch: "+self.name+" wartosc z rejestru: "+str(data) + " , wartosc levelu: "+str(value))                 


    def UpdateRegister(self,RS485,command,level):
        if command == "Set Level":
            value = self.LevelValueConversion2Data(command,level)
        else:
            if command == "On":
                value = 1
            elif command == "Off":
                value = 0
        if Parameters["Mode6"] == 'Debug':
                Domoticz.Log("Updating register: "+str(self.register)+" with command: "+str(command)+" and level: "+str(level))

        if RS485.MyMode == "minimalmodbus":
            while True:
                try:
                    RS485.write_register(self.register,value,functioncode=self.functioncode)
                except Exception as e:
                    Domoticz.Log("Connection failure: "+str(e))
                    Domoticz.Log("retry updating register in 2 s") 
                    sleep(2.0)
                    continue
                break
        elif RS485.MyMode == "pymodbus":
             while True:
                try:
                    RS485.write_register(self.register,value,unit=1)
                except Exception as e:
                    Domoticz.Log("Connection failure: "+str(e))
                    Domoticz.Log("retry updating register in 2 s") 
                    sleep(2.0)
                    continue
                break
        else:
            Domoticz.Log("Unknown Modbus mode")
        if Parameters["Mode6"] == 'Debug':    
            Domoticz.Log("Register: "+str(self.register)+" updated with value: "+str(value))

        

class Dev:
    def __init__(self,ID,name,nod,register,functioncode: int = 3,options=None, Used: int = 1, Description=None, signed: bool = False, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0  ):
        self.ID = ID
        self.name = name
        self.TypeName = TypeName if TypeName is not None else ""
        self.Type = Type
        self.SubType = SubType
        self.SwitchType = SwitchType
        self.nod = nod
        self.value = 0
        self.signed = signed 
        self.register = register
        self.functioncode = functioncode
        self.options = options if options is not None else None
        self.Used=Used
        self.Description = Description if Description is not None else ""
        if self.ID not in Devices:
            msg = "Registering device: "+self.name+" "+str(self.ID)+" "+self.TypeName+"  Description: "+str(self.Description);
            Domoticz.Log(msg)        
            if self.TypeName != "":
                 Domoticz.Log("adding Dev with TypeName, "+self.TypeName)
                 Domoticz.Device(Name=self.name, Unit=self.ID, TypeName=self.TypeName,Used=self.Used,Options=self.options,Description=self.Description).Create()
            else:
                 Domoticz.Device(Name=self.name, Unit=self.ID,Type=self.Type, Subtype=self.SubType, Switchtype=self.SwitchType, Used=self.Used,Options=self.options,Description=self.Description).Create()
                 Domoticz.Log("adding Dev with Type, "+str(self.Type))
                      

    def UpdateSensorValue(self,RS485):
        if RS485.MyMode == "minimalmodbus":
                 Domoticz.Log("minimalmodbus")
                 if self.functioncode == 3 or self.functioncode == 4:
                     while True:
                       try:
                           payload = RS485.read_register(self.register,number_of_decimals=self.nod,functioncode=self.functioncode,signed=self.signed)
                       except Exception as e:
#                           Domoticz.Log("Connection failure: "+str(e))
                           Domoticz.Log("Modbus connection failure")
                           Domoticz.Log("retry updating register in 2 s") 
                           sleep(2.0)
                           continue
                       break        
                 Domoticz.Log("DEV.UPDATUJE wartosc z rejestru: "+str(self.register)+" value: "+str(payload)+" signed: "+str(self.signed))
                 data = payload
                 Devices[self.ID].Update(0,str(data)+';'+str(data),True) # force update, even if the voltage has no changed. 
                 if Parameters["Mode6"] == 'Debug':
                     Domoticz.Log("Device:"+self.name+" data="+str(data)+" from register: "+str(hex(self.register)) )
        elif RS485.MyMode == "pymodbus":
                Domoticz.Log("pymodbus")
                if self.functioncode == 3:
                        while True:
                            try:
                                payload = RS485.read_holding_registers(self.register,1,unit=RS485.MyUnit)
                            except Exception as e:
                                Domoticz.Log("Connection failure: "+str(e))
                                Domoticz.Log("retry updating register in 2 s") 
                                sleep(2.0)
                                continue
                            break
                elif self.functioncode == 4:
                        while True:
                            try:
                                payload = RS485.read_input_registers(self.register,1,unit=RS485.MyUnit)
                            except Exception as e:
                                Domoticz.Log("Connection failure: "+str(e))
                                Domoticz.Log("retry updating register in 2 s") 
                                sleep(2.0)
                                continue
                            break   
                data = payload.registers[0]
                Devices[self.ID].Update(0,str(data)+';'+str(data),True) # force update, even if the voltage has no changed.
                if Parameters["Mode6"] == 'Debug':
                    Domoticz.Log("Device:"+self.name+" data="+str(data)+" from register: "+str(hex(self.register)) )
        else:
                Domoticz.Log("unknown ModBus mode")
                return
        
class BasePlugin:
    def __init__(self):
        self.runInterval = 1
        self.RS485 = ""
        return

    def onStart(self):
      # debug
        if Parameters["Mode6"] == 'Debug':
            Domoticz.Debugging(1)
            DumpConfigToLog()
            self.RS485.debug = True
        if Parameters["Mode4"] == "RTU" or Parameters["Mode4"] == "ASCII":
            Domoticz.Log("Using minimalmodbus library")
            self.RS485 = minimalmodbus.Instrument(Parameters["SerialPort"], int(Parameters["Mode2"]))
            self.RS485.serial.baudrate = Parameters["Mode1"]
            self.RS485.serial.bytesize = 8
            self.RS485.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.RS485.serial.stopbits = 1
            self.RS485.serial.timeout = 1
            self.RS485.MyMode = 'minimalmodbus'
            self.RS485.mode = minimalmodbus.MODE_RTU        
        elif Parameters["Mode4"] == "TCP":
            Domoticz.Debug("TCP mode is not supported by minimalmodbus, so we use pymodbus instead")
        # TCP is not supported by minimalmodbus, so we use pymodbus
 #       c = ModbusClient(host="127.0.0.1", auto_open=True, auto_close=True)
            try: 
                Domoticz.Log("Using pymodbus, connecting to "+Parameters["Address"]+":"+Parameters["Port"]+" unit ID"+ str(DeviceID))
                self.RS485 = ModbusClient(host=Parameters["Address"], port=int(Parameters["Port"]), unit_id=DeviceID, auto_open=True, auto_close=True, timeout=2)
            except: 
                Domoticz.Log("pyMmodbus connection failure")
            self.RS485.MyMode = 'pymodbus'
        else:
            Domoticz.Log("Unknown mode: "+Parameters["Mode4"])

        devicecreated = []
        Domoticz.Log("Panasonic-IntesisBox-Modbus plugin start")


#     def __init__(self,    ID,name,nod,register,functioncode: int = 3,options=None, Used: int = 1, Description=None, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0  ):
        self.sensors = [
                 Dev(1,"outdoor_temp",0,1,functioncode=3,TypeName="Temperature",Description="Outside temperature",signed=True),
                 Dev(2,"outlet_water_temp",0,2,functioncode=3,TypeName="Temperature",Description="Outlet temperature"),
                 Dev(3,"inlet_temp",0,3,functioncode=3,TypeName="Temperature",Description="Inlet temperature"),
                 Dev(4,"tank_water_temp",0,32,functioncode=3,TypeName="Temperature",Description="Tank water temperature"),
                 Dev(5,"Tank energy consumption",0,45,functioncode=3,TypeName="kWh",Description="Tank mode energy consumption"),
                 Dev(6,"Heat energy consumption",0,46,functioncode=3,TypeName="kWh",Description="Heat mode energy consumption"),
                 Dev(7,"Cool energy consumption",0,47,functioncode=3,TypeName="kWh",Description="Cool mode energy consumption"),
                 Dev(8,"Tank Energy Generation",0,187,functioncode=3,TypeName="kWh",Description="Tank mode energy consumption"),
                 Dev(9,"Heat Energy Generation",0,188,functioncode=3,TypeName="kWh",Description="Heat mode energy consumption"),
                 Dev(10,"Cool Energy Generation",0,189,functioncode=3,TypeName="kWh",Description="Cool mode energy consumption"),
                 Dev(11,"Current error status",0,70,functioncode=3,TypeName="Alert",Description="Current error status")
            ]
#   def __init__(self,    ID,name,register,functioncode: int = 3,options=None, Used: int = 1):
        self.settings = [
                 Switch(51,"System On/Off",0,functioncode=3),
                 Switch(52,"OperatingMode",4,functioncode=3,Type=244,SwitchType=18,SubType=0,options={"LevelActions": "|act1| |act2|","LevelNames": "|" + "Heat" + "|" + "Heat Tank" + "|" + "Tank"+ "|" + "Cool Tank"+ "|" + "Cool"+ "|" + "Auto"+ "|" + "Auto Tank"+ "|" + "Auto Heat"+ "|" + "Auto Heat Tank"+ "|" + "Auto Cool"+ "|" + "Auto Cool Tank", "LevelOffHidden": "true", "SelectorStyle": "1"}),
                 Switch(53,"Tank heater",34,functioncode=3),
                 Switch(54,"Tank set temp",33,functioncode=3,Description="Tank set temperature point", Type=242 , SubType=1),
                 Switch(55,"Valve direction",85,functioncode=3,Description="Valve direction",Type=244,SwitchType=18,SubType=62,options={"LevelActions": "|room| |tank|","LevelNames": "|" + "Room" + "|" + "Tank", "LevelOffHidden": "true", "SelectorStyle": "1"})

  
                 
#   def __init__(self,ID,name,register,functioncode: int = 3,options=None, Used: int = 1, Description=None, TypeName=None,Type: int = 0, SubType:int = 0 , SwitchType:int = 0):
#Domoticz.Device(Name="Set Temp", Unit=5, Type=242, Subtype=1, Image=16, Used=1).Create()

                  ]



     #   Domoticz.Device(Name=self.name, Unit=self.ID,
     #       Type=self.Type, Subtype=self.SubType, Switchtype=self.SwitchType, Used=self.Used,Options=self.options,Description=self.Description).Create()

# create exceptional device
#        Domoticz.Device(Name="Tank Setpoint",
#                            Unit=55,
#                            Image=15,
#                            Type=242,
#                            Subtype=1,
#                            Used=1).Create()

    def onStop(self):
        Domoticz.Log("Panasonic-IntesisBox Modbus plugin stop")

    def onHeartbeat(self):
        self.runInterval -= 1
        if self.runInterval <= 0:
            for i in self.sensors:
                try:
                         # Get data from modbus
                        Domoticz.Log("Getting data from modbus for device:"+i.name+" ID:"+str(i.ID))
                        self.sensors[i.ID-1].UpdateSensorValue(self.RS485)
                except Exception as e:
                        Domoticz.Log("Update failure: "+str(e))
                else:
                        if Parameters["Mode6"] == 'Debug':
                            Domoticz.Log("in HeartBeat "+i.name+": "+format(i.value))
            self.runInterval = int(Parameters["Mode3"])

            for i in self.settings:
                l = len(self.settings)
                dev_len=len(self.sensors)
                try:
                         # Get data from modbus
                        Domoticz.Log("Getting data from modbus for device:"+i.name+" ID:"+str(i.ID))
                        self.settings[i.ID-1-50].UpdateSettingValue(self.RS485)
                except Exception as e:
                        Domoticz.Log("Update failure: "+str(e))
                else:
                        if Parameters["Mode6"] == 'Debug':
                            Domoticz.Log("in HeartBeat "+i.name+": "+format(i.value))
            self.runInterval = int(Parameters["Mode3"]) 

            # update exceptional device, get data from modbus and update domoticz device
            # Tank water setpoint temperature
 #           payload = self.RS485.read_register(33,0,3)
 #           Domoticz.Log("Getting data from modbus for device: Tank water setpoint temperature ID: 55 ,value: " + str(payload))
 #           Devices[55].Update(0,str(payload)+';0',True) 




    def onCommand(self, u, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(u) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        if Parameters["Mode6"] == 'Debug':
                Domoticz.Log(str(Devices[u].Name) + ": onCommand called: Parameter '" + str(Command) + "', Level: " + str(Level))
        dev_len=len(self.sensors)
        try:
            Domoticz.Log("onCommand: Parameter " + str(u-1-50) )
            self.settings[u-1-50].UpdateRegister(self.RS485,Command,Level)
        except Exception as e:
            Domoticz.Log("Connection failure: "+str(e));
    


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
    Domoticz.Log("onHeartbeat called")
    _plugin.onHeartbeat()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    Domoticz.Log("onCommand called")
    _plugin.onCommand(Unit, Command, Level, Hue)

   

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

