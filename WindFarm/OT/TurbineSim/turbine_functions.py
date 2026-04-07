import math
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import RegularGridInterpolator
import pandas as pd

##  Turbine Blade Constants  ##
c1 = 0.5
c2 = 116
c3 = 0.4
c4 = 5
c5 = 21
c6 = 0
c7 = 0.089
c8 = 0.035

w_min = 0.2   # Assuming the turbine will continue rotating slowly when not operating.

## Helper class for Cp lookup table
class CpLookup:
    def __init__(self, filename):
        self.pitch = None
        self.tsr = None
        self.cp = None

        self.load_file(filename)

        self.interp = RegularGridInterpolator(
            (self.tsr,self.pitch),
            self.cp
        )

    def load_file(self, filename):
        with open(filename) as f:
            lines = f.readlines()

        data = [
            line.strip() for line in lines
            if line.strip() and not line.startswith("#")
        ]

        self.pitch = np.array(
            [float(x) for x in data[0].split()]
        )

        self.tsr = np.array(
            [float(x) for x in data[1].split()]
        )

        cp_start = 3
        rows = len(self.tsr)
        cols = len(self.pitch)
        cp_matrix = []
        for i in range(rows):
            row = [
                float(x)
                for x in data[cp_start + i].split()
            ]
            cp_matrix.append(row)

        self.cp = np.array(cp_matrix)

    def get_cp(self,pitch,tsr):
      pitch = np.clip(pitch,self.pitch[0],self.pitch[-1])
      tsr = np.clip(tsr,self.tsr[0],self.tsr[-1])
      return self.interp([[tsr,pitch]])[0]

    def get_max_cp(self):
      idx = np.unravel_index(
        np.argmax(self.cp),
        self.cp.shape
      )
      tsr_index = idx[0]
      pitch_index = idx[1]
      max_cp = self.cp[tsr_index, pitch_index]
      max_tsr = self.tsr[tsr_index]
      max_pitch = self.pitch[pitch_index]
      return max_cp, max_pitch, max_tsr

    def plot_cp_surface(self):
      TSR,PITCH = np.meshgrid(
          self.tsr,
          self.pitch,
          indexing='ij'
      )

      fig = plt.figure()
      ax = fig.add_subplot(
          111,
          projection='3d'
      )

      ax.plot_surface(
          TSR,
          PITCH,
          self.cp,
          cmap='viridis'
      )

      ax.set_xlabel("TSR")
      ax.set_ylabel("Pitch")
      ax.set_zlabel("Cp")
      ax.set_title("NREL 5MW Cp Surface")

      plt.show()

    def plot_cp_vs_tsr(self, pitch_list=None):
      if pitch_list is None:
          pitch_list = [0,2,5,10,15]

      plt.figure()
      for pitch in pitch_list:
          cp_vals = []
          for tsr in self.tsr:
              cp_vals.append(
                  self.get_cp(pitch,tsr)
              )
          plt.plot(
              self.tsr,
              cp_vals,
              label=f"Pitch {pitch} deg"
          )

      plt.xlabel("Tip Speed Ratio")
      plt.ylabel("Cp")
      plt.title("NREL 5MW Cp Curves")
      plt.legend()
      plt.grid()
      plt.show()

## Wind Data Functions
def get_wind_list(setpoints, ramp_rate, dt):
    total_duration = 0    
    for i in range(0,len(setpoints)):
      sp = setpoints[i][0]
      duration = setpoints[i][1]
      total_duration += duration
      
      if i == len(setpoints)-1:
        break
      
      next_sp = setpoints[i+1][0]
      total_duration += abs((next_sp-sp))/ramp_rate

    x = np.arange(0,total_duration, dt)
    conditions = []
    functions = []
    elapsed = 0
    for i in range(0,len(setpoints)):
      sp = setpoints[i][0]
      duration = setpoints[i][1]
      conditions.append((x>=elapsed)&(x<elapsed+duration))
      functions.append(sp)
      elapsed += duration

      if i == len(setpoints)-1:
        break
      
      next_sp = setpoints[i+1][0]
      sp_diff = next_sp - sp
      ramp_duration = abs(sp_diff)/ramp_rate
      conditions.append((x>=elapsed)&(x<elapsed+ramp_duration))     
      ramp_dir = 1 if sp_diff >= 0 else -1
      functions.append(lambda x,s=ramp_dir,m=ramp_rate,b=sp,t=elapsed: (s*m*x)+(b-(s*m*t)))
      elapsed += ramp_duration
    
    wind = np.piecewise(x, conditions, functions).tolist()
    wind.extend(wind[::-1])
    return wind

def get_wind_from_flat_irons(filename, file_dt, sim_dt, start_time, duration):
  wind_df = pd.read_csv(filename, usecols=['Avg Wind Speed @ 80m [m/s]'])
  wind_df = wind_df[start_time:start_time+duration+1]
  n = file_dt/sim_dt
  wind_series = wind_df['Avg Wind Speed @ 80m [m/s]']

  new_index = np.arange(0, len(wind_series) - 1 + 1e-9, 1/(n + 1))
  reindexed_series = wind_series.reindex(new_index, method=None)
  interpolated_series = reindexed_series.interpolate(method='linear')  
  interpolated_series.reset_index(drop=True, inplace=True)
  # wind_series = wind_df['Avg Wind Speed @ 80m [m/s]'].repeat(file_dt/TIME_STEP)
  # wind_series = wind_series.reset_index(drop=True)
  wind_data = interpolated_series.to_list()
  wind_data.extend(wind_data[::-1])
  # wind_data = wind_series.to_list()
  return wind_data

## Modeling Functions
def tsr_func(w, r, v):
  '''
  Calculates the Tip-to-speed ratio.
  
  Inputs:
  w		Rotor angular velocity  (rad/s)
  r		Turbine radius          (m)
  v		Wind speed              (m/s)
  
  Outputs:
  Tip-to-speed ratio (TSR)
  '''
  return (w*r)/v

def tsrI_func(tsr, beta):
  '''
  	Calculates a corrected TSR that accounts for blade angle
	and aerodynamic effects.
  
  Inputs:
  tsr 	Tip-to-speed ratio                ()
  beta 	Blade angle <- Control Variable   (deg)
  
  Outputs:
  Corrected TSR
  '''
  return 1/((1/(tsr+c7))-(c8/(1+(beta**3))))

def Cp_func(tsr_i, beta):
  '''
  	Calculates the Power Coefficient, which is the ratio of power
  extracted from the wind and the available power in the wind.
  
  Inputs:
  tsr_i		Corrected TSR		                  ()
  beta		Blade angle <- Control Variable   (deg)
  
  Outputs:
  Power coefficient (Cp)
  '''
  return c1*((c2/tsr_i)-(c3*beta)-c4)*(math.e**((-1*c5)/tsr_i))+(c6*tsr_i)

def P_rotor_func(Cp, rho, r, v):
  '''
  Calculates the power extracted from the wind by the turbine.
  
  Inputs:
  Cp    Power coefficient	  ()
  rho   Air density         (kg/m^3)
  r     Turbine radius      (m)
  v     Wind speed          (m/s)

  Outputs:
  Rotor power (W)
  '''

  return 0.5*Cp*rho*math.pi*(r**2)*(v**3)

def T_rotor_func(P_rotor, w_rotor):
  '''
  Calculates the rotor torque.

  Inputs:
  P_rotor   Rotor power               (W)
  w_rotor   Rotor angular velocity    (rad/s)

  Outputs:
  Rotor torque (Nm)
  '''
  return P_rotor/max([w_rotor, w_min])

def accel_func(T_rotor, T_gen, N, J_rotor, J_gen):
  '''
  Calculates the angular acceleration of the rotor.

  Inputs:
  T_rotor   Rotor torque                (Nm)
  J         Turbine moment of inertia   (kg*m^2)

  Outputs:
  Angular acceleration (rad/s^2)   
  '''
  return (T_rotor-(N*T_gen))/(J_rotor+((N**2)*J_gen))

def w_gen_func(w_rotor, gbr, gbr_eff):
  '''
  Calculates the rotational velocity of the generator.

  Inputs:
  w_rotor   Rotor angular velocity            (rad/s)
  gbr       Gearbox ratio                     ()
  gbr_eff   Gearbox efficiency, 1=no losses   ()
  
  engaged   Bool flag for whether generator is connected to rotor

  Outputs:
  Generator angular velocity (rad/s)
  '''

  return w_rotor * gbr * gbr_eff
  


def P_gen_func(T_gen, w_gen, gen_eff, engaged:bool):
  '''
  Calculates the rotational velocity of the generator.

  Inputs:
  T_gen     Generator torque <- Control Variable    (Nm)
  w_gen     Generator angular velocity              (rad/s)
  gen_eff   Generator efficiency, 1=no losses       ()
  
  engaged   Bool flag for whether generator is producing power

  Outputs:
  Electric power from the generator (rad/s)
  '''
  if engaged:
    return T_gen * w_gen * gen_eff
  
  return 0