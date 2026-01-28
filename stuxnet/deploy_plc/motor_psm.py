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

#import all your libraries here
import psm
import time
import math

#global variables
time_delta = 0.1

def vfd_to_motor_rpm(
    vfd_freq_hz,
    current_rpm,
    dt: float = time_delta,
    ramp_rate_hz_per_s: float = 5.0,
    poles: int = 4,
    load_torque: float = 0.5,
    rated_torque: float = 1.0,
    rated_slip_percent: float = 3.0
):
###
#    Simulate an induction motor’s RPM response to a VFD frequency command.
#
#    Parameters:
#        vfd_freq_hz (float): Commanded frequency from the VFD (Hz).
#        current_rpm (float): Current actual motor speed (mechanical RPM).
#        dt (float): Simulation time step (seconds).
#        ramp_rate_hz_per_s (float): Maximum rate the VFD can change output frequency (Hz/s).
#        poles (int): Number of motor poles (e.g., 2, 4, 6, etc.).
#        load_torque (float): Load torque (0.0–1.0, relative to rated).
#        rated_torque (float): Motor rated torque (for slip calculation).
#        rated_slip_percent (float): Slip at rated load (% of synchronous speed).
#
#    Returns:
#        int: Updated motor speed in RPM.
###

    # Calculate motor slip based on torque
    slip = rated_slip_percent * (load_torque / rated_torque)

    # Convert current mechanical RPM back to synchronous electrical frequency for ramp tracking
    current_vfd_freq = (current_rpm * poles) / (120 * (1-(slip/100)))

    # Apply VFD ramp limit (simulate acceleration/deceleration)
    freq_err = vfd_freq_hz - current_vfd_freq
    max_delta = ramp_rate_hz_per_s * dt
    if abs(freq_err) > max_delta:
        current_vfd_freq += max_delta * (1 if freq_err > 0 else -1)
    else:
        current_vfd_freq = vfd_freq_hz

    # Compute synchronous speed (no slip)
    sync_speed_rpm = (current_vfd_freq * 120) / poles

    # Simulate slip (drops proportional to torque)
    actual_rpm = sync_speed_rpm * (1 - slip / 100.0)

    return int(actual_rpm)

def hardware_init():
    psm.start()
    print("Start Successful")

def update_inputs():    
    motor_running = psm.get_var("QX0.1")
    motor_rpm = psm.get_var("IW0")
    target_freq = psm.get_var("QW0")

    update_rpm = vfd_to_motor_rpm(vfd_freq_hz=target_freq, current_rpm=motor_rpm)
    psm.set_var("IW0",update_rpm)
    psm.set_var("IW1",update_rpm)
 
    
    
def update_outputs():
    pass


if __name__ == "__main__":
    hardware_init()
    while (not psm.should_quit()):
        update_inputs()
        update_outputs()
        time.sleep(0.1) #You can adjust the psm cycle time here
    psm.stop()

