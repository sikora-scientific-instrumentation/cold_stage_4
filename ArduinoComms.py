"""
########################################################################
#                                                                      #
#                  Copyright 2020 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
#      A class allowing simple call-response communication with        #
#             a slave device over a serial connection.                 #
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

import serial
import serial.tools.list_ports
import time
import crcmod.predefined

import FakeDuino

class ArduinoComms():
	def __init__ (self, parent):
		self.start_timestamp = time.time()
		self.parent = parent
		self.available_devices = {0: ('none', 'simulation_test_device', 0)}
		self.available_ports = []
		self.port = None
		self.baud = 57600
		self.unique_id = None
		self.welcome_string = None
		self.number_of_channels = None
		self.serial_connection = None
		self.fault_condition = False
		self.connected = False
		self.ScanForDevices()
	
	def Clear(self):
		self.port = None
		self.unique_id = None
		self.welcome_string = None
		self.number_of_channels = None
		self.fault_condition = False
		self.connected = False
		
	def ConnectByID(self, ID):
		if int(ID) in self.available_devices.keys():
			port, welcome_string, number_of_channels = self.available_devices[int(ID)]
			success_flag = self.Connect(port, self.baud)
			if success_flag == True:
				fault_flag, responses = self.Call('Greeting', 3)
				if fault_flag == '':
					self.port = port
					self.unique_id = int(responses[0])
					self.welcome_string = responses[1]
					self.number_of_channels = int(responses[2])
					print("Connected to device: " + self.welcome_string + ", ID: " + str(self.unique_id) + " on port: " + self.port)
					self.connected = True
				else:
					del self.available_devices[ID]
					self.serial_connection.close()
					self.Clear()
			else:
				del self.available_devices[ID]
				self.Clear()
		else:
			self.Clear()
		return self.connected
	
	def ConnectByPort(self, port):
		success_flag = self.Connect(port, self.baud)
		if success_flag == True:
			fault_flag, responses = self.Call('Greeting', 3)
			if fault_flag == '':
				self.port = port
				self.unique_id = int(responses[0])
				self.welcome_string = responses[1]
				self.number_of_channels = int(responses[2])
				print("Connected to device: " + self.welcome_string + ", ID: " + str(self.unique_id) + " on port: " + self.port)
				self.connected = True
			else:
				self.serial_connection.close()
				self.Clear()
		else:
			self.Clear()
		return self.connected
	
	def ScanForDevices(self):
		#~print("-----------------------------------------------------------------------------------")
		#~print("Scanning for cold-stage devices...")
		serial_ports = [entry[0] for entry in serial.tools.list_ports.comports()]
		new_ports = [port for port in serial_ports if port not in self.available_ports]
		missing_ports = [port for port in self.available_ports if port not in serial_ports]
		#~print("Missing ports: ", missing_ports)
		#~print("New ports    : ", new_ports)
		# Remove devices that are no-longer available.
		changed_devices = 0
		for key in self.available_devices.keys():
			if self.available_devices[key][0] in missing_ports:
				del self.available_devices[key]
				changed_devices += 1
		# Check new ports for devices.
		for port in new_ports:
			success_flag = self.Connect(port = port, baud = self.baud)
			if success_flag == True:
				fault_flag, responses = self.Call('Greeting', 3)
				if fault_flag == '':
					unique_id = int(responses[0])
					welcome_string = responses[1]
					number_of_channels = int(responses[2])
					self.available_devices[unique_id] = (port, welcome_string, number_of_channels)
					changed_devices += 1
				self.serial_connection.close()
		self.available_ports = serial_ports
		return (changed_devices > 0)
		
	def Connect(self, port, baud):
		print("-----------------------------------------------------------------------------------")
		print("Attempting to connect to device on port ", port, " ...")
		success_flag = False
		try:
			# Open up the serial communication link with the Arduino.
			# If the final argument (mode) is set to 0, open a real serial connection to the Arduino.
			# If set to 1, instead instantiate a FakeDuino, an object that will simulate both the comms and
			# cooling behaviour of the hardware system for testing purposes.
			if port != 'none':
				self.serial_connection = serial.Serial(port, self.baud)
				# Apparently pyserial ( > v 2.5) has a bug whereby when connecting to a device over USB serial, 
				# after the first successful connection subsequent connections will fail as the correct terminal
				# settings are *not* applied, even if those settings are the defaults. 
				# The solution to this is to change the settings to anything, and then back to the setting you
				# want. This forces the back end to apply the correct (in this case, default) settings.
				# See the link below for more info :
				# http://raspberrypi.stackexchange.com/questions/37892/raspberry-pi-and-serial-only-working-one-shot
				self.serial_connection.parity = serial.PARITY_ODD
				self.serial_connection.parity = serial.PARITY_NONE
				# Must given Arduino time to reset.
				#~time.sleep(1.0)
				self.serial_connection.reset_input_buffer()
			else:
				self.serial_connection = FakeDuino.FakeDuino(self.parent.device_parameter_defaults['simulation_number_of_channels'], self.parent.device_parameter_defaults['time_step'], 4.0, 20.0, 1.0, 0.021, 16)
			success_flag = True
			print("...success!")
		except:
			self.serial_connection = None
			success_flag = False
			print("...unsuccessful.")
		return success_flag
	
	def Reconnect(self):
		self.connected = False
		self.ScanForDevices()
		if self.ConnectByID(self.unique_id) == False:
			# If we couldn't reconnect by ID, Likely the stage with that ID is no longer connected. 
			# However, if two stages were connected at the same time and both failed at the same time, if when they re-appeared
			# to the system the ports assigned to them were swapped (IE - the stage previous on /dev/ttyUSB3 is now on /dev/ttyUSB4
			# and vice-versa) the available_ports list would not change, thus the available_devices dictionary would not be rebuilt
			# and so ConnectByID() would try and connect to the stages via the wrong port. We can force the available_devices
			# dictionary to be rebuilt by clearing the available_ports list. Next time CommFailureLoop() calls Reconnect(), 
			# ScanForDevices() will interrogate every available port and completely rebuild the available_devices list.
			self.available_ports = []
		
	def __SerialSpeak(self, message):
		message = '>' + message + '<' + str(self.calcCRC8(message)) + '<'
		for current_char in message:
			self.serial_connection.write(current_char.encode())
		
	def __SerialListen(self, timeout_secs):
		start_time = time.time()
		message_buffer = ''
		crc_buffer = ''
		message_received = False
		crc_check_passed = False
		input_flag = False
		crc_flag = False
		while(True):
			while ((self.serial_connection.inWaiting() > 0)):
				received_byte = self.serial_connection.read()
				received_character = received_byte.decode('utf-8')
				if received_character == '>':
					input_flag = True
					crc_flag = False
				elif ((received_character == '<') and (crc_flag == False)):
					crc_flag = True
				elif ((received_character == '<') and (crc_flag == True)):
					input_flag = False
					crc_flag = False
					message_received = True
					break
				else:
					if input_flag == True:
						if crc_flag == False:
							message_buffer += received_character
						else:
							crc_buffer += received_character
			if (((time.time() - start_time) > timeout_secs) or (message_received == True)):
				break
		
		if message_received == True:
			# First check if we can convert crc string to int.
			check = False
			message_crc_value = 0
			try:
				message_crc_value = int(crc_buffer)
				check = True
			except:
				check = False
			if check == True:
				calculated_crc_value = self.calcCRC8(message_buffer)
			if message_crc_value == calculated_crc_value:
				crc_check_passed = True
		return message_received, crc_check_passed, message_buffer
	
	def Call(self, message, expected_replies):
		fault_flag = ''
		responses = []
		crc_check_passed = []
		try:
			#~# Clear serial input buffer of any existing contents...
			while ((self.serial_connection.inWaiting() > 0)):
				self.serial_connection.read()
			self.__SerialSpeak(message)
			for reply in range(expected_replies):
				response_completed_flag, crc_check_passed_flag, response = self.__SerialListen(0.2)
				if response_completed_flag == True:
					responses.append(response)
					crc_check_passed.append(crc_check_passed_flag)
			if len(responses) < expected_replies:
				fault_flag = 't'
				print('Serial comms fault - Message timeout! Retrying...')
			else:
				if all(crc_check_passed) == False:
					fault_flag = 'c'
					print('Serial comms fault - CRC check failure! Retrying...')
		except OSError as e:
			if e.args[0] == 5:
				fault_flag = 'f'
				print('Serial comms fault - USB connection failure! Attempting to reconnect...')
		return fault_flag, responses
	
	def __CommsFailureLoop(self):
		# Attempt to reconnect until successful or channel 0 front-end tells us to give up...
		success_flag = False
		retry_flag = True
		while retry_flag == True:
			next_message = ('1',)
			try:
				next_message = self.parent.mq_front_to_back[0].get(False, None)
			except:
				next_message = ('',)
			if next_message[0] == 'AllShutDown':
				retry_flag = False
				success_flag = False
			else:
				self.Reconnect()
				if self.connected == True:
					print("Cold-stage reconnected!")
					retry_flag = False
					success_flag = True
		return success_flag
		
	def __AlertFrontendCommsFailure(self):
		if self.fault_condition == False:
			# Inform channel 0 front-end of connection failure.
			self.parent.mq_back_to_front[0].put((2, 'Comms_fault'))
			self.fault_condition = True
	
	def __AlertFrontendCommsSuccess(self):
		if self.fault_condition == True:
			# Inform channel 0 front-end of re-connection success.
			self.parent.mq_back_to_front[0].put((2, 'Comms_success'))
			self.fault_condition = False
	
	def __CheckForFrontendCancel(self):
		retry_flag = True
		next_message = ('1',)
		try:
			next_message = self.parent.mq_front_to_back[0].get(False, None)
		except:
			next_message = ('',)
		if next_message[0] == 'AllShutDown':
			retry_flag = False
		else:
			time.sleep(0.1)
			retry_flag = True
		return retry_flag
	
	def StageChannelSelect(self, channel_id):
		retry_flag = True
		success_flag = False
		fault_flag = ''
		responses = []
		while retry_flag == True:
			fault_flag, responses = self.Call('Channel', 1)
			if fault_flag == '':
				fault_flag, responses = self.Call(str(channel_id), 1)
				if fault_flag == '':
					if int(responses[0]) == channel_id:
						success_flag = True
						retry_flag = False
						self.__AlertFrontendCommsSuccess()
					else:
						self.__AlertFrontendCommsFailure()
						retry_flag = self.__CheckForFrontendCancel()
				elif ((fault_flag == 't') or (fault_flag == 'c')):
					self.__AlertFrontendCommsFailure()
					retry_flag = self.__CheckForFrontendCancel()
				elif fault_flag == 'f':
					self.__AlertFrontendCommsFailure()
					retry_flag = self.__CommsFailureLoop()
			elif ((fault_flag == 't') or (fault_flag == 'c')):
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CheckForFrontendCancel()
			elif fault_flag == 'f':
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CommsFailureLoop()
		return success_flag, responses
	
	def StageIdle(self, channel_id):
		retry_flag = True
		success_flag = False
		fault_flag = ''
		responses = []
		while retry_flag == True:
			fault_flag, responses = self.Call('Idle', 3)
			if fault_flag == '':
				success_flag = True
				retry_flag = False
				self.__AlertFrontendCommsSuccess()
			elif ((fault_flag == 't') or (fault_flag == 'c')):
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CheckForFrontendCancel()
			elif fault_flag == 'f':
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CommsFailureLoop()
				if retry_flag == True:
					retry_flag, responses = self.StageChannelSelect(channel_id)
		return success_flag, responses
		
	def StageThrottle(self, throttle_setting, channel_id):
		retry_flag = True
		success_flag = False
		fault_flag = ''
		responses = []
		while retry_flag == True:
			fault_flag, responses = self.Call('Throttle', 1)
			if fault_flag == '':
				fault_flag, responses = self.Call(str(throttle_setting), 3)
				if fault_flag == '':
					success_flag = True
					retry_flag = False
					self.__AlertFrontendCommsSuccess()
				elif ((fault_flag == 't') or (fault_flag == 'c')):
					self.__AlertFrontendCommsFailure()
					retry_flag = self.__CheckForFrontendCancel()
				elif fault_flag == 'f':
					self.__AlertFrontendCommsFailure()
					retry_flag = self.__CommsFailureLoop()
					if retry_flag == True:
						retry_flag, responses = self.StageChannelSelect(channel_id)
			elif ((fault_flag == 't') or (fault_flag == 'c')):
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CheckForFrontendCancel()
			elif fault_flag == 'f':
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CommsFailureLoop()
				if retry_flag == True:
					retry_flag, responses = self.StageChannelSelect(channel_id)
			# After the initial attempt we will try and zero the throttle.
			throttle_setting = 0.0
		return success_flag, responses
	
	def StageGreeting(self, channel_id):
		retry_flag = True
		success_flag = False
		fault_flag = ''
		responses = []
		while retry_flag == True:
			fault_flag, responses = self.Call('Greeting', 1)
			if fault_flag == '':
				success_flag = True
				retry_flag = False
			elif ((fault_flag == 't') or (fault_flag == 'c')):
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CheckForFrontendCancel()
			elif fault_flag == 'f':
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CommsFailureLoop()
		return success_flag, responses
	
	def StageOff(self, channel_id):
		retry_flag = True
		success_flag = False
		fault_flag = ''
		responses = []
		while retry_flag == True:
			fault_flag, responses = self.Call('Off', 1)
			if fault_flag == '':
				success_flag = True
				retry_flag = False
				self.__AlertFrontendCommsSuccess()
			elif ((fault_flag == 't') or (fault_flag == 'c')):
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CheckForFrontendCancel()
			elif fault_flag == 'f':
				self.__AlertFrontendCommsFailure()
				retry_flag = self.__CommsFailureLoop()
				if retry_flag == True:
					retry_flag, responses = self.StageChannelSelect(channel_id)
		return success_flag, responses
	
	def calcCRC8(self, message):
		crc8 = crcmod.predefined.mkPredefinedCrcFun('crc-8-maxim')
		crc8_check_value = crc8(message.encode('utf-8'))
		return crc8_check_value
