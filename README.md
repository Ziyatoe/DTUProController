# DTUProController
Hoymiles DTU-Pro controller for zero export

Beacuse of the bugs on Hoymiles DTU-Pro while doing zero export, I wrote this python script for controlling the Hoymiles DTU-Pro for grid zero export.

'''

Data Logger and zero export Controller for Hoymiles DTU-Pro / one Microinverter MI1500 series over RS485/ModbusRTU
This script controls zero export power to the grid and creates a daily csv-file for monitoring,
which can be read with excel etc...

usage this.py 0 or 1 > [1=controller&datalogger] [0=only datalogger]

What you need are:
- set DTU-Pro RS485 device number to 101 or change it bellow
- set DTSU666 grid meter device number to 22 or change it bellow, (DDSU666 or whatever CHINT compatible is also ok)
- for RaspberryPi or PC get a USB/RS485 stick
- connect DTU-Pro, DTSU666 and PC over RS485 (take care of A/B)
- install python3
- install pymodbus
- install MQTT mosquitto
- install Node-Red
- configure this script below
- start script in terminal

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the License,
or any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with this program.
If not, see <https://www.gnu.org/licenses/>

NO COMMERCIAL USE !!

Copyright 2022 Z.TOe toedci@gmail.com
------------------------------------------------------------------------------------------------------------------------
If you do any modification to this python script please SHARE with me, thank you!!!!
------------------------------------------------------------------------------------------------------------------------
'''
