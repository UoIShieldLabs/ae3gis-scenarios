import numpy as np
import math
import time
import precision_timer
import turbine_functions as tbf
from dataclasses import dataclass
import threading
import json
import zmq
import threading
import matplotlib.pyplot as plt
import csv
from flask import Flask, jsonify, request, render_template, send_file
import pandas as pd
import io

###   Constants and Simulator Settings    ###
TIME_STEP = 0.01
WIND_RAMP_RATE = 0.1

R = 63			        # Turbine radius;               m
rho = 1.225	        # Air density;                  kg/m^3
J_ROTOR = 3.87E7    # Rotor Inertia;    	          kg*m^2
J_GEN = 534.116     # Generator Inertia;            kg*m^2
PITCH_RR = 9.9981   # Ramp rate for blade pitch;    deg/s
TQ_RR = 40000       # Gen. torque ramp rate;        Nm/s

GBR = 97	        # Gearbox ratio between rotor and generator 
GBR_EFF = 1       # Gearbox efficiency, 1=no losses
GEN_EFF = 0.944   # Generator mechanical to electrical power efficiency
CP_TABLE = tbf.CpLookup('Cp_Ct_Cq.NREL5MW.txt')


# WIND_SETPOINTS= [
#   # (1, 60),
#   # (5, 120),
#   # (11.3, 120),
#   (8, 60),
#   (15, 120),
#   (26, 120), 
# ]
# WIND_RAMP_RATE = 0.1
# WIND = tbf.get_wind_list(WIND_SETPOINTS, WIND_RAMP_RATE, TIME_STEP)

# WIND_FILE = 'flatirons_wind_2026_03_31.csv'
# FILE_DT = 60
# FILE_START = 0
# FILE_DURATION = 30
# WIND = tbf.get_wind_from_flat_irons('flatirons_wind_2026_03_31.csv', FILE_DT, TIME_STEP,FILE_START,FILE_DURATION)

# WIND_LEN = len(WIND)

LOGGING_ENABLED = True
class SimLogger:
  def __init__(self):
    self.time = []
    self.pitch_setpoint = []
    self.gen_torque_setpoint = []
    self.engage_generator = []
    self.wind_speed = []
    self.pitch_real = []
    self.rotor_power = []
    self.rotor_speed = []
    self.rotor_accel = []
    self.rotor_torque = []
    self.rotor_Cp = []
    self.gen_power = []
    self.gen_speed = []
    self.gen_torque_real = []
    self.tsr = []
    self.tsr_i = []
    self.ctrl_reg = []

  def write_parquet(self, filename="simulation_output.parquet"):
    fields = vars(self)
    length = min(len(v) for v in fields.values())
    trimmed = {
        k: v[:length]
        for k,v in fields.items()
    }
    df = pd.DataFrame(trimmed)
    df.to_parquet(
        filename,
        engine='pyarrow',
        compression='zstd'
    )
  
  def display_logger_stats(self):
    fields = vars(self)
    for field in fields.keys():
      print(f"{field}:\t{len(fields[field])}")
  
  def get_tail(self, n):
    return {
      key:value[-n:]
      for key,value in vars(self).items()
      if isinstance(value,list)
    }

class CtrlLogger:
  def __init__(self):
    self.time = []
    self.pitch_setpoint = []
    self.gen_torque_setpoint = []
    self.ctrl_region = []
    self.engage_generator = []
  
  def write_parquet(self, filename="simulation_output.parquet"):
    fields = vars(self)
    length = min(len(v) for v in fields.values())
    trimmed = {
        k: v[:length]
        for k,v in fields.items()
    }
    df = pd.DataFrame(trimmed)
    df.to_parquet(
        filename,
        engine='pyarrow',
        compression='zstd'
    )
  
  def display_logger_stats(self):
    fields = vars(self)
    for field in fields.keys():
      print(f"{field}:\t{len(fields[field])}")

@dataclass
class TurbineCtrlInputs:      ## Setpoints from PLC
  pitch_setpoint: float = 0.0
  gen_torque_setpoint: float = 0.0
  ctrl_region: float = 0.0
  engage_generator: bool = False

inputs = TurbineCtrlInputs()

@dataclass
class TurbineSimOutputs:      ## Simulator Outputs
  wind_speed: float = 0.0
  pitch_real: float = 0.0
  gen_torque_real: float = 0.0
  gen_speed: float = 0.0
  rotor_speed: float = tbf.w_min
  generator_power: float = 0.0
  tsr: float = 0.0

outputs = TurbineSimOutputs()

class WindController:
  def __init__(self):
    self.use_manual = False
    self.default_speed = 1.0
    self.manual_speed = self.default_speed
    self.file_wind = None
    self.file_index = 0
    self.wind_ramp = WIND_RAMP_RATE*TIME_STEP
    self.current_wind = self.default_speed
    self.lock = threading.Lock()

  def set_manual(self, speed):
    with self.lock:
      self.manual_speed = speed
      self.use_manual = True

  def use_file(self):
    with self.lock:
      self.use_manual = False

  def load_file(self, data):
    with self.lock:
      self.file_wind = data
      self.file_index = 0
      self.use_manual = False

  def get_wind(self):
    with self.lock:
      if self.use_manual:
        diff = self.manual_speed - self.current_wind
        if diff > 0:
          self.current_wind = self.current_wind + min(self.wind_ramp,abs(diff))
        else:
          self.current_wind = self.current_wind - min(self.wind_ramp,abs(diff))
     
      if self.file_wind is not None:
        wind = self.file_wind[self.file_index]
        self.file_index = (self.file_index + 1) % len(self.file_wind)
        return wind
      
      return self.current_wind

wind_ctrl = WindController()

lock = threading.Lock()
stop_event = threading.Event()
logger = SimLogger()
ctrl_logger = CtrlLogger()

class WebInterface:
  def __init__(self, inputs:TurbineCtrlInputs, outputs:TurbineSimOutputs, wind_ctrl:WindController, lock):
    self.inputs = inputs
    self.outputs = outputs
    self.wind = wind_ctrl
    self.lock = lock
    self.last_plot = None
    self.plot_time = None
    self.app = Flask(__name__)
    self.setup_routes()

  def setup_routes(self):
    @self.app.route('/')
    def index():
      return render_template('index.html')

    @self.app.route('/api/state')
    def state():
      with self.lock:
        return jsonify({
          "wind_speed":self.outputs.wind_speed,
          "gen_torque_real":self.outputs.gen_torque_real,
          "gen_torque_setpoint":self.inputs.gen_torque_setpoint,
          "pitch_real":self.outputs.pitch_real,
          "pitch_setpoint":self.inputs.pitch_setpoint,
          "generator_power":self.outputs.generator_power,
          "rotor_speed":self.outputs.rotor_speed,
          "gen_speed":self.outputs.gen_speed,
          "tsr":self.outputs.tsr
        })

      # @self.app.route('/api/wind',methods=['POST'])
      # def wind():
      #   data=request.json
      #   self.wind.set_override(data["speed"])
      #   return jsonify({"status":"ok"})
    @self.app.route('/api/set_wind',methods=['POST'])
    def set_wind():
      data=request.json
      self.wind.set_manual(data["speed"])
      return jsonify({"status":"manual"})
      
      # @self.app.route('/api/wind_enable',methods=['POST'])
      # def wind_enable():
      #   data=request.json
      #   self.wind.enable(data["state"])
      #   return jsonify({"status":"ok"})
      
    @self.app.route('/api/upload_wind',methods=['POST'])
    def upload_wind():
      if 'file' not in request.files:
        return jsonify({"status":"no file"})
      file=request.files['file']
      try:
        df=pd.read_csv(file)              
        wind_data=df.iloc[:,0].dropna().tolist()
        wind_data=[float(x) for x in wind_data]
        self.wind.load_file(wind_data)
        return jsonify({
          "status":"loaded",
          "points":len(wind_data)
        })

      except Exception as e:
        return jsonify({
          "status":"error",
          "msg":str(e)
        })
      
    @self.app.route('/api/plot_sim', methods=['GET'])
    def plot_sim():
      self.plot_time = request.args.get('time',default='_')
      with self.lock:
        fig=plot_data(logger)
      
      buf = io.BytesIO()
      fig.savefig(buf,format='png',dpi=150)
      plt.close(fig)
      buf.seek(0)
      self.last_plot = buf.getvalue()
      return send_file(
        io.BytesIO(self.last_plot),
        mimetype='image/png'
      )

    @self.app.route('/download_plot')
    def download_plot():
      if self.last_plot is None:
        return "Generate plot first",400
      
      return send_file(
        io.BytesIO(self.last_plot),
        mimetype='image/png',
        as_attachment=True,
        download_name=f"turbine_plot-{self.plot_time}.png"
      )

  def run(self):
    self.app.run(
      host='0.0.0.0',
      port=8080,
      threaded=True
    )

def network_loop(ctrl_in: TurbineCtrlInputs, state_out: TurbineSimOutputs, lock, stop_event, ctrl_logger:CtrlLogger):
  context = zmq.Context()
  socket = context.socket(zmq.REP)
  socket.bind("tcp://*:5555")

  while not stop_event.is_set():
    message = socket.recv()
    msg_time = time.perf_counter()
    data = json.loads(message.decode())

    with lock:
      if "pitch_setpoint" in data:
        ctrl_in.pitch_setpoint = data["pitch_setpoint"]
      if "gen_torque_setpoint" in data:
        ctrl_in.gen_torque_setpoint = data["gen_torque_setpoint"]
      if "ctrl_reg" in data:
        ctrl_in.ctrl_region = data["ctrl_reg"]
      if "engage_generator" in data:
        ctrl_in.engage_generator = data["engage_generator"]

      reply = {
        "rotor_speed": state_out.rotor_speed,
        "generator_power": state_out.generator_power,
        "pitch_real": state_out.pitch_real,
        "wind_speed": state_out.wind_speed,
        "tsr": state_out.tsr,
        "gen_torque_real": state_out.gen_torque_real,
        "gen_speed": state_out.gen_speed
      }

    socket.send(json.dumps(reply).encode())
    if LOGGING_ENABLED:
      ctrl_logger.time.append(msg_time)
      ctrl_logger.pitch_setpoint.append(ctrl_in.pitch_setpoint)
      ctrl_logger.gen_torque_setpoint.append(ctrl_in.gen_torque_setpoint)
      ctrl_logger.ctrl_region.append(ctrl_in.ctrl_region)
      ctrl_logger.engage_generator.append(ctrl_in.engage_generator)

def simulation_loop(ctrl_in: TurbineCtrlInputs, state_out: TurbineSimOutputs, lock, stop_event, logger:SimLogger, wind_ctrl:WindController):
  step_count = 0  
  sim_start_time = time.perf_counter()
  
  while not stop_event.is_set():
    with lock:
      pitch_sp = ctrl_in.pitch_setpoint
      gen_tq_sp = ctrl_in.gen_torque_setpoint
      ctrl_reg = ctrl_in.ctrl_region
      engage = ctrl_in.engage_generator
      pitch_real = state_out.pitch_real
      gen_tq_real = state_out.gen_torque_real
      rotor_speed = state_out.rotor_speed

  ## Adjust gen_tq and pitch based on CTRL parameters
    pitch_err = pitch_sp - pitch_real
    pitch_step = min(abs(pitch_err), PITCH_RR*TIME_STEP)
    if pitch_err > 0: 
      pitch_real = pitch_real + pitch_step
    elif pitch_err < 0:
      pitch_real = pitch_real - pitch_step

    gen_tq_err = gen_tq_sp - gen_tq_real
    gen_tq_step = min(abs(gen_tq_err), TQ_RR*TIME_STEP)
    if gen_tq_err > 0: 
      gen_tq_real = gen_tq_real + gen_tq_step
    elif gen_tq_err < 0:
      gen_tq_real = gen_tq_real - gen_tq_step

  ## Get current wind speed from WIND list
    # wind_speed = WIND[step_count%WIND_LEN]  # Restarts the list once sim reaches the end
    # file_wind = WIND[step_count%WIND_LEN]
    wind_speed = wind_ctrl.get_wind()

  ## Calculate Sim Outputs
    tsr = tbf.tsr_func(rotor_speed, R, wind_speed)
    tsr_i = tbf.tsrI_func(tsr, pitch_real)
    # power_coef = tbf.Cp_func(tsr_i, pitch_real)
    power_coef = CP_TABLE.get_cp(pitch_real, tsr)
    rotor_power = tbf.P_rotor_func(power_coef, rho, R, wind_speed)
    rotor_tq = tbf.T_rotor_func(rotor_power, rotor_speed)
    rotor_accel  = tbf.accel_func(rotor_tq, gen_tq_real,GBR, J_ROTOR,J_GEN)
    rotor_speed = max(rotor_speed + (rotor_accel*TIME_STEP),tbf.w_min)
    gen_speed = tbf.w_gen_func(rotor_speed, GBR, GBR_EFF)
    gen_power = tbf.P_gen_func(gen_tq_real, gen_speed, GEN_EFF, engage)

    with lock:
      state_out.rotor_speed = rotor_speed
      state_out.generator_power = gen_power
      state_out.wind_speed = wind_speed
      state_out.pitch_real = pitch_real
      state_out.tsr = tsr
      state_out.gen_torque_real = gen_tq_real
      state_out.gen_speed = gen_speed

    if LOGGING_ENABLED:
      logger.time.append(TIME_STEP*step_count)
      logger.pitch_setpoint.append(pitch_sp)
      logger.gen_torque_setpoint.append(gen_tq_sp)
      logger.gen_torque_real.append(gen_tq_real)
      logger.engage_generator.append(engage)
      logger.wind_speed.append(wind_speed)
      logger.pitch_real.append(pitch_real)
      logger.rotor_speed.append(rotor_speed)
      logger.gen_power.append(gen_power)
      logger.tsr.append(tsr)
      logger.tsr_i.append(tsr_i)
      logger.rotor_accel.append(rotor_accel)
      logger.rotor_torque.append(rotor_tq)
      logger.rotor_power.append(rotor_power)
      logger.rotor_Cp.append(power_coef)
      logger.gen_speed.append(gen_speed)
      logger.ctrl_reg.append(ctrl_reg)

    step_count += 1
    expected_end_time = sim_start_time + (TIME_STEP*step_count)
    while time.perf_counter() <= expected_end_time:
      precision_timer.usleep(500)

def plot_data(logger:SimLogger):
    fig = plt.figure(figsize=(12,10))
    
    plt.subplot(3,2,1)
    plt.plot(logger.time, logger.wind_speed)
    plt.ylabel("Wind Speed (m/s)")
    plt.xlabel("Time (s)")
    plt.grid(True)
    
    plt.subplot(3,2,2)
    plt.plot(logger.time, logger.gen_torque_real, label='Gen Tq real')
    plt.plot(logger.time, logger.gen_torque_setpoint, label='Gen Tq setpoint')
    # plt.plot(logger.time, logger.rotor_torque, label='Rotor Tq')
    plt.ylabel("Torque (Nm)")
    plt.xlabel("Time (s)")
    plt.legend()
    plt.grid(True)
    
    plt.subplot(3,2,3)
    plt.plot(logger.time, logger.pitch_setpoint, label="setpoint")
    plt.plot(logger.time, logger.pitch_real, label="real")
    plt.legend()
    plt.ylabel("Blade Pitch (deg)")
    plt.grid(True)
    
    plt.subplot(3,2,4)
    plt.plot(logger.time, logger.gen_power,label="Gen power")
    plt.plot(logger.time, logger.rotor_power, label="Rotor power")
    plt.legend()
    plt.ylabel("Power (W)")
    plt.xlabel("Time (s)")
    plt.grid(True)

    plt.subplot(3,2,5)
    plt.plot(logger.time, logger.rotor_speed, label="Rotor Speed")
    plt.plot(logger.time, logger.gen_speed, label="Generator Speed")
    plt.ylabel("Angular Velocity (rad/s)")
    plt.xlabel("Time (s)")
    plt.legend()
    plt.grid(True)

    plt.subplot(3,2,6)
    plt.plot(logger.time, logger.tsr)
    plt.ylabel("TSR")
    plt.xlabel("Time (s)")
    plt.grid(True)
    # plt.show()
    return fig

net_thread = threading.Thread(
  target=network_loop,
  args=(inputs, outputs, lock, stop_event, ctrl_logger),
  daemon=True
)

sim_thread = threading.Thread(
  target=simulation_loop,
  args=(inputs, outputs, lock, stop_event, logger, wind_ctrl),
  daemon=True
)

web = WebInterface(inputs,outputs,wind_ctrl,lock)
web_thread = threading.Thread(
  target=web.run,
  daemon=True
)

web_thread.start()
net_thread.start()
sim_thread.start()

try:
  net_thread.join()
  sim_thread.join()

except KeyboardInterrupt:
  stop_event.set()
  print("\nSim shutdown...")
  # if LOGGING_ENABLED:
  #   print("Plotting Data...")
  #   logger.write_parquet()
  #   ctrl_logger.write_parquet()
  #   plot_data(logger)

