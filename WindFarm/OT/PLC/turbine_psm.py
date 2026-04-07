#                  - OpenPLC Python SubModule (PSM) -
# 
# PSM is the bridge connecting OpenPLC core to Python programs. PSM allows
# you to directly interface OpenPLC IO using Python and even write drivers 
# for expansion boards using just regular Python.
#
# PSM API is quite simple and just has a few functions. When writing your
# own programs, avoid touching on the "__main__" function as this regulates
# how PSM works on the PLC cycle. You can write your own hardware initialization
# code on hardware_init(), and your IO handling code on update_inputs() and
# update_outputs()
#
# To manipulate IOs, just use PSM calls psm.get_var([location name]) to read
# an OpenPLC location and psm.set_var([location name], [value]) to write to
# an OpenPLC location. For example:
#     psm.get_var("QX0.0")
# will read the value of %QX0.0. Also:
#     psm.set_var("IX0.0", True)
# will set %IX0.0 to true.
#
# Below you will find a simple example that uses PSM to switch OpenPLC's
# first digital input (%IX0.0) every second. Also, if the first digital
# output (%QX0.0) is true, PSM will display "QX0.0 is true" on OpenPLC's
# dashboard. Feel free to reuse this skeleton to write whatever you want.

# DWORDS RETURN LISTS DO NOT FORGOR

#import all your libraries here
import psm
import time
import json
import zmq

#global variables
SCALING_FACTOR = 1000
with open("/opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt", 'r')as file:
    SIM_ADDR = file.read().rstrip()
# SIM_ADDR = "127.0.0.1:5555"
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"tcp://{SIM_ADDR}")
sim_data = {
    "rotor_speed": 0.0,
    "generator_power": 0.0,
    "pitch_real": 0.0,
    "wind_speed": 0.0,
    "tsr": 0.0,
    "gen_torque_real":0.0,
    "gen_speed":0.0
}

def float_to_words(value, is_power=False):
    if is_power:
        scaled = int(value / SCALING_FACTOR)
    else:
        scaled = int(value * SCALING_FACTOR)
    # scaled_2s = scaled & 0xFFFFFFFF
    h_word = (scaled >> 16) & 0xFFFF
    l_word = scaled & 0xFFFF
    return h_word,l_word

def words_to_float(h_word, l_word):
    value = (h_word << 16) | l_word
    # if value & 0x80000000:
    #     value -= 0x100000000

    value = value/SCALING_FACTOR
    return value

def hardware_init():
    #Insert your hardware initialization code in here
    global sim_data
    global socket
    socket.send_json({})
    response = socket.recv_json()
    sim_data["rotor_speed"] = response["rotor_speed"]
    sim_data["generator_power"] = response["generator_power"]
    sim_data["pitch_real"] = response["pitch_real"]
    sim_data["wind_speed"] = response["wind_speed"]
    sim_data["tsr"] = response["tsr"]
    sim_data["gen_torque_real"] = response["gen_torque_real"]
    sim_data["gen_speed"] = response["gen_speed"]

    psm.start()

def update_inputs():
    #place here your code to update inputs
    global sim_data
    
    wind_speed = float_to_words(sim_data["wind_speed"])
    pitch_real = float_to_words(sim_data["pitch_real"])
    generator_power = float_to_words(sim_data["generator_power"], is_power=True)
    rotor_speed = float_to_words(sim_data["rotor_speed"])
    tsr = float_to_words(sim_data["tsr"])
    gen_torque_real = float_to_words(sim_data["gen_torque_real"])
    gen_speed = float_to_words(sim_data["gen_speed"])

    input_data = [wind_speed, pitch_real, generator_power, rotor_speed, tsr, gen_torque_real, gen_speed]

    for i in range(0, len(input_data)):
        psm.set_var(f"IW{i*2}",input_data[i][0])
        psm.set_var(f"IW{(i*2)+1}",input_data[i][1])
    
    
def update_outputs():
    #place here your code to work on outputs
    global socket
    global sim_data
    engage_gen = psm.get_var("QX0.0")
    pitch_H = psm.get_var("QW0")
    pitch_L = psm.get_var("QW1")
    pitch = words_to_float(pitch_H,pitch_L)
    gen_tq_H = psm.get_var("QW2")
    gen_tq_L = psm.get_var("QW3")
    gen_tq = words_to_float(gen_tq_H,gen_tq_L)
    ctrl_reg_H = psm.get_var("QW4")
    ctrl_reg_L = psm.get_var("QW5")
    ctrl_reg = words_to_float(ctrl_reg_H,ctrl_reg_L)
    engage_gen = psm.get_var("QX0.0")
    print(f"Pitch: {pitch_H}, {pitch_L}, {pitch}")
    print(f"Tq   : {gen_tq_H}, {gen_tq_L}, {gen_tq}")
    print(f"Reg  : {ctrl_reg_H}, {ctrl_reg_L}, {ctrl_reg}")
    updated_setpoints = {
        "pitch_setpoint": pitch,
        "gen_torque_setpoint": gen_tq,
        "ctrl_reg": ctrl_reg,
        "engage_generator": engage_gen
    }
    
    socket.send_json(updated_setpoints)

    response = socket.recv_json()
    print(response)
    sim_data["rotor_speed"] = response["rotor_speed"]
    sim_data["generator_power"] = response["generator_power"]
    sim_data["pitch_real"] = response["pitch_real"]
    sim_data["wind_speed"] = response["wind_speed"]
    sim_data["tsr"] = response["tsr"]
    sim_data["gen_torque_real"] = response["gen_torque_real"]
    sim_data["gen_speed"] = response["gen_speed"]


if __name__ == "__main__":
    hardware_init()
    while (not psm.should_quit()):
        update_inputs()
        update_outputs()
        time.sleep(0.02) #You can adjust the psm cycle time here
    psm.stop()

