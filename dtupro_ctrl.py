'''

Data Logger and zero export Controller for Hoymiles DTU-Pro / max. 6 Microinverter MH/MI series or TSUN over RS485/ModbusRTU
This script controls zero export power to the grid and publishes data to mqtt for monitoring,
which can be read for excel etc...

usage this.py 0 or 1 > [1=controller&datalogger] [0=only datalogger] [% limit]

What you need are:
- set DTU-Pro RS485 device number to 101 or change it bellow
- set DTSU666 grid meter device number to 22 or change it bellow, (DDSU666 or whatever CHINT compatible is also ok)
- for RaspberryPi or PC get a USB/RS485 stick
- connect DTU-Pro, DTSU666 and PC over RS485 (take care of A/B)
- install python3
- install pymodbus
- install MQTT mosquitto
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

# import os
from datetime import datetime
# from datetime import date
# from subprocess import call
import errno
import sys
from pymodbus.client.sync import ModbusSerialClient
# from pymodbus.client import ModbusSerialClient  for newer pymodbus   !!!!!!!!!!!!!!!!!!!
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
# from pymodbus.payload import BinaryPayloadBuilder
# from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
import time
import json

# ###################### CONFIGURATION #################################################################################
VERSION = "0.4.7"
# ::::::::::::
# clientDTU = ModbusTcpClient('192.168.2.100', 502)   also possible
clientDTU = ModbusSerialClient(
   method='rtu',
   port='/dev/ttyUSB0',
   baudrate=9600,
   timeout=8,
   parity='N',
   stopbits=1,
   bytesize=8
)
DTU_DEV_NR = 101  # Hoymiles DTU-Pro Modbus device number
# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
clientDTSU = ModbusSerialClient(
   method='rtu',
   port='/dev/ttyUSB0',
   baudrate=9600,
   timeout=8,
   parity='N',
   stopbits=1,
   bytesize=8
)
DTSU_DEV_NR = 22        # Chint DTSU666 grid meter Modbus device number


NrOfInv   = 6           ## number of inverters, change if you want more <<<<<<<<<<<<<<<<<<<<<<<<<<<
InvIdPowr = [[0, 0.0], [0, 0.0], [0, 0.0], [0, 0.0], [0, 0.0], [0, 0.0]] #change if you want more depending on NrOfInv
# inverter [[Sernr, totalpower],,,]
# InvIdPowr[0][0]= 0x106163707160   1.inverter
# InvIdPowr[0][1]= total produced PV power of this inverter

MINPERCENT = 10         #in %, MI series min 10%, HM series min.2% to be set 
EXPORT_PLUS = 1         # gridmeter direction normal (-)=0 , or (+)=1
RWCOUNTER = 4           # how many times do we try to read or write if not successful before
doZEROSensivity = 16    # watt, do_zeroexort if more than this power needed
MAXPOWER  = 2000        # Watt, total all inverters   to be SET !!
# Limit = 10            # PowerLimit in % of Maxpower 10% at begin
SLEEP = 30              # polling tact
broker = "127.0.0.1"    #mqtt broker
Output = True           # False = disable all print commands

# ###################### END CONFIGURATION #############################################################################
NRofPORTS = 4           # can be less than 4, will be set in loop depend on iverter modell
BIT8_INT = 0
BIT8_UINT = 1
BIT16_INT = 2
BIT16_UINT = 3
BIT32_INT = 4
BIT32_UINT = 5
BIT64_INT = 6
BIT64_UINT = 7
BIT32_FLOAT = 8

TABS = "\t\t\t\t"
WAIT = 5                # wait sek. on each read/write
BaseDataReg = 0x1000
InvAdrOffset = 0x28 * 4
# DTUDataRegAdr = [0x1000, 0x1028, 0x1050, 0x1078]  # base address-list for the first inverter each port1-4
                                                    # will change for each inverter

MainOnOff = 0x9D9C      # DTU_Pro main register, for all inverter/ports, 0x9D9C or 0xC000
MainLimitRegs = 0x9D9D  # DTU_Pro limit register, for all inverter/ports,

ZeroExportController = 1  # running 1=controller 0=only as datalogger
SolarP = 0
mqttclient = mqtt.Client("XX")

DtuMiPvData = [0] * 4  # DtuMiPvData[port].registers[1] is a list!! 2 dim array

Mi1CH = 1 #Micrinverter with 1 port
Mi2CH = 2 #Micrinverter with 2 ports
Mi4CH = 3 #Micrinverter with 4 ports
MItype = [["not known", 0, 0], ["Mi1CH", 1, 375], ["Mi2CH", 2, 375], ["Mi4CH", 4, 375]]
boldon = "" #"\033[1m"
boldoff ="" #"\033[0m"


def GetMIModel(sn):
   # ---------------------------------------------------------------------------------------
   Mi = (sn >> 32)
   if Mi == 0x1020:  return Mi1CH  # MI200,MI300
   if Mi == 0x1021:  return Mi1CH  # MI200,MI300
   if Mi == 0x1121:  return Mi1CH  # HM200,HM300

   if Mi == 0x1040:  return Mi2CH
   if Mi == 0x1041:  return Mi2CH  # MI500,MI600,TSUN TSOL-M800
   if Mi == 0x1141:  return Mi2CH  # HM500,HM600

   if Mi == 0x1060:  return Mi4CH
   if Mi == 0x1061:  return Mi4CH  # MI1000,MI1200, MI1500.
   if Mi == 0x1161:  return Mi4CH  # HM1000,HM1200, HM1500.
   return 0
def read_sernr():
   # ------------------------------------------------------------------------------------------------------------------
   global InvIdPowr, NrOfInv

   if not clientDTU.connect:
      ststxt = "read_sernr: Error connecting DTU"
      if Output: print()
      mqttclient.publish("DTUStatus", ststxt)
      return 0
   # DTU serial in Device SN Register List at 0x2000
   result = clientDTU.read_holding_registers(address=0x2000, count=6, unit=DTU_DEV_NR)
   if not result.isError():
      decoder = BinaryPayloadDecoder.fromRegisters(result.registers, Endian.Big)
      DtuId = decoder.decode_64bit_uint() >> 16
      if Output: print("DTUSerialNr:", hex(int(DtuId)), "\tDevice SN Register List (10F8xxxxxxxx)")
   else:
      ststxt = "Error connecting DTU sernr at 0x2000"
      if Output: print(ststxt)
      mqttclient.publish("DTUStatus", ststxt)
      return 0
   time.sleep(5)
   # Mi lists Device SN Register List at 0x2056
   i = 0
   while i < NrOfInv:
      adr = 0x2056 + i * 6
      result = clientDTU.read_holding_registers(address=adr, count=5, unit=DTU_DEV_NR)
      if not result.isError():
         decoder = BinaryPayloadDecoder.fromRegisters(result.registers, Endian.Big)
         InvIdPowr[i][0] = decoder.decode_64bit_uint() >> 16
         if InvIdPowr[i][0] == 0:  # end of list with invertersernr
            if Output: print("Nr of Inv:", i)
            NrOfInv = i
            break
         # if Output: print("MISerialNr :", hex(int(InvIdPowr[i][0])), "\tDevice SN Register List", hex(adr),i)

         if Output: print("MISerialNr :", hex(int(InvIdPowr[i][0])), "\tModel:", MItype[GetMIModel(InvIdPowr[i][0])][0],
                          " Ports:", MItype[GetMIModel(sn=InvIdPowr[i][0])][1],
                          " Power/Port:", MItype[GetMIModel(sn=InvIdPowr[i][0])][2])
      else:

         if Output: print("Error connecting DTU, Mi sernr at 0x2056")
         return 0
      i += 1
      time.sleep(3)

   # if Output:
   #     for i in range(NrOfInv):
   #         print (hex(InvIdPowr[i][0]))

   return DtuId
# ------------------------------------------------------------------------------------------------------------------
def template():
   # ------------------------------------------------------------------------------------------------------------------
   a = 1#just for def template, not used
# ------------------------------------------------------------------------------------------------------------------
def readMiDataRegs(DtuDataRegs):
   # ------------------------------------------------------------------------------------------------------------------
   global DtuMiPvData
   i = 0
   if Output: print("[readMiDataRegs] read DTU-Regs ")
   time.sleep(2)

   for port in range(NRofPORTS):
      adr_begin = DtuDataRegs[port]  # hex(0x1000+4*0x28) next inverter
      # todo !! achtung es wird immer 2byte register gelesen darum count=20!!!!!!!!! todo !!
      DtuMiPvData[port] = clientDTU.read_holding_registers(address=adr_begin, count=20, unit=DTU_DEV_NR)
      if DtuMiPvData[port].isError():
         if Output: print("[readMiDataRegs] Error Port:", port, " ", hex(adr_begin))
      else:
         i += 1
         # print("Port:",port," ",hex(adr_begin))
         # for k in range(20):
         #     print(hex(DtuMiPvData[port].registers[k]))
         # print(DtuMiPvData[port].registers[0]," ",DtuMiPvData[port].registers[1]," ",DtuMiPvData[port].registers[2]," ",DtuMiPvData[port].registers[3])
      time.sleep(2)
   if i < NRofPORTS:
      ststxt = "[readMiDataRegs]cant read DTU-Regs"
      if Output: print(ststxt)
      mqttclient.publish("DTUStatus", ststxt)
      return 0
   else:
      if Output: print("[readMiDataRegs] readed ")
      return 1
# ---readMiDataRegs---------------------------------------------------------------------------------------------------------------
def readFromDataRegList(my_client, dtuDataRegs, adr, regs_count, dev_nr, number): #todo check regs_count
   # ------------------------------------------------------------------------------------------------------------------
   global DtuMiPvData
   my_result = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
   i = value = r_result = 0

   # todo weil wir immer 2byte register haben, können kein 1 byte gelesen werden, darum ist der divider=2
   # todo für 1 byte, 2byte lesen dann mit and(&) 0xFF

   while not r_result and i < RWCOUNTER:
      if dev_nr == DTU_DEV_NR:
         # read registers from DtuMiPvData[], all registers are readed before
         for i in range(int(regs_count / 2)):
            #if Output : print("readFromDataRegList i:",i," adr:",hex(adr)," idx:",hex(int((adr - 0x1000+i)/2)))
            if dtuDataRegs[0] <= adr < dtuDataRegs[1]:  # PV1,
               my_result[i] = DtuMiPvData[0].registers[int((adr - dtuDataRegs[0]) / 2) + i]
               # print( "PV1 cnt:",i," idx", hex(int((adr - 0x1000)/2+i))," val ",hex(v))
            if NRofPORTS == 1: #check the  NRofPORTS
               break          #changed for 0.4.6
            if dtuDataRegs[1] <= adr < dtuDataRegs[2]:
               my_result[i] = DtuMiPvData[1].registers[int((adr - dtuDataRegs[1] + i) / 2)]  # PV2
               # print("PV2 ", hex(adr - 0x1028)," val ",DtuMiPvData[1].registers[int((adr - 0x1028+i)/2)])
            if NRofPORTS == 2: #check the  NRofPORTS
               break          #changed for 0.4.6
            if dtuDataRegs[2] <= adr < dtuDataRegs[3]:
               my_result[i] = DtuMiPvData[2].registers[int((adr - dtuDataRegs[2] + i) / 2)]  # PV3
               # print("PV3 ", hex(adr - 0x1050)," val ",DtuMiPvData[2].registers[int((adr - 0x1050+i)/2)])
            if dtuDataRegs[3] <= adr:
               my_result[i] = DtuMiPvData[3].registers[int((adr - dtuDataRegs[3] + i) / 2)]  # PV4
               # print("PV4 ", hex(adr - 0x1078)," val ",DtuMiPvData[3].registers[int((adr - 0x1078+i)/2)])

         value = my_result
         # if Output: print( "value---------------------")
         # for k in range(int(regs_count/2)):
         # print(hex(value[k]))
         r_result = 1
      else:  # DTSU
         r_result = my_client.read_holding_registers(address=adr, count=regs_count, unit=dev_nr)
         if r_result.isError():
            r_result = 0
            i += 1
         else:
            value = r_result.registers
   if value:
      dodecode = BinaryPayloadDecoder.fromRegisters(value, Endian.Big)
      if number == BIT8_INT:  return dodecode.decode_8bit_int()
      if number == BIT8_UINT: return dodecode.decode_8bit_uint()
      if number == BIT16_INT: return dodecode.decode_16bit_int()
      if number == BIT16_UINT: return dodecode.decode_16bit_uint()
      if number == BIT32_INT: return dodecode.decode_32bit_int()
      if number == BIT32_UINT: return dodecode.decode_32bit_uint()
      if number == BIT64_INT: return dodecode.decode_64bit_int()
      if number == BIT64_UINT: return dodecode.decode_64bit_uint()
      if number == BIT32_FLOAT: return dodecode.decode_32bit_float()
   else:
      ststxt = "error readFromDataRegList"
      if Output: print(TABS + ststxt)
      # ----mqtt
      mqttclient.publish("DTUStatus", ststxt)
      # ----mqtt
      return 0
# --readFromDataRegList-----------------------------------------------------------------------------------------------
def dtu_write(reg_adr, towrite, dev_nr=DTU_DEV_NR):
   # ------------------------------------------------------------------------------------------------------------------
   answer = i = 0
   while not answer and i < RWCOUNTER:
      time.sleep(WAIT)  # sattle down a bit
      if Output: print(TABS + "writing DTU", i + 1, "time", hex(reg_adr), towrite, dev_nr)
      answer = clientDTU.write_register(address=reg_adr, value=towrite, count=1, unit=dev_nr)
      if answer.isError():
         answer = 0
         i += 1
   if answer:
      if Output: print(TABS + "DTU writeOK", answer)
      return 1
   else:
      ststxt = "DTU write error!!"
      if Output: print(TABS, ststxt, hex(reg_adr), answer)
      # ----mqtt
      mqttclient.publish("DTUStatus", ststxt)
      # ----mqtt
      return 0
# --dtu_write-----------------------------------------------------------------------------------------------------------
# def set_micro_on():
#     # ------------------------------------------------------------------------------------------------------------------
#     global OldLimit
#     if clientDTU.connect():
#         if Output: print("[set_micro_on]all inverter set ON ")
#         if not(dtu_write(MainOnOff, 1, DTU_DEV_NR)):  # power on,     main on/off address 0x9D9D 0xC001
#             return 0
#         # TODO : maybe we don't need it, since inverter ON sets the limit 100% ???
#         if not (dtu_write(MainLimitRegs, Limit, DTU_DEV_NR)):   # main limit address 0x9D9D 0xC001
#             return 0
#         OldLimit = Limit
#         if Output: print("[set_micro_on]wait.. ")
#
#         #mqttclient.publish("Limiting", Limit)
#
#         return 1
#     else:
#         if Output: print("DTU not connected!!")
#         # ----mqtt
#         mqttclient.publish("DTUStatus", "error set_micro_on")
#         return 0
#         # ----mqtt
#
# # --set_micro_on--------------------------------------------------------------------------------------------------------

def mqtt_on_connect(client, userdata, flags, rc):
   # -------------------------------------------------inverter-----------------------------------------------------------------
   if rc == 0:
      client.connected_flag = True  # set flag
      if Output: print("MQTT:connected")
   else:
      if Output: print("Bad connection Returned code=", rc)
      client.bad_connection_flag = True
# -mqtt_on_connect------------------------------------------------------------------------------------------------------
def setup_mqtt():
   # ------------------------------------------------------------------------------------------------------------------
   global mqttclient

   broker = "127.0.0.1"
   mqtt.Client.connected_flag = False
   mqtt.Client.bad_connection_flag = False
   mqttclient = mqtt.Client("ToeEv")
   mqttclient.on_connect = mqtt_on_connect  # bind call back function
   mqttclient.loop_start()
   if Output: print("MQTT:Connecting to broker ", broker)
   # res=mqttclient.connect("mqtt.eclipseprojects.io", 1883, 60)
   mqttclient.connect(broker, 1883, 60, "127.0.0.1")
   while not mqttclient.connected_flag and not mqttclient.bad_connection_flag:  # wait in loop
      if Output: print("MQTT:wait loop")
      time.sleep(1)
   if mqttclient.bad_connection_flag:
      mqttclient.loop_stop()  # Stop loop
      sys.exit(sys.exit(errno.EACCES))
   mqttclient.loop_stop()
# -setup_mqtt-----------------------------------------------------------------------------------------------------------
def setup_things():
   global Output,ZeroExportController
   Usage = "usage: dtupro_ctrl.py [1=controller&datalogger, 0=only datalogger] [Output=1/0] [Limit=10..100%]"
   if len(sys.argv) < 3:
      if Output: print("parameter error!!")
      if Output: print(Usage)
      sys.exit(errno.EACCES)  # exit

   if not (0 <= int(sys.argv[1]) <= 1):
      if Output: print(Usage)
      sys.exit(errno.EACCES)
   else:
      ZeroExportController = int(sys.argv[1])  # running as zero export controller

   if 0 <= int(sys.argv[2]) <= 1:  # print output
      if int(sys.argv[2]) == 1:
         Output = 1
      else:
         Output = 0
   else:
      if Output: print(Usage)
      sys.exit(errno.EACCES)

   if Output: print("DTU-Pro RS485/ModbusDTU zero export controller. Version", VERSION)

   if len(sys.argv) == 4:
      if 10 <= int(sys.argv[3]) <= 100:
         Limit = int(sys.argv[3])
         Old_Limit = Limit
      if Output: print("Limit:", Limit, " OldLimit:", Old_Limit)
   # ----mqtt
   setup_mqtt()
   # # ----mqtt
   mqttclient.publish("DTUStatus", "running")
   # # ----mqtt
   return Limit, Old_Limit
# setup_things ---------------------------------------------------------------------------------------------------------
class DTUCtrl():
   # =======================================================================================================================
   global InvIdPowr
   global Output

   zCounter = 0
   OldLimit = 0
   Limit = 0
   jsonstr = "{"  # initialise json jsonstr
   invPortSts = 0;

   def doZeroExport(self, GridP, SolarP, ZEROSensivity):
      # --------------------------------------------------------------------------------------------
      #this is very tricky, because of the total power and min. power, should be fine tuned for every system
      # todo SolarP > summe of InvIdPowr[all inverters][1]
      if Output: print("[doZeroExport]", SolarP, self.OldLimit, ZEROSensivity)
      Limit10P = 125  #watt, change to MINPERCENT% if below this
      Limit11P = 170  #watt, over this, it will be fine limiting, +/- 1 watt ????????????????
      OnePcnt = int(MAXPOWER / 100)  # is watt

      # be carefully with the export power direction on grid meter
      #-----------------------------------------------------------
      if EXPORT_PLUS:#here is the export to grid as positive number of watt
         to_correct_soll = SolarP + (GridP * -1)
      else:
         to_correct_soll = SolarP + GridP

      #    consum_ist = abs(GridPower) + SolarP
      now = datetime.now()
      if now.hour >= 16:  # after 16 oclock no MINPERCENT%
         Limit10P = 1
         if Output: print(TABS + "its ", now.hour, " oclock!")

      if to_correct_soll <= Limit10P:
         self.Limit = MINPERCENT
         if Output: print(TABS + "under 10P Limit %:", self.Limit)
      else:
         if Limit10P < to_correct_soll <= Limit11P:
            self.Limit = 11
            if Output: print(TABS + "under 11P Limit %:", self.Limit)
         else:
            self.Limit = int(to_correct_soll * 100 / MAXPOWER)
            if Output: print(TABS + "Limit calculated %:", self.Limit)
            if GridP > ZEROSensivity:  # >16 watt, es wird exportiert, zu viel produktion
               if ((self.OldLimit > 11) and (self.Limit >= self.OldLimit)):  # todo.........
                  self.Limit = self.OldLimit - 1  # int(abs(GridPower) / OnePcnt)
                  if Output: print(TABS + "too much \033[1m Limit is", self.Limit, "old ", self.OldLimit)
            else:
               if GridP < -1 * (ZEROSensivity):  # < -16 watt, es wird importiert, zu wenig produktion
                  if ((self.OldLimit < 99) and (self.Limit <= self.OldLimit)):
                     self.Limit = self.OldLimit + 1  # int(abs(GridPower) / OnePcnt)
                     if Output: print(TABS + "zu wenig \033[1m Limit is", self.Limit, "old ", self.OldLimit)
            # fine tuning-----------------
            if (self.Limit > 99):
               self.Limit = 100
            if (self.Limit < MINPERCENT):
               self.Limit = MINPERCENT

      if (self.Limit != self.OldLimit) or (self.zCounter > 10):
         if Output: print(TABS + "Limiting\033[1m new", self.Limit, "% old", self.OldLimit, "%\033[0m target",
                          "%.1f" % to_correct_soll)
         # ----mqtt
         # mqttclient.publish("Limiting", Limit)
         # ----mqtt
         r = dtu_write(MainLimitRegs, self.Limit)

         if not r:
            ststxt = "error do_zero_export"
            if Output: print(ststxt, r)
            # ----mqtt
            mqttclient.publish("DTUStatus", ststxt)
            # ----mqtt
         else:
            self.OldLimit = self.Limit
         self.zCounter = 0
      else:
         if Output: print(TABS + "ZeroCounter \033[1m", self.zCounter, " Limit is", self.Limit, "%\033[0m target",
                          "%.1f" % to_correct_soll)
         self.zCounter += 1
   # doZeroExport -----------------------------------------------------------------------------------------------------
   def getData(self, DataRegAdr, invNumber, anzPorts, invsrnr):
   # ------------------------------------------------------------------------------
      boldon = "\033[1m"
      boldoff = "\033[0m"

      InvIdPowr[invNumber][1] = 0  # total power for this inverter
      while not (readMiDataRegs(DataRegAdr)):  # read all data from DTU at once, tries forever
         if Output: print('[DtuDtsuCtrl]Cant read DTU All Registers!!')
         time.sleep(3)

      with open("./dtudtsuregister.json") as txtfile:
         regsFromJson = json.loads(txtfile.read())

      for port in range(anzPorts):
         for parameter in regsFromJson:
            for item in parameter["items"]:
               title = item["title"]
               ratio = item["ratio"]
               unit = item["unit"]
               count = item["count"]
               nrtype = item["nrtype"]
               # regsadr=item["adr"]
               if title != "end":  # begin port x data
                  regsadr = int(item["adr"], 16)  # read only offset adr (is hex str) from json!!
                  result = 0
                  #            for register in item["registers"]:

                  # read data from register dtu
                  if parameter["directory"] == "solar":
                     regsadr = DataRegAdr[port] + regsadr
                     if ratio > 1:  # wenn result= int 1, dann ratio, result wird float!!
                        result = readFromDataRegList(clientDTU, DataRegAdr, adr=regsadr, regs_count=count,
                                                     dev_nr=DTU_DEV_NR, number=nrtype) / ratio
                     else:  # wenn result= int 0, dann kein ratio, sonst wirds float!!
                        result = readFromDataRegList(clientDTU, DataRegAdr, adr=regsadr, regs_count=count,
                                                     dev_nr=DTU_DEV_NR, number=nrtype)

                     if title == "INVSNR":  # inv srnr  0x1061637
                        #                         0xc10616370716002
                        # todo InvSERnr vom 1 port nehmen, bug in dtupro mit srnr
                        # if Output: print(parameter["directory"], title, hex(result),"\t", hex(regsadr))
                        # InvSERnr = (int(result) >> 8) & 0x0FFFFFFFFFFFF   #last byte is portnr!!!
                        #InvSERnr = (int(result) & 0x0FFFFFFFFFFFF00) >> 8  # last byte is portnr!!! todo bug ???
                        InvSERnr=invsrnr
                        if Output: print(parameter["directory"], boldon, title, hex(InvSERnr),
                                         boldoff)  # ,"-------------------------------\t", hex(regsadr))

                        # self.jsonstr = self.jsonstr + "\"" + title + "(" + unit + ")" + "\":\"" + hex(InvSERnr) + "\","
                        self.jsonstr = self.jsonstr + "\"" + title + "\":\"" + hex(InvSERnr) + "\","
                     else:
                        if title == "PortNR":
                           result = int(result) & 0xFF
                           PortNummer = result
                           if Output: print(parameter["directory"], boldon, title, PortNummer, boldoff, "\t",
                                            hex(regsadr))
                        else:
                           if Output: print(parameter["directory"], title, "\t", round(result, 1), unit)
                           # ,"\t\t\t", nrtype ,count, ratio,hex(regsadr))
                        # self.jsonstr = self.jsonstr + "\"" + title + "(" + unit + ")" + "\":" + str(round(result,1)) + ","
                        self.jsonstr = self.jsonstr + "\"" + title + "\":" + str(round(result, 1)) + ","

                     if title == "P_DC":
                        InvIdPowr[invNumber][1] = InvIdPowr[invNumber][1] + round(result, 1)  #

                     if title == "STS_DC" and result > 0 and result <= 8:
                        self.invPortSts = self.invPortSts + result

               else:  # title="end" end of port x data----
                  self.jsonstr = self.jsonstr + '"Limit":"' + str(self.Limit) + '",'
                  self.jsonstr = self.jsonstr + '"date":"' + datetime.now().strftime('%d-%m-%y') + '",'
                  self.jsonstr = self.jsonstr + '"time":"' + datetime.now().strftime('%H:%M:%S') + '",'
                  self.jsonstr = self.jsonstr[:-1] + "}"  # endof jsonstr
                  mqttclient.publish(("DTUPRO" + "/" + hex(invsrnr) + "/" + str(PortNummer)),
                                     self.jsonstr)  # invsrnr ist aus sernr register
                  # todo if Output: print(self.jsonstr)
                  self.jsonstr = "{"  # initialise next jsonstr for next port

      if Output: print("[getData]>>>>>>>> this inverter:", hex(invsrnr), " total ", round(InvIdPowr[invNumber][1], 1),
                       " W")
      return 1
   # def getData-------------------------------------------------------------------------------------------------------
# DTUCtrl===============================================================================================================
class DTSUCtrl():
   # =======================================================================================================================
   global Output
   GridP = 0
   jsonstr = "{"  # initialise json jsonstr

   def getData(self):  # ------------------------------------------------------------------------------
      self.GridP = 0
      self.jsonstr = "{"  # initialise next jsonstr for next port
      with open("./dtudtsuregister.json") as txtfile:
         regsFromJson = json.loads(txtfile.read())

      for parameter in regsFromJson:
         for item in parameter["items"]:
            title = item["title"]
            ratio = item["ratio"]
            unit = item["unit"]
            count = item["count"]
            nrtype = item["nrtype"]
            regsadr = item["adr"]
            if title != "end":  # begin  data
               regsadr = int(item["adr"], 16)
               result = 0
               #            for register in item["registers"]:
               # read data from register dtsu "directory": "grid"
               if parameter["directory"] == "grid":
                  result = readFromDataRegList(clientDTSU, 0, adr=regsadr, regs_count=count, dev_nr=DTSU_DEV_NR,
                                               number=nrtype) / ratio
                  # [end]read data from register dtu&dtsu
                  if Output: print(parameter["directory"], title, "\t", round(result, 1), unit)
                  # , "\t\t\t", nrtype, count, ratio, hex(regsadr))
                  self.jsonstr = self.jsonstr + "\"" + title + "\":" + str(round(result, 1)) + ","
               if title == "P_ACtot":
                  self.GridP = result
                  # print("GridP:",self.GridP)
            else:  # title="end" end of  data----
               self.jsonstr = self.jsonstr + '"date":"' + datetime.now().strftime('%d-%m-%y') + '",'
               self.jsonstr = self.jsonstr + '"time":"' + datetime.now().strftime('%H:%M:%S') + '",'
               self.jsonstr = self.jsonstr[:-1] + "}"  # endof jsonstr
               mqttclient.publish("DTSU666" + "/1/", self.jsonstr)
               # todo if Output: print(self.jsonstr)

      return self.GridP
   # def getData-------------------------------------------------------------------------------------------------------
# DTSUCtrl==============================================================================================================

if __name__ == "__main__":
   # main -------------------------------------------------------------------------------------------------------------

   setupresult = setup_things()

   while not (clientDTU.connect and clientDTSU.connect):
      if Output: print("main: Error connecting client DTU or DTSU")
      # time.sleep(5)

   while not (read_sernr()):
      time.sleep(3)
      # if 1: #ZeroExportController:
      #     while not (set_micro_on()):  # set ON and power down to MINPERCENT%, is option
      #         time.sleep(SLEEP)
   dtu = DTUCtrl()
   dtsu = DTSUCtrl()
   while True:  # todo cover the loop with try: and except:keyboard interrupt
      while not mqttclient.connected_flag and not mqttclient.bad_connection_flag:  # wait in loop
         if Output: print("MQTT:wait loop")
         time.sleep(2)
         mqttclient.connect(broker, 1883, 60, "127.0.0.1")

      SolarP = 0  # summ of all inverter DC Power
      BaseDataReg = 0x1000
      # ------------------------------------------------------------------------------
      for inv in range(NrOfInv):  # [begin]get all inverter DC data
         DTUDataReg = [0xffff, 0xffff, 0xffff, 0xffff] #will be filled below  with only used port basisregs
         NRofPORTS = MItype[GetMIModel(sn=InvIdPowr[inv][0])][1]
         offset = inv * (0x28 * NRofPORTS)

         for portnr in range(NRofPORTS):
            portreg = portnr * 0x28  # pointer
            # DTUDataReg are = [0x1000 + offset, 0x1028 + offset, 0x1050 + offset, 0x1078 + offset]
            DTUDataReg[portnr] = BaseDataReg + portreg

         BaseDataReg = DTUDataReg[portnr] + 0x28

         if Output: print("Inverter", inv + 1, " of \033[1m", NrOfInv,
                          " SrNr:", hex(InvIdPowr[inv][0]), "\033[0m basis:",hex(BaseDataReg),
                          hex(DTUDataReg[inv]), "NrOfPorts:", NRofPORTS)

         dtu.getData(DTUDataReg, inv, NRofPORTS, invsrnr=InvIdPowr[inv][0])
         SolarP = SolarP + InvIdPowr[inv][1]  # [end] get all inverter DC data
      # ------------------------------------------------------------------------------
      dtsu.getData()  # get grid AC data

      if Output: print(boldon, "[main]GridP:", dtsu.GridP, " SolarP:", SolarP, boldoff, "do now ZeroExport")

      if ZeroExportController and (abs(dtsu.GridP) > doZEROSensivity) and dtu.invPortSts:
         dtu.doZeroExport(dtsu.GridP, SolarP, doZEROSensivity)  # zeroexport function
      else:
         if not dtu.invPortSts:
            if Output: print("[main]invPortSTS_DC:", dtu.invPortSts, " not doing doZeroExport")
         else:
            if Output: print("[main](abs)GridP:", abs(dtsu.GridP), " is in doZEROSensivity:", doZEROSensivity)
      dtu.invPortSts = 0
      if Output: print("[main]", datetime.now().strftime('%H:%M:%S'), "----------------------------------sleep ", SLEEP)

      now = datetime.now()
      if now.hour >= 20 or now.hour <= 7:  # sleep longer
         time.sleep(60 * 10)
      else:
         time.sleep(SLEEP)