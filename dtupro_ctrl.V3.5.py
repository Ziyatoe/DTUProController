'''

Data Logger and zero export Controller for Hoymiles DTU-Pro / one Microinverter MH/MI1500 series over RS485/ModbusRTU
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

import os
from datetime import datetime
from datetime import date
# from subprocess import call
import errno
import sys
from pymodbus.client.sync import ModbusSerialClient
#from pymodbus.client import ModbusSerialClient  for newer pymodbus
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
# from pymodbus.payload import BinaryPayloadBuilder
# from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
import time


# ###################### CONFIGURATION #################################################################################
VERSION = "3.5"
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
DTU_DEV_NR = 101                            # Hoymiles DTU-Pro Modbus device number
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
DTSU_DEV_NR = 22                            # Chint DTSU666 grid meter Modbus device number


# ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

NRofPORTS=4                                  # number of connected ports on WR
MAXPOWER = 1500                              # for 3 ports max value: MI1500 ~1500Watt/4*3s,
Limit = 10                                   # PowerLimit in % of Maxpower 10% at begin
SLEEP = 30                                  # polling tact
# ###################### END CONFIGURATION #############################################################################
UsedPvPorts = [0, 0, 0, 0]
Output = 1    # 0 disable all print commands
BIT8_INT = 0
BIT8_UINT = 1
BIT16_INT = 2
BIT16_UINT = 3
BIT32_INT = 4
BIT32_UINT = 5
BIT64_INT = 6
BIT64_UINT = 7
BIT32_FLOAT = 8
PORT_STATUS = ["cant read MI", "?", "?", "Normal", "?", "ev. PV not connected", "?", "?", "Reduced"]
HEADSTR = "Date,Time,PV1W,PV2W,PV3W,MiTotalW,ImpExpW,ConsumW,DTSU_V,DTSU_Hz,PV1kWhDay,PV2kWhDay,PV3kWhDay\n"
TABS = "\t\t\t\t"
DEBUG = 0

WAIT = 5                                    # wait sek. on each read/write
EXPORT_PLUS = 1                             # gridmeter direction normal (-)=0 , now (+)=1
RWCOUNTER = 4                               # how many times do we try to read or write if not successful before
doZEROSensivity = 16			    # do_zeroexort if more than this power needed

DTUreadRegisters = [0x1000, 0x1028, 0x1050, 0x1078]  # base address-list for each inverter1 port
MainOnOff = 0x9D9C                          # DTU_Pro register all inverter on/off all ports, 0x9D9C,0xC000
MainLimitRegs = 0x9D9D                      # DTU_Pro register all inverter limit all ports
                                            # main limit address 0x9D9D 0xC001
ZeroExportController = 1                    # running 1=controller 0=only as datalogger
csvStr = ""                                 # String for data file
MicroTotalPower = 0
OldLimit = Limit
GridPower = 0
MicroPowerStatus = 0
MicroPortStatus = [0, 0, 0, 0]
MiPortStatus = 0
DTSUStatus = 0

mqttclient = mqtt.Client("XX")
zCounter=0
DTUAllRegs =  [0]*4
current_time = ""
ToDay = date.today()
YesterDay = ToDay                       # for day change
fname = "./data/"+str(ToDay)+".csv"     # the data file in ./data folder as date.csv


def read_DTU_AllRegs():
    # ------------------------------------------------------------------------------------------------------------------
    global DTUAllRegs
    i= 0
    if Output: print("[read_DTU_AllRegs] read DTU-Regs ")
    time.sleep(2)
    for port in range(NRofPORTS):
        adr_begin = DTUreadRegisters[port]
        DTUAllRegs[port] = clientDTU.read_holding_registers(address=adr_begin, count=20, unit=DTU_DEV_NR)
        if DTUAllRegs[port].isError():
            print("[read_DTU_AllRegs] Error Port:",port," ",hex(adr_begin))
        else:
            i+=1
            #print("Port:",port," ",hex(adr_begin))
            #for k in range(20):
                #print(hex(DTUAllRegs[port].registers[k]))
            #print(DTUAllRegs[port].registers[0]," ",DTUAllRegs[port].registers[1]," ",DTUAllRegs[port].registers[2]," ",DTUAllRegs[port].registers[3])
        time.sleep(2)
    if i < NRofPORTS:
        if Output: print("[read_DTU_AllRegs] Can not read all DTU-Regs ",i)
        return 0
    else:
        if Output: print("[read_DTU_AllRegs] readed ")
        return 1

# ---read_DTU_AllRegs---------------------------------------------------------------------------------------------------------------

def read_any_holding_regs(my_client, adr, regs_count, dev_nr, number):
    # ------------------------------------------------------------------------------------------------------------------
    global DTUAllRegs
    my_result=[0,0,0,0,0,0,0,0,0,0]
    i = value = r_result= 0
    # if dev_nr == DTU_DEV_NR:
    #     dev = "DTU"
    # else:
    #     dev = "DSU"
    while not r_result and i < RWCOUNTER:
        if dev_nr == DTU_DEV_NR:
            # read registers from DTUAllRegs[], all registers are readed before
            for i in range(int(regs_count/2)):
                #print("i:",i," adr:",hex(adr)," idx:",hex(int((adr - 0x1000+i)/2)))
                if 0x1000<=adr<0x1028: #  PV1,
                    v=DTUAllRegs[0].registers[int((adr - 0x1000)/2)+i]
                    #print( "PV1 cnt:",i," idx", hex(int((adr - 0x1000)/2+i))," val ",hex(v))
                    my_result[i] = v
                if 0x1028<=adr<0x1050:
                    #print("PV2 ", hex(adr - 0x1028)," val ",DTUAllRegs[1].registers[int((adr - 0x1028+i)/2)])
                    my_result[i] = DTUAllRegs[1].registers[int((adr - 0x1028+i)/2)] #  PV2
                if 0x1050<=adr<0x1078:
                    #print("PV3 ", hex(adr - 0x1050)," val ",DTUAllRegs[2].registers[int((adr - 0x1050+i)/2)])
                    my_result[i] = DTUAllRegs[2].registers[int((adr - 0x1050+i)/2)]#  PV3
                if 0x1078<=adr:
                    #print("PV4 ", hex(adr - 0x1078)," val ",DTUAllRegs[3].registers[int((adr - 0x1078+i)/2)])
                    my_result[i] = DTUAllRegs[3].registers[int((adr - 0x1078+i)/2)]       # PV4
            value = my_result
            #if Output: print( "value---------------------")
            #for k in range(int(regs_count/2)):
                #print(hex(value[k]))
            r_result = 1
        else: #DTSU
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
        if number == BIT16_UINT:return dodecode.decode_16bit_uint()
        if number == BIT32_INT: return dodecode.decode_32bit_int()
        if number == BIT32_UINT:return dodecode.decode_32bit_uint()
        if number == BIT64_INT: return dodecode.decode_64bit_int()
        if number == BIT64_UINT:return dodecode.decode_64bit_uint()
        if number == BIT32_FLOAT:return dodecode.decode_32bit_float()
    else:
        if Output: print(TABS+"read_any_holding_regs error!!")
        # ----mqtt
        mqttclient.publish("Error", "read_any_holding_regs")
        # ----mqtt
        return 0
# --read_any_holding_regs-----------------------------------------------------------------------------------------------

def dtu_write(reg_adr, towrite, dev_nr):
    # ------------------------------------------------------------------------------------------------------------------
    answer = i = 0
    while not answer and i < RWCOUNTER:
        time.sleep(WAIT)       # sattle down a bit
        if Output: print(TABS + "writing DTU", i+1, "time", hex(reg_adr), towrite, dev_nr)
        answer = clientDTU.write_register(address=reg_adr, value=towrite, count=1, unit=dev_nr)
        if answer.isError():
            answer = 0
            i += 1
    if answer:
        if Output: print(TABS+"DTU writeOK", answer)
        return 1
    else:
        if Output: print(TABS+"DTU write error!!", hex(reg_adr), answer)
        # ----mqtt
        mqttclient.publish("Error", "dtu_write")
        # ----mqtt
        return 0
# --dtu_write-----------------------------------------------------------------------------------------------------------


def get_connected_ports():
    # ------------------------------------------------------------------------------------------------------------------
    for port in range(NRofPORTS):   # Important
        adr_begin = DTUreadRegisters[port] + 0x1A   # port status register
        if clientDTU.connect():
            PortStatus = read_any_holding_regs(clientDTU, adr=adr_begin,
                                               regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_UINT)
            if PortStatus != 5:  # 5 is probably not connected
                UsedPvPorts[port] = 1
            else:
                UsedPvPorts[port] = 0
        else:
            if Output: print("Error: get_connected_ports")
            return 0
    if Output: print(UsedPvPorts)
    return 1
# --get_connected_ports-------------------------------------------------------------------------------------------------


def read_micro_status():
    # ------------------------------------------------------------------------------------------------------------------
    global MicroPortStatus
    any_status = 0

    for port in range(NRofPORTS):  # read DTU data from all ports
        t = "Mi01StsPort"
        if UsedPvPorts[port]:
            adr_begin = DTUreadRegisters[port] + 0x1A
            if clientDTU.connect():
                PortStatus = read_any_holding_regs(clientDTU, adr=adr_begin,
                                                        regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_UINT)
                MicroPortStatus[port] = PortStatus
                t = t + str(port+1)
                # ----mqtt
                mqttclient.publish(t, PortStatus)
                # ----mqtt
                #if Output: print("Portstatus--------", PortStatus)
                if Output: print("P", port + 1, ":\033[1m", PORT_STATUS[PortStatus], "\033[0m,",
                      MicroPortStatus[port]," ",end='',sep='')  # , TABS, hex(adr_begin))
            else:
                if Output: print(TABS + "MicroPortStatus: DTU not connected! MicroPortStatus=", any_status)
                MicroPortStatus[port] = -1
                # ----mqtt
                mqttclient.publish("Error", "read_micro_status")
                # ----mqtt
                return 0
        any_status = any_status+MicroPortStatus[port]
    # if Output: print(TABS + "total status", any_status)
    if Output: print("")
    return any_status    # return at least one port is ok or all 0
# --read_micro_status---------------------------------------------------------------------------------------------------

def read_pv_ui(InvPort):
    # ------------------------------------------------------------------------------------------------------------------
    t = "Mi01_UPv"  # read voltage
    result = read_any_holding_regs(clientDTU, adr=DTUreadRegisters[InvPort] + 8, regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_INT) / 10
    t = t + str(InvPort + 1)
    mqttclient.publish(t, result)
    #if Output: print(t, "\t\t", "%5.1f" % result)
    if Output: print("\t%5.1f V " % result,end='',sep='')

    t = "Mi01_IPv"   # read current
    result = read_any_holding_regs(clientDTU, adr=DTUreadRegisters[InvPort] +  0xA, regs_count=2, dev_nr=DTU_DEV_NR,
                          number=BIT16_INT) / 10
    t = t + str(InvPort + 1)
    mqttclient.publish(t, result)
    #if Output: print(t, "\t\t", "%5.1f" % result)
    if Output: print(" %5.1f A " % result,sep='')

# --read_pv_ui----------------------------------------------------------------------------------------------------------

def read_micro_power():
    # ------------------------------------------------------------------------------------------------------------------
    global MicroTotalPower, csvStr
    status = 0

    csvStr = str(ToDay) + "," + current_time + ","

    for port in range(NRofPORTS):  # read DTU data from all ports
        t = "Mi01pvPower"
        if UsedPvPorts[port]:
            adr_begin = DTUreadRegisters[port] + 0x10
            if DEBUG and Output: print("used ports", UsedPvPorts[port], "address", hex(adr_begin))

            pv_power = read_any_holding_regs(clientDTU, adr=adr_begin,
                                             regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_INT) / 10
            if pv_power >= 0:  # 0 is important, because result can be 0 Watt !!
                if Output: print("PV ", port + 1, "\t\t", "%5.1f" % pv_power, "W",end='')
                csvStr = csvStr + str(pv_power) + ","
                # ----mqtt
                t = t + str(port+1)
                mqttclient.publish(t, pv_power)
                # ----mqtt

                MicroTotalPower = MicroTotalPower + pv_power
                status = 1
            else:
                if Output: print(TABS + "wrong Data DTU !!")
                # ----mqtt
                mqttclient.publish("Error", "read_micro_power")
                # ----mqtt
                status = 0

            read_pv_ui(port)
    if status:
        if Output: print("\033[32mTotal PV Power\t", "%5.1f" % MicroTotalPower, "W\033[0m")
        csvStr = csvStr + str(round(MicroTotalPower, 1)) + ","
        # ----mqtt
        mqttclient.publish("Mi01_totalW", round(MicroTotalPower, 1))
        # ----mqtt

    return status
# --DTU read_micro_power------------------------------------------------------------------------------------------------


def read_dtu_dtsu_grid_v_hz_kwh():
    global csvStr
    # ------------------------------------------------------------------------------------------------------------------
    # DTU...........................................
    adr_begin = DTUreadRegisters[1] + 0x0C
    read_v = read_any_holding_regs(clientDTU, adr=adr_begin, regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_INT) / 10
    if Output: print("\n\rWR AC\t\t", read_v, "V\t",end='')        # , hex(adr_begin))
    # csvStr = csvStr + str(read_v) + ","
    # #        time.sleep(SLEEP)
    #
    adr_begin = DTUreadRegisters[1] + 0x0E
    read_hz = read_any_holding_regs(clientDTU, adr=adr_begin,
                                     regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_INT) / 100
    if Output: print(" ", read_hz, "Hz\t",end='')   # , hex(adr_begin))
    # csvStr = csvStr + str(read_hz) + ","

    adr_begin = DTUreadRegisters[1] + 0x18
    temp = read_any_holding_regs(clientDTU, adr=adr_begin,
                                     regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_INT) / 10
    if Output: print(" ", temp, "C")   # , hex(adr_begin))
    # ----mqtt
    mqttclient.publish("WRtemp", round(temp, 1))
    # ----mqtt

    if clientDTSU.connect():
        # DSU.............................................
        adr_begin = 0x2006
        read_v = read_any_holding_regs(clientDTSU, adr=adr_begin,
                                       regs_count=2, dev_nr=DTSU_DEV_NR, number=BIT32_FLOAT) / 10
        if Output: print("Grid AC\t\t", read_v, "V\t",end='')  # , hex(adr_begin))
        csvStr = csvStr + str(read_v) + ","
        # ----mqtt
        mqttclient.publish("Volt", read_v)
        # ----mqtt
        adr_begin = 0x2044
        read_hz = read_any_holding_regs(clientDTSU, adr=adr_begin,
                                        regs_count=2, dev_nr=DTSU_DEV_NR, number=BIT32_FLOAT) / 100
        if Output: print(" ", read_hz, "Hz")  # , hex(adr_begin))
        csvStr = csvStr + str(read_hz) + ","
        # ----mqtt
        mqttclient.publish("Hz", read_hz)
        # ----mqtt
        imp_enrgy = read_any_holding_regs(clientDTSU, adr=0x101e,
                                          regs_count=2, dev_nr=DTSU_DEV_NR, number=BIT32_FLOAT) * 1
        exp_enrgy = read_any_holding_regs(clientDTSU, adr=0x1028,
                                          regs_count=2, dev_nr=DTSU_DEV_NR, number=BIT32_FLOAT) * 1
        # ----mqtt
        if EXPORT_PLUS:
            mqttclient.publish("ExportEnergy", imp_enrgy)
            mqttclient.publish("ImportEnergy", exp_enrgy)
        else:
            mqttclient.publish("ImportEnergy", imp_enrgy)
            mqttclient.publish("ExportEnergy", exp_enrgy)
        # ----mqtt
        # if Output: print("ImportEnergy\t", "%5.1f" % imp_enrgy, "kWh")
        # if Output: print("ImportEnergy\t", "%5.1f" % exp_enrgy, "kWh")

    else:
        if Output: print("DTSU666 can't read data !")
        # ----mqtt
        mqttclient.publish("Error", "read_dtu_dtsu_grid_v_hz_kwh")
        # ----mqtt
        return 0


def read_dtsu_grid_power():
    # ------------------------------------------------------------------------------------------------------------------
    global GridPower, MicroTotalPower, csvStr
    GridP=[0,0,0]

    for i in range(3):
        GridP[i] = read_any_holding_regs(clientDTSU, adr=0x2012,
                                      regs_count=2, dev_nr=DTSU_DEV_NR, number=BIT32_FLOAT) / 10
        time.sleep(1)
    GridPower = round((GridP[0]+GridP[1]+GridP[2]) / 3, 1)
        
    # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # - ist import(bezug)    vom DSU
        # + export(einspeisung)
#    if EXPORT_PLUS:  # be carefully with the export power direction on grid meter
#        GridPower = GridPower * -1
        # - ist export(einspeisung)
        # + ist import(bezug)
    # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
    if abs(GridPower):  
        if GridPower > 0:
            if Output: print("\033[31;1mGrid exp\t", "%5.1f" % GridPower, "W\033[0m")  # + TABS + "Limit",  Limit)
        else:
            if Output: print("\033[34;1mGrid imp\t", "%5.1f" % GridPower, "W\033[0m")  # + TABS + "Limit",  Limit)
        csvStr = csvStr + str(GridPower) + ","
        Consum = round(abs(GridPower) + MicroTotalPower, 1)
        if Output: print("\033[1mConsumption\t", "%5.1f" % Consum, "W \033[0m")
        csvStr = csvStr + str(Consum) + ","
        # ----mqtt
        mqttclient.publish("ImpExpW", GridPower)
        mqttclient.publish("ConsumW", Consum)
        # ----mqtt
        # =========================
        read_dtu_dtsu_grid_v_hz_kwh()
        # =========================
        return 1
    else:
        if Output: print("DTSU666 can't read data !")
        # ----mqtt
        mqttclient.publish("Error", "read_dtsu_grid_power")
        # ----mqtt
        return 0
# --read_dtsu_grid_power------------------------------------------------------------------------------------------------


def read_micro_ports_kwh():
    # ------------------------------------------------------------------------------------------------------------------
    global csvStr
    if clientDTU.connect():
        for port_i in range(4):
            t = "Mi01EnergiePV"
            if UsedPvPorts[port_i]:
                my_adr = DTUreadRegisters[port_i] + 0x12
                result = read_any_holding_regs(clientDTU, adr=my_adr,
                                               regs_count=2, dev_nr=DTU_DEV_NR, number=BIT16_UINT)
                if DEBUG:
                    if Output: print("Today port", port_i, result, "Wh\t\t\t", hex(my_adr))
                csvStr = csvStr + str(result) + ","
                # ----mqtt
                t = t+str(port_i+1)
                mqttclient.publish(t, result)
                # if Output: print("mqtt "+t+str(result))
                # ----mqtt

                # my_adr = DTUreadRegisters[port_i] + 0x14
                # result = read_any_holding_regs(clientDTU, adr=my_adr,
                #                               regs_count=4, dev_nr=DTU_DEV_NR, number=BIT32_UINT)
                if DEBUG:
                    if Output: print("Total port", port_i, result, "Wh\t\t\t", hex(my_adr))
                # csvStr = csvStr + str(result) + ","
        csvStr = csvStr + "\n"
        return 1
    else:
        # ----mqtt
        mqttclient.publish("Error", "read_micro_ports_kwh")
        # ----mqtt
        return 0
# -read_micro_ports_kwh-------------------------------------------------------------------------------------------------


def set_micro_on():
    # ------------------------------------------------------------------------------------------------------------------
    global OldLimit
    if clientDTU.connect():
        if Output: print("[set_micro_on]all inverter set ON ")
        if not(dtu_write(MainOnOff, 1, DTU_DEV_NR)):  # power on,     main on/off address 0x9D9D 0xC001
            return 0
        # TODO : maybe we don't need it, since inverter ON sets the limit 100% ???
        if not (dtu_write(MainLimitRegs, Limit, DTU_DEV_NR)):   # main limit address 0x9D9D 0xC001
            return 0
        OldLimit = Limit
        if Output: print("[set_micro_on]all inverter ON ")
        return 1
    else:
        if Output: print("DTU not connected!!")
        # ----mqtt
        mqttclient.publish("Error", "set_micro_on")
        return 0
        # ----mqtt

# --set_micro_on--------------------------------------------------------------------------------------------------------

def do_zero_export(dtu_adr):
    # ------------------------------------------------------------------------------------------------------------------
    '''
    100	1500	
    90	1350	
    80	1200	
    70  1050	942
    60	900	    920     +20
    50	750	    770     +20
    40	600	    623     +23
    30	450	    470     +20
    20	300	    315     +15
    18	270	    283     +13
    17	255	    267     +12
    15	225	    238     +13
    13	195	    207     +12
    12	180	    192     +12
    11	165	    170     +5
    10	150	    66
    '''

    global li,GridPower, MicroTotalPower, Limit, OldLimit, zCounter
    Limit10P = 115 #change to 10% under this watt
    Limit11P = 170 #over this watt is fine limiting with +/- 1 ????????????????
    OnePcnt = int(MAXPOWER/ 100) #is watt

    # be carefully with the export power direction on grid meter
    if EXPORT_PLUS:
        to_correct_soll = MicroTotalPower + (GridPower* -1)
    else:
        to_correct_soll = MicroTotalPower + GridPower
        
#    consum_ist = abs(GridPower) + MicroTotalPower

    if to_correct_soll <= Limit10P:
        Limit= 10
        if Output: print(TABS + "under 10P Limit %:", Limit)
    else:
        if Limit10P < to_correct_soll <= Limit11P:
            Limit= 11
            if Output: print(TABS + "under 11P Limit %:", Limit)
        else:
            Limit = int(to_correct_soll * 100 / MAXPOWER)
            if Output: print(TABS + "Limit calculated %:", Limit)
            if GridPower > doZEROSensivity :  # >16 watt, es wird exportiert, zu viel produktion
               # Limit calculated %: 27.0
                #zu viel Limit is 33 old 34

                if ((OldLimit > 11) and (Limit >= OldLimit)): #todo.........
                    Limit = OldLimit - 1 #int(abs(GridPower) / OnePcnt)
                    if Output: print(TABS + "zu viel \033[1m Limit is", Limit, "old ",OldLimit)
            else:
                if GridPower < -1*(doZEROSensivity): #< -16 watt, es wird importiert, zu wenig produktion
                    if ((OldLimit < 99) and (Limit <= OldLimit)):
                        Limit = OldLimit + 1 #int(abs(GridPower) / OnePcnt)
                        if Output: print(TABS + "zu wenig \033[1m Limit is", Limit, "old ",OldLimit)
            # fine tuning-----------------
            if (Limit > 99) :
                Limit = 100
            if (Limit < 10) :
                Limit = 10


    if (Limit != OldLimit) or (zCounter > 10):
        if Output: print(TABS + "Limiting\033[1m new", Limit, "% old", OldLimit, "%\033[0m target", "%.1f" % to_correct_soll)
        # ----mqtt
        mqttclient.publish("Limiting", Limit)
        # ----mqtt
        r = dtu_write(MainLimitRegs, Limit, dtu_adr)
        
        if not r:
            if Output: print("ZeroExportController: dtu_write error!!", r)
            # ----mqtt
            mqttclient.publish("Error", "do_zero_export")
            # ----mqtt
        else:
            OldLimit = Limit
        zCounter = 0
    else:
        if Output: print(TABS + "ZeroCounter \033[1m",zCounter, " Limit is", Limit, "%\033[0m target", "%.1f" % to_correct_soll)
        zCounter += 1
# -do_zero_export-------------------------------------------------------------------------------------------------------



def mqtt_on_connect(client, userdata, flags, rc):
    # ------------------------------------------------------------------------------------------------------------------
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

def main():
# -main ================================================================================================================
    global MicroTotalPower, GridPower, fname, YesterDay, current_time, MiPortStatus, MicroPowerStatus,\
        DTSUStatus, csvStr


    if ZeroExportController:
        while not (set_micro_on()):                                # set ON and power 10%
            time.sleep(SLEEP)
        time.sleep(15)

    while not (read_DTU_AllRegs()):   #read all data from DTU at once, tries forever
        if Output: print('Cant read DTU All Registers!!')
        time.sleep(3)

    while not (get_connected_ports()):
        time.sleep(3)
        # ----mqtt
        #mqttclient.publish("Error", "!connected ports")
        # ----mqtt
        #sys.exit(errno.EACCES)
    try:
        while True:
            MicroTotalPower = 0
            GridPower = 0

            ToDay = date.today()                # day change new file
            if ToDay > YesterDay:
                fname = "./data/" + str(ToDay) + ".csv"  # the data file in ./data folder as date.csv
                csvStr = HEADSTR
                file = open(fname, 'a')
                file.write(csvStr)  # write header
                file.close()
                YesterDay = ToDay
            else:
                if Output: print("same day")

            file = open(fname, 'a')
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            if Output: print(ToDay, current_time, "-----------------------------------------------")
            # MQTT --------------------
            mqttclient.publish("Day", str(ToDay))
            mqttclient.publish("Time", str(current_time))
            # MQTT --------------------

            # MicroPortStatus ------------------------------------------------------------------------------
            MiPortStatus = read_micro_status()
            # MicroPortStatus ------------------------------------------------------------------------------

            # DTU reading PV -------------------------------------------------------------------------------
            if clientDTU.connect() and MiPortStatus:
                MicroPowerStatus = read_micro_power()
            else:
                if Output: print("DTU read power: can't connect or MicroPortStatus=", MiPortStatus)
                MicroPowerStatus = 0
            # DTU reading PV -------------------------------------------------------------------------------

            # Grid -----------------------------------------------------------------------------------------
            if clientDTSU.connect():  # and MiPortStatus:    # read DSU only when DTU reading was ok
                DTSUStatus = read_dtsu_grid_power()
            else:
                if Output: print("DSUGrid: can't read or MicroPowerStatus:", MiPortStatus)
            # Grid ----------------------------------------------------------------------------------------

            # -- Controller zero export--------------------------------------------------------------------,
            if ZeroExportController and (abs(GridPower) > doZEROSensivity):
                if clientDTU.connect() and DTSUStatus and MiPortStatus:
                    do_zero_export(DTU_DEV_NR)
                else:
                    if Output: print("Not ZeroExportController or can't connect DTU or read_dtsu_grid_power=",
                          DTSUStatus, "or MicroPowerStatus=", MiPortStatus)
            else:
                if Output: print(TABS+ "GridP ", round(abs(GridPower),1),"W < doZEROSensivity ",doZEROSensivity, "W Limit ",Limit,"%",sep='')
            # -- Controller zero export--------------------------------------------------------------------

            # -- production--------------------------------------------------------------------------------
            if ZeroExportController:
                if MiPortStatus and DTSUStatus and read_micro_ports_kwh():  # read production kWh
                    file.write(csvStr)
                else:
                    if Output: print("DTU not connected or MicroPortStatus or DTSU not connected")
            # production-----------------------------------------------------------------------------------

            file.close()

            if Output: print("sleep for", SLEEP, "sek")
            if ZeroExportController:
                time.sleep(SLEEP)
            else:
                # SLEEP = 30
                time.sleep(SLEEP)
            while not read_DTU_AllRegs():   #read all data from DTU at once, tries forever
                if Output: print('Cant read DTU All Registers!!')
                time.sleep(3)

    except KeyboardInterrupt:
        if Output: print('You cancelled!!')
        clientDTU.close()
        clientDTSU.close()
        if Output: print('Closed all connections!!')

# if MicroTotalPower < 50:
#     call(["aplay", "./sirene.wav"])
#     sys.exit(errno.EACCES)
# ==main================================================================================================================


if __name__ == "__main__":
    # setup------------------------------------------------------------------------------------------------------------------
    if Output: print("DTU-Pro RS485/ModbusDTU zero export controller. Version", VERSION)
    Usage = "usage: *.py Controller=0/1 [1=controler&datalog] [0=only datalog], Output=1/0, Limit=10-100"
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

    if len(sys.argv) == 4:
        if 10 <= int(sys.argv[3]) <= 100:
            Limit = int(sys.argv[3])
            Old_Limit = Limit

    if os.path.isfile(fname):
        if Output: print("Data file exist!", fname)  # do not write header
        file = open(fname, 'a')
    else:  # write data file header, see what we loging
        csvStr = HEADSTR
        file = open(fname, 'a')
        file.write(csvStr)  # write header
    file.close()
    # ----mqtt
    setup_mqtt()
    # ----mqtt
    mqttclient.publish("Error", "running")
    # ----mqtt
    # setup------------------------------------------------------------------------------------------------------------------

    main()













# --------------------------- mqtt vars
# Mi01StsPort3
# pvPower01_3  # PV Power, microinverter 01
# Mi01_totalW
# ImpExpW
# ConsumW
# Volt
# Hz
# Mi01EnergiePV3  # PV energie today, microinverter 01
