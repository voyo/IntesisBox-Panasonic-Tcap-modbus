# IntesisBox-Panasonic-Tcap-modbus
IntesisBox Panasonic-Tcap over modbus, Domoticz plugin
Author: Wojtek Sawasciuk  <voyo@no-ip.pl>


    Requirements:
    1.python module minimalmodbus -> http://minimalmodbus.readthedocs.io/en/master/
        (pi@raspberrypi:~$ sudo pip3 install minimalmodbus)
    2.Communication module Modbus USB to RS485 converter module
    3.python module pyModbusTCP
    4.'something' what can act as proxy for Modbus TCP to Modbus RTU (RS-232/485) connectivity. Hardware or software solution.
      I'm using open-source mbusd (https://github.com/3cky/mbusd/ , running as docker service on my RBPI


