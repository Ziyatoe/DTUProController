# DTUProController
Hoymiles DTU-Pro  zeroexport controller for 2.gen Microinverter with serialnumber begin:
0x1020xxxxxx  #MI200,MI300
0x1021xxxxxx  #MI200,MI300
0x1040xxxxxx MI600
0x1041xxxxxx #MI500,MI600,TSUN TSOL-M800
0x1060xxxxxx MI1500
0x1061xxxxxx #MI1000,MI1200, MI1500.

Beacuse of the bugs on the Hoymiles DTU-Pro while doing zero export, I wrote this python script for controlling the Hoymiles DTU-Pro for "real" zero export.

Data Logger and zero export Controller for Hoymiles DTU-Pro / (tested with one Microinverter MI1500) series over RS485/ModbusRTU
This script controls zero export power to the grid, monitoring over mqtt/nodered for monitoring,
which can be read with excel etc...

 usage: *.py Controller=0/1 [1=controler&datalog] [0=only datalogger], Output=1/0, Limit=10-100
 
 dtupro_ctrl.py 1 1 50     ; script running as zeroexport controller with limiting the microinverter to 50%, output to the console
 
 dtupro_ctrl.py 0 1        ; script is running as datalogger, no limiting , output to the console

What do you need:
- set DTU-Pro RS485 device number to 101 or change it bellow
- set DTSU666 grid meter device number to 22 or change it bellow, (DDSU666 or whatever CHINT compatible is also ok)
- for RaspberryPi or PC get a USB/RS485 stick
- connect DTU-Pro, DTSU666 and PC over RS485 (take care of A/B)
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

