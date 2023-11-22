# DTUProController
Hoymiles DTU-Pro  zeroexport controller for 6 Microinverter 
Beacuse of the bugs on the Hoymiles DTU-Pro while doing zero export, I wrote this python script for controlling the Hoymiles DTU-Pro for "real" zero export.

Data Logger and zero export Controller for Hoymiles DTU-Pro / (tested with one Microinverter MI1500) series over RS485/ModbusRTU
This script controls zero export power to the grid, monitoring over mqtt/nodered for monitoring,
which can be read with excel etc...

 usage: *.py Controller=0/1 [1=controler&datalog] [0=only datalogger], Output=1/0, Limit=10-100
 
 dtupro_ctrl.py 1 1 50     ; script running as zeroexport controller with limiting the microinverter to 50%, output to the console
 
 dtupro_ctrl.py 0 1        ; script is running as datalogger, no limiting , output to the console

What do you need:
- SET !! DTU-Pro as Remote Control/Modbus Protocol
- SET !! DTU-Pro RS485 device number to 101 or change it in script 
- SET !! DTSU666 grid meter device number to 22 or change it in script (DDSU666 or whatever CHINT compatible is also ok)
- for RaspberryPi or PC get a USB/RS485 stick
- connect DTU-Pro, DTSU666 and PC over RS485 twisted pair (take care of A/B)
- install python3
- install pymodbus
- install MQTT mosquitto
- install Node-Red, if you want to use my Node-red functions for data-graphics
- CONFIGURE "dtupro_ctrl.py" in script
- start the script in terminal

Please, place any issues here:
https://github.com/Ziyatoe/DTUProController/issues

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the License,
or any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this program.
If not, see <https://www.gnu.org/licenses/>

NO COMMERCIAL USE !!

Copyright 2022 Z.TOe

If you do any modification to this python script please SHARE with me, thank you!!!!-

