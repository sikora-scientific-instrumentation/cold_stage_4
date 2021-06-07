"""
########################################################################
#                                                                      #
#                  Copyright 2021 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
########################################################################

	This file is part of Cold Stage 4.
	PRE RELEASE 3

	Cold Stage 4 is free software: you can redistribute it and/or 
	modify it under the terms of the GNU General Public License as 
	published by the Free Software Foundation, either version 3 of the 
	License, or (at your option) any later version.

	Cold Stage 4 is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with Cold Stage 4.  
	If not, see <http://www.gnu.org/licenses/>.

"""

import math
import numpy as np
import csv
import time
from multiprocessing import Event

def QuantizeReading(reading, fraction_resolution_denominator):
	real_value = reading
	try:
		measured_value = round(real_value * float(fraction_resolution_denominator)) / int(fraction_resolution_denominator)
	except:
		print(reading, fraction_resolution_denominator)
	return measured_value

def AddNoise(reading, standard_deviation):
	import numpy as np
	real_value = reading
	noise = np.random.normal(real_value, standard_deviation)
	return noise

def PolynomialCorrection(measured_value, coefficients):
	# Apply a polynomial correction to a measured value.
	# Order of polynomial function is determined according to the number of coefficients.
	# Polynomial of form y = Ax^2 + Bx + C, coefficients of the form [A, B, C].    
	corrected_value = 0.0
	if len(coefficients) > 0:
		for term in range((len(coefficients))):
			value = (coefficients[term] * pow(measured_value, ((len(coefficients) - 1) - term)))
			corrected_value += value
	return corrected_value

class DriftFreeTimer():
	def __init__ (self, signal_thread_event, kill_thread_event, interval_msecs):
		# Drift compensating timer.
		next_call = time.time()
		while kill_thread_event.wait(0.01):
			next_call = next_call + interval_msecs
			sleep_duration = next_call - time.time()
			if sleep_duration < 0.0:
				sleep_duration = 0.0
			time.sleep(sleep_duration)
			signal_thread_event.set()


class PIDController():
	def __init__(self, time_step, pid_coeffs, drive_mode):
		self.time_step = float(time_step)
		self.P = pid_coeffs['P']
		self.I = pid_coeffs['I']
		self.D = pid_coeffs['D']
		self.drive_mode = drive_mode
	def Initialise(self, current_temp, setpoint):
		self.current_temp = current_temp
		self.setpoint = setpoint
		self.error = self.current_temp - self.setpoint
		self.integral_error = 0.0
		self.output = 0.0
	def Update(self, measurement):
		error = float(measurement) - self.setpoint
		self.delta_error = error - self.error
		self.error = error
		self.integral_error += (self.error * self.time_step) 
		self.delta_output = (self.P * self.error) + (self.I * self.integral_error) + (self.D * self.delta_error * (1.0 / self.time_step))
		self.output += self.delta_output
		
		if self.drive_mode == 1:
			# Heating only mode...
			if self.output > 0.0:
				self.output = 0.0
			if self.output < -100.0:
				self.output = -100.0
		elif self.drive_mode == 2:
			# Heating/Cooling mode...
			if self.output > 100.0:
				self.output = 100.0
			if self.output < -100.0:
				self.output = -100.0
		elif self.drive_mode == 3:
			# Cooling only mode...
			if self.output > 100.0:
				self.output = 100.0
			if self.output < 0.0:
				self.output = 0.0
		return round(self.output, 3)

class Fluid():
	properties = {}
	def __init__(self, name, data_file, bulk_temperature):
		self.name = name
		self.data_file = data_file
		self.bulk_temperature = bulk_temperature
		values = []
		with open(self.data_file, 'r') as csvfile:
			spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
			for i, row in enumerate(spamreader):
				if i == 0:
					columns = [[str(j)] for i, j in enumerate(row)]
				elif i == 1:
					for j, k in enumerate(row):
						columns[j].append(str(k))
				else:
					for j, k in enumerate(row):
						columns[j].append(float(k))
			for i in columns:
				self.properties[i[0]] = {}
				self.properties[i[0]]['units'] = i[1]
				self.properties[i[0]]['values'] = i[2:]
				if i[0] != 'Temperature':
					self.properties[i[0]]['fit_order'] = 3
					self.properties[i[0]]['fit_coeffs'] = np.polyfit(self.properties['Temperature']['values'], self.properties[i[0]]['values'], 2)
	def GetProperties(self, temperature, property_name):
		return np.polyval(self.properties[property_name]['fit_coeffs'], temperature)

class PeltierCooler():
	def __init__(self, max_cooling_power, heatsink_temperature, number_of_elements, element_width, element_length, element_thermal_conductivity):
		self.heatsink_temperature = heatsink_temperature
		self.number_of_elements = number_of_elements
		self.element_width = element_width
		self.element_length = element_length
		self.element_thermal_conductivity = element_thermal_conductivity
		self.throttle_percent = 0
		self.maximum_cooling_power = max_cooling_power
		self.current_cooling_power = 0.0
	def ConductiveHeatTransfer(self, delta_t):
		return self.number_of_elements * (self.element_thermal_conductivity * (self.element_width ** 2) * (delta_t / self.element_length))
	def SetThrottle(self, throttle_percent):
		self.throttle_percent = float(throttle_percent)
		self.current_cooling_power = float((self.maximum_cooling_power / 100.0) * self.throttle_percent)

class CooledObject():
	def __init__(self, temperature, edge_length, thickness, density, specific_heat_capacity):
		self.temperature = temperature
		self.edge_length = float(edge_length)
		self.thickness = float(thickness)
		self.density = float(density)
		self.specific_heat_capacity = float(specific_heat_capacity)
		self.volume = np.power(edge_length, 2.0) * thickness
		self.mass = self.volume * self.density
		self.cooled_area = np.power(edge_length, 2.0)
		self.length_parameter = self.cooled_area / (self.edge_length * 4.0)
		self.conductive_heat_transfer = 0.0
		self.temperature_change_rate = 0.0
	def ConvectiveHeatTransfer(self, fluid, delta_t):
		boundary_temperature = fluid.bulk_temperature + delta_t
		film_temperature = (fluid.bulk_temperature + boundary_temperature) / 2.0
		density = fluid.GetProperties(film_temperature, 'Density')
		thermal_expansion_coefficient = 1.0 / film_temperature
		dynamic_viscosity = fluid.GetProperties(film_temperature, 'DynamicViscosity') * 1e-5
		grashof_number = (np.power(self.length_parameter, 3.0) * np.power(density, 2.0) * 9.81 * (-1.0*delta_t) * thermal_expansion_coefficient) / (dynamic_viscosity ** 2.0)
		prandtl_number = fluid.GetProperties(film_temperature, 'Prandtl\'sNumber')
		rayleigh_number = grashof_number * prandtl_number
		# We can't take a fractional power of a negative number with np.power(). 
		# This solution taken from https://stackoverflow.com/a/45384691
		nusselt_number = 0.27 * (np.sign(rayleigh_number) * (np.abs(rayleigh_number)) ** 0.25)
		coefficient_of_convective_heat_transfer = (nusselt_number * (fluid.GetProperties(film_temperature, 'ThermalConductivity') * 1e-2)) / self.length_parameter
		heat_transfer_rate = coefficient_of_convective_heat_transfer * self.cooled_area * delta_t
		return {'Rayleigh Number' : rayleigh_number, 'Convective Heat Transfer Coefficient' : coefficient_of_convective_heat_transfer, 'Heat Transfer Rate' : heat_transfer_rate}
	def UpdateTemperature(self, fluid, peltier_cooler, integration_time, sub_time_steps):
		integration_time = float(integration_time)
		sub_time_step = integration_time / float(sub_time_steps)
		sub_time = 0.0
		self.sub_times = []
		self.sub_temperatures = []
		self.sub_rates = []
		for i in range(sub_time_steps):
			self.sub_times.append(sub_time)
			self.sub_temperatures.append(self.temperature)
			heatsink_object_delta_t = self.temperature - peltier_cooler.heatsink_temperature
			bulk_fluid_object_delta_t = self.temperature - fluid.bulk_temperature
			conductive_heat_transfer = peltier_cooler.ConductiveHeatTransfer(heatsink_object_delta_t)
			convective_heat_transfer = self.ConvectiveHeatTransfer(fluid, bulk_fluid_object_delta_t)
			# Multiply overall rate by -1 as we are actually calculating flow INTO the object
			net_heat_transfer_rate = (conductive_heat_transfer + convective_heat_transfer['Heat Transfer Rate'] + peltier_cooler.current_cooling_power) * -1.0
			delta_t = ((net_heat_transfer_rate * sub_time_step) / (self.specific_heat_capacity)) * (1.0 / self.mass)
			self.temperature_change_rate = delta_t
			self.temperature += delta_t
			self.sub_rates.append((delta_t * (1.0 / (integration_time / float(sub_time_steps)))))
			sub_time += (integration_time / float(sub_time_steps))
		return self.temperature

class KalmanFilter():
	def __init__(self, name, time_step, x0, F, q, p0, H, R):
		self.name = name
		self.time_step = time_step
		self.x0 = np.matrix(x0)
		self.F = np.matrix(F)
		self.Q = np.matrix([[q, 0.0], [0.0, q]])
		self.p0 = np.matrix(p0)
		self.H = np.matrix(H)
		self.R = np.matrix(R)
		self.B = np.matrix([[0.0], [0.0]])
	def Predict(self):
		self.x1 = (self.F * self.x0) + self.B
		self.p1 = ((self.F * self.p0) * np.transpose(self.F)) + self.Q
	def Update(self, measurement):
		y = np.matrix(np.array([[measurement], [0.0]]))
		z = y - (self.H * self.x1)
		S = self.H * self.p1 * np.transpose(self.H) + self.R
		K = self.p1 * np.transpose(self.H) * (S ** -1)
		self.x2 = self.x1 + (K * z)
		self.p2 = (np.eye(2) - (K * self.H)) * self.p1
		self.x0 = self.x2
		self.p0 = self.p2

class TimingMonitor():
	def __init__(self, channel_id, mq_timestamp, event_kill):
		self.mq_timestamp = mq_timestamp
		self.event_kill = event_kill
		self.channel_id = channel_id
		self.current_timestamps = []
		
		print("Timing monitor ready.")
		while True:
			if not self.event_kill.is_set():
				break
			try:
				most_recent_timestamp = self.mq_timestamp.get(False, timeout = None)
				if most_recent_timestamp[0] == 0:
					self.normalised_timestamps = [[j[0], round(j[1] - self.current_timestamps[0][1], 4)] for i, j in enumerate(self.current_timestamps)]
					print('Channel ' + str(self.channel_id) + ': ', self.normalised_timestamps)
					self.current_timestamps = []
				else:
					self.current_timestamps.append(most_recent_timestamp)
			except:
				pass
		# Flush timestamp message queue in readiness for shutdown. If we end this process with items still on the input
		# queue, attempts to join this process will block indefinitely.
		while self.mq_timestamp.qsize() > 0:
			try:
				most_recent_timestamp = self.mq_timestamp.get(False, None)
			except:
				pass
		print("Timing monitor shut down.")

def TruncateFloat(number, digits) -> float:
	stepper = 10.0 ** digits
	return math.trunc(stepper * number) / stepper
