"""
########################################################################
#                                                                      #
#                  Copyright 2020 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
########################################################################

	This file is part of Cold Stage 4.

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
 
import Utilities
import time

class CoolerModel():
	def __init__ (self, object_temp_deg, fluid_temp_deg, heat_sink_temp_deg, measurement_noise_sd, measurement_quantization_steps_per_deg):
		self.measurement_noise_sd = measurement_noise_sd
		self.measurement_quantization_steps_per_deg = measurement_quantization_steps_per_deg
		self.object_temp_k = 273.15 + object_temp_deg
		self.fluid_temp_k = 273.15 + fluid_temp_deg
		self.heat_sink_temp_k = 273.15 + heat_sink_temp_deg
		self.air = Utilities.Fluid('air', 'air_properties.csv', self.fluid_temp_k)
		self.cooler = Utilities.PeltierCooler(6.5, self.heat_sink_temp_k, 64.0, 0.002, 0.002, 1.2)
		self.obj = Utilities.CooledObject(self.object_temp_k, 0.022, 0.003, 2700.0, 921.096)
		self.last_timestamp = time.time()
		
	def UpdateTemperature(self):
		current_timestamp = time.time()
		elapsed_time_secs = float(current_timestamp - self.last_timestamp)
		if elapsed_time_secs == 0:
			elapsed_time_secs = 0.0001
		self.last_timestamp = current_timestamp
		self.obj.UpdateTemperature(self.air, self.cooler, elapsed_time_secs, 10)
	
	def SetThrottle(self, throttle_value):
		self.cooler.SetThrottle(throttle_value)
	
	def ReadTemperatureK(self):
		new_noisy_temperature = Utilities.QuantizeReading(Utilities.AddNoise(self.obj.temperature, self.measurement_noise_sd), self.measurement_quantization_steps_per_deg)
		return new_noisy_temperature
	
	def ReadTemperatureC(self):
		new_noisy_temperature = Utilities.QuantizeReading(Utilities.AddNoise(self.obj.temperature, self.measurement_noise_sd), self.measurement_quantization_steps_per_deg)
		return new_noisy_temperature - 273.15
