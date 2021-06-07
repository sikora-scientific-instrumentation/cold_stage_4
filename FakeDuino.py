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
 
# Fake arduino for testing purposes.
import time
import numpy as np
import crcmod.predefined

import CoolerModel

class FakeDuino():
	def __init__ (self, num_channels, time_step, object_temp_deg_c, fluid_temp_deg_c, heatsink_temp_deg_c, measurement_noise_sd, measurement_quantization_per_deg):
		self.unique_id = 0
		self.welcome_string = 'simulation_test_device'
		self.start_timestamp = time.time()
		self.num_channels = num_channels
		self.rx_buffer = ''
		self.tx_buffer = ''
		self.crc_buffer = ''
		self.INPUT_FLAG = False
		self.CRC_FLAG = False
		
		self.current_channel = 0
		self.flow_rate = [15.0 for i in range(self.num_channels)]
		self.fakeduino_mode = ['Idle' for i in range(self.num_channels)]
		self.last_timestamp = [0.0 for i in range(self.num_channels)]
		self.time_step = time_step
		
		self.object_temp_deg_c = object_temp_deg_c
		self.fluid_temp_deg_c = fluid_temp_deg_c
		self.heatsink_temp_deg_c = heatsink_temp_deg_c
		self.measurement_noise_sd = measurement_noise_sd
		self.measurement_quantization_per_deg = measurement_quantization_per_deg
		self.models = [CoolerModel.CoolerModel(self.object_temp_deg_c, self.fluid_temp_deg_c, self.heatsink_temp_deg_c, self.measurement_noise_sd, self.measurement_quantization_per_deg) for i in range(self.num_channels)]
		
		self.prt_diff_slope = 1.1
		self.prt_diff_offset = -0.1
		
	def close(self):
		pass
	
	def write(self, written_byte):
		message_to_process = False
		written_char = written_byte.decode()
		if written_char == '>':
			self.INPUT_FLAG = True
			self.CRC_FLAG = False
			self.rx_buffer = ''
			self.crc_buffer = ''
		elif ((written_char == '<') and (self.CRC_FLAG == False)):
			self.CRC_FLAG = True
		elif ((written_char == '<') and (self.CRC_FLAG == True)):
			self.CRC_FLAG = False
			self.INPUT_FLAG = False
			message_to_process = True
		else:
			if ((self.INPUT_FLAG == True) and (self.CRC_FLAG == False)):
				self.rx_buffer += written_char
			elif ((self.INPUT_FLAG == True) and (self.CRC_FLAG == True)):
				self.crc_buffer += written_char
		
		if message_to_process == True:
			# Can we make an int from CRC string?
			check = False
			crc_value = 0
			try:
				message_crc_8 = int(self.crc_buffer)
				check = True
			except:
				check = False
			if check == True:
				# Calculate check comparison.
				calculated_crc_8 = self.calcCRC8(self.rx_buffer)
				if message_crc_8 == calculated_crc_8:
					self.__ParseInput()
	
	def read(self):
		character_to_return = self.tx_buffer[0]
		byte_to_return = character_to_return.encode()
		self.tx_buffer = self.tx_buffer[1:]
		return byte_to_return
	
	def inWaiting(self):
		return len(self.tx_buffer)
	
	def __ParseInput(self):
		# We update the temperature of the simulation every time we change the current fake Arduino cooler channel.
		# (We switch through all available channels every iteration in the back end)
		#~if (((time.time() - self.start_timestamp) > 15.0) and ((time.time() - self.start_timestamp) < 30.0) and (self.current_channel == 1)):
			#~self.flow_rate[self.current_channel] = 0
		#~else:
			#~self.flow_rate[self.current_channel] = 15.0 + np.random.uniform(-1.0, 1.0)
		self.flow_rate[self.current_channel] = 15.0 + np.random.uniform(-1.0, 1.0)
		if self.fakeduino_mode[self.current_channel] == 'Idle':
			if self.rx_buffer == 'Idle':
				self.fakeduino_mode[self.current_channel] = 'Idle'
				current_model_temperature = self.models[self.current_channel].ReadTemperatureC()
				flow_rate = self.flow_rate[self.current_channel]
				self.tx_buffer = '>' + str(current_model_temperature) + '<' + str(self.calcCRC8(str(current_model_temperature))) + '<'
				self.tx_buffer += '>' + str((current_model_temperature * self.prt_diff_slope) + self.prt_diff_offset) + '<' + str(self.calcCRC8(str((current_model_temperature * self.prt_diff_slope) + self.prt_diff_offset))) + '<'
				self.tx_buffer += '>' + str(flow_rate) + '<' + str(self.calcCRC8(str(flow_rate))) + '<'
				self.models[self.current_channel].SetThrottle(0.0)
			elif self.rx_buffer == 'Throttle':
				self.tx_buffer += '>*<' + str(self.calcCRC8('*')) + '<'
				self.fakeduino_mode[self.current_channel] = 'Throttle'
			elif self.rx_buffer == 'Off':
				self.tx_buffer += '>*<' + str(self.calcCRC8('*')) + '<'
				self.models[self.current_channel].SetThrottle(0.0)
			elif self.rx_buffer == 'Channel':
				self.tx_buffer += '>*<' + str(self.calcCRC8('*')) + '<'
				self.fakeduino_mode[self.current_channel] = 'Channel'
			elif self.rx_buffer == 'Greeting':
				self.tx_buffer += '>' + str(self.unique_id) + '<' + str(self.calcCRC8(str(self.unique_id))) + '<'
				self.tx_buffer += '>' + self.welcome_string + '<' + str(self.calcCRC8(self.welcome_string)) + '<'
				self.tx_buffer += '>' + str(self.num_channels) + '<' + str(self.calcCRC8(str(self.num_channels))) + '<'
		elif self.fakeduino_mode[self.current_channel] == 'Throttle':
			new_throttle_setting = float(self.rx_buffer)
			current_model_temperature = self.models[self.current_channel].ReadTemperatureC()
			flow_rate = self.flow_rate[self.current_channel]
			self.tx_buffer = '>' + str(current_model_temperature) + '<' + str(self.calcCRC8(str(current_model_temperature))) + '<'
			self.tx_buffer += '>' + str((current_model_temperature * self.prt_diff_slope) + self.prt_diff_offset) + '<' + str(self.calcCRC8(str((current_model_temperature * self.prt_diff_slope) + self.prt_diff_offset))) + '<'
			self.tx_buffer += '>' + str(flow_rate) + '<' + str(self.calcCRC8(str(flow_rate))) + '<'
			self.models[self.current_channel].SetThrottle(new_throttle_setting)
			self.fakeduino_mode[self.current_channel] = 'Idle'
		elif self.fakeduino_mode[self.current_channel] == 'Channel':
			self.previous_channel = self.current_channel
			self.current_channel = int(self.rx_buffer)
			self.models[self.current_channel].UpdateTemperature()
			self.tx_buffer += '>' + str(self.current_channel) + '<' + str(self.calcCRC8(str(self.current_channel))) + '<'
			self.fakeduino_mode[self.previous_channel] = 'Idle'

	def calcCRC8(self, message):
		crc8 = crcmod.predefined.mkPredefinedCrcFun('crc-8-maxim')
		crc8_check_value = crc8(message.encode('utf-8'))
		#~if (((time.time() - self.start_timestamp) > 15.0) and ((time.time() - self.start_timestamp) < 55.0) and (self.current_channel == 0)):
			#~crc8_check_value += 1
		return crc8_check_value
