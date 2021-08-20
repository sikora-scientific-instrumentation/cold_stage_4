"""
########################################################################
#                                                                      #
#                  Copyright 2021 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
########################################################################

	This file is part of Cold Stage 4.
	PRE RELEASE 3.2

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

import time
from multiprocessing import Queue, Process, Event
import threading as Thread
import os, sys
import csv
import numpy as np

import Utilities
import RampManager
import Logger

class CoolerChannel():
	def __init__ (self, device_parameter_defaults, backend_object, channel_id, mq_back_to_front, mq_back_to_vlogger, event_vlogger_fault, event_back_to_front, mq_timestamp, logging_rate, drive_mode, timing_flag, video_enabled_flag, comms_manager, time_step, pid_coeffs):
		self.current_time = time.time()
		
		self.device_parameter_defaults = device_parameter_defaults
		self.backend_object = backend_object
		self.channel_id = channel_id
		self.drive_mode = drive_mode
		self.comms_manager = comms_manager
		self.time_step = time_step
		self.pid_coeffs = pid_coeffs
		self.logging_rate = logging_rate
		
		self.mq_back_to_front = mq_back_to_front
		self.mq_back_to_vlogger = mq_back_to_vlogger
		self.mq_timestamp = mq_timestamp
		self.event_vlogger_fault = event_vlogger_fault
		self.event_back_to_front = event_back_to_front
		
		self.mode = 'idle'
		self.shut_down_flag = False
		self.logging_flag = False
		self.setpoint_flag = False
		self.ramping_flag = False
		self.flow_fault_flag = False
		self.video_fault_flag = False
		self.force_video_off = False
		self.force_log_data_file_path = False
		self.timing_flag = timing_flag
		self.video_enabled_flag = video_enabled_flag
		self.log_start_on_profile_start_flag = self.device_parameter_defaults['start_logging_at_profile_start_flag'][self.channel_id]
		self.log_end_on_profile_end_flag = self.device_parameter_defaults['stop_logging_at_profile_end_flag'][self.channel_id]
		self.log_video_split_flag = self.device_parameter_defaults['log_video_split_flag'][self.channel_id]
		
		self.setpoint = 'NA'
		self.throttle_setting = 0.0
		self.temperature_limits = {'max': self.device_parameter_defaults['max_temperature_limit'][self.channel_id], 'min': self.device_parameter_defaults['min_temperature_limit'][self.channel_id]}
		self.overload_fault_flags = {'suspected': False, 'start_time': 0.0, 'confirmed': False}
		#~self.temperature_rates = {'old_1st_derivative': 0.0, '1st_derivative': 0.0, '2nd_derivative': 0.0}
		
		# Load the prt and thermocouple calibration coefficients.
		self.prt_calibration_coeffs = self.LoadCalibration('Channel ' + str(self.channel_id) + ' internal PRT', self.device_parameter_defaults['prt_calibration_coeffs_filepath'][self.channel_id])
		self.EnableTCCalibration()
		self.LoadTempLimits()
		self.calibration_limit = None
		
		if self.backend_object.comms_success_flag == True:
			# Get channel temperature upon instantiation:
			# Set controller to channel select mode, send the current channel ID, then send an Idle command to read
			# the current temperature.
			success_flag, responses = self.comms_manager.StageChannelSelect(self.channel_id)
			if success_flag == True:
				self.current_time = time.time()
				success_flag, responses = self.comms_manager.StageIdle(self.channel_id)
				if success_flag == True:
					self.temperature = Utilities.PolynomialCorrection(float(responses[0]), self.tc_calibration_coeffs)
					self.PRT_temperature = Utilities.PolynomialCorrection(float(responses[1]), self.prt_calibration_coeffs)
					self.flow_rate = float(responses[2])
					
					# Instantiate a PID controller object.
					self.pd = Utilities.PIDController(self.device_parameter_defaults, self.time_step, self.pid_coeffs, self.drive_mode)
					
					# Instantiate a RampManager object.
					self.ramp_manager = RampManager.RampManager(self, self.mode, self.time_step)
					print('Channel ' + str(self.channel_id) + ' initialised.')
		else:
			success_flag = False
		self.backend_object.comms_success_flag = success_flag
		
	def ServiceHardware(self):
		# Send starting timestamp for this update.
		if self.timing_flag == True:
			self.mq_timestamp.put([1, time.time()])
		comms_success_flag = False	
		if self.video_enabled_flag == True:
			if self.video_fault_flag == False:
				if self.event_vlogger_fault.is_set() == True:
					self.video_fault_flag = True
					self.mq_back_to_front.put((2, 'Video_fault'))
			else:
				if self.event_vlogger_fault.is_set() == False:
					self.video_fault_flag = False
					self.mq_back_to_front.put((2, 'Video_success'))
		
		if self.mode == 'idle':
			# Write timestamp 2 - Initial timestep 'Idle' command sent to Arduino.
			if self.timing_flag:
				self.mq_timestamp.put([2, time.time()])
			# Send the 'Idle' command to the Arduino and receive the current temperature.
			# We then send the idle command we expect 2 replies (temperature, relative humidity)
			self.current_time = time.time()
			comms_success_flag, responses = self.comms_manager.StageIdle(self.channel_id)
		# If the cooler is running in setpoint mode (ie, in 'setpoint', 'precooling' or 'ramping' mode):
		elif ((self.mode == 'setpoint') or (self.mode == 'profile_setpoint') or (self.mode == 'holding') or (self.mode == 'precooling') or (self.mode == 'ramping') or (self.mode == 'throttle')):
			if ((self.mode == 'setpoint') or (self.mode == 'profile_setpoint') or (self.mode == 'holding') or (self.mode == 'precooling') or (self.mode == 'ramping')):
				# If we are pre-cooling or ramping, update the RampManager object with the current temperature, from which it 
				# will determine whether to begin ramping (if pre-cooling) or the next setpoint temperature (if ramping).
				# Adjust the backend mode and send message to the front end accordingly.
				if self.ramping_flag == True:
					self.mode, self.setpoint, message_to_front_end, ramp_state_change = self.ramp_manager.NextSetpoint(self.temperature)
					self.pd.setpoint = self.setpoint
					if message_to_front_end[1].startswith('End of profile'):
						if self.logging_flag == True:
							if self.log_end_on_profile_end_flag == True:
								# Stop logging if this is required at the end of the ramp profile.
								self.ShutdownLogger()
								if ((self.video_enabled_flag == True) and (self.force_video_off == False)):
									self.StopVideo()
						# Clear the mpevent here to let the frontend widget in control know that we have reached the target setpoint.
						self.event_back_to_front['ramp_running_flag'].clear()
					if message_to_front_end[0] == True:
						# If we've reached the end of a state in the ramp profile, update the mode display with the new state.
						self.mq_back_to_front.put((2, 'Set_mode_label', message_to_front_end[1]))
						print(message_to_front_end[1])
						if ((self.force_video_off == False) and (self.video_enabled_flag == True) and (ramp_state_change[0] == True) and (self.logging_flag == True) and (self.log_video_split_flag == True)):
							# Change the video logger path if splitting the video log according to state.
							self.SwitchVideoLogPath(self.base_log_path + ramp_state_change[1] + '/')
					
				# Update the PID loop with the current temperature and obtain the resulting throttle value.
				self.throttle_setting = self.pd.Update(self.temperature)
							
			# When we call out with a throttle command, the command itself expects one reply (a newline character)
			# We then send the throttle value itself, expecting one reply (temperature).
			self.current_time = time.time()
			comms_success_flag, responses = self.comms_manager.StageThrottle(self.throttle_setting, self.channel_id)
		
		if comms_success_flag == True:
			self.last_temperature = self.temperature
			self.temperature = Utilities.PolynomialCorrection(float(responses[0]), self.tc_calibration_coeffs)
			self.PRT_temperature = Utilities.PolynomialCorrection(float(responses[1]), self.prt_calibration_coeffs)
			self.flow_rate = float(responses[2])
			
			if self.mode == 'throttle':
				# If we are in raw throttle-control mode, and gradient_detect_flag is not set (ie, we aren't determining max delta t),
				# if we breach max or min temperature limits, switch to setpoint mode with the setpoint equal to the limit just breached.
				if self.event_back_to_front['gradient_detect_flag'].is_set() == False:
					if ((self.temperature > self.temperature_limits['max']) or (self.temperature < self.temperature_limits['min'])):
						if self.temperature > self.temperature_limits['max']:
							new_setpoint = self.temperature_limits['max']
						else:
							new_setpoint = self.temperature_limits['min']
						self.SwitchToSetpointMode(new_setpoint)
				# If the gradient_detect_flag *is* set, we are auto-ranging at 100% throttle at the start of auto-calibration. 
				else:
					auto_ranging_complete = False
					# If there is a calibration lower temperature limit, check if we have passed it.
					if self.calibration_limit is not None:
						if self.temperature < self.calibration_limit:
							print('Auto-calibration minimum temperature limit reached.')
							self.calibration_limit = None
							auto_ranging_complete = True
					# If there is no limit or we have not passed it, check if the cooling-rate has fallen below X deg/min.
					if ((auto_ranging_complete == False) and ((time.time() - self.rolling_gradient_start_timestamp) > 2.0)):
						rolling_gradient = self.rolling_gradient.AddSample([self.temperature, self.current_time])
						target_rate_per_second = self.device_parameter_defaults['auto_range_min_cooling_rate_per_min'] / 60.0
						if rolling_gradient > target_rate_per_second:
							print('Minimum temperature at which ' + str(self.device_parameter_defaults['auto_range_min_cooling_rate_per_min']) + ' °C / minute achieveable = ' + '{:0.3f}'.format(self.temperature))
							auto_ranging_complete = True
					# If we have hit the limit, or slowed below X deg/min rate, write current temperature to temporary file and clear mp
					# event to signal end of auto-ranging to front end calibration widget.
					if auto_ranging_complete == True:
						with open('./min_temperature.tmp', 'w') as temporary_temperature_file:
							temporary_temperature_file.write('{:0.3f}'.format(self.temperature) + '\n')
						self.event_back_to_front['gradient_detect_flag'].clear()
			
			#~self.temperature_rates['old_1st_derivative'] = self.temperature_rates['1st_derivative']
			#~self.temperature_rates['1st_derivative'] = (self.temperature - self.last_temperature) / self.time_step
			#~self.temperature_rates['2nd_derivative'] = (self.temperature_rates['1st_derivative'] - self.temperature_rates['old_1st_derivative']) / self.time_step
			
			if self.shut_down_flag == False:
				# Write timestamp 3 - Final timestep reply received from Arduino.
				if self.timing_flag:
					self.mq_timestamp.put([3, self.current_time])
				# If logging, send data to various loggers via queue and event flag.
				if self.logging_flag == True:
					if self.logging_sub_counter >= self.logging_rate:
						sp = self.setpoint
						if sp != 'NA':
							sp = str(round(sp, 3))						
						if ((self.video_enabled_flag == True) and (self.force_video_off == False)):
							if self.video_fault_flag == False:
								if self.event_vlogger_fault.is_set() == False:
									self.mq_back_to_vlogger.put(('Go', {'index': str(self.logging_counter), 'temp': str(round(self.temperature, 3)), 'setpoint': sp, 'timestamp': self.current_time}))
									log_file_video_fault_flag = ''
								else:
									log_file_video_fault_flag = 'VIDEO_FAULT'
									self.video_fault_flag = True
									self.mq_back_to_front.put((2, 'Video_fault'))
							else:
								log_file_video_fault_flag = 'VIDEO_FAULT'
						else:
							log_file_video_fault_flag = 'VIDEO_DISABLED'
						if self.mode == 'idle':
							log_throttle_value = 'NA'
						else:
							log_throttle_value = str(round(self.throttle_setting, 2))
						self.mq_back_to_logger.put((str(round(self.current_time - self.logging_start_time, 3)) + ', ' + str(self.logging_counter) + ', ' + str(sp) + ', ' + str(round(self.temperature, 3)) + ', ' + str(round(self.PRT_temperature, 3)) + ', ' + str(round(self.flow_rate, 3)) + ', ' + log_throttle_value + ', ' + log_file_video_fault_flag))
						self.logging_sub_counter = 1
						self.logging_counter += 1
					else:
						self.logging_sub_counter += 1
						if self.timing_flag == True:
							self.mq_timestamp.put([0,])
				else:
					# If we aren't logging, write the current timestamp queue terminator.
					if self.timing_flag:
						self.mq_timestamp.put([0,])
				# Send current temperature / setpoint message to front end via queue.
				self.mq_back_to_front.put((1, 'Current_temperature', self.current_time, self.temperature))
				self.mq_back_to_front.put((1, 'Current_PRT_temperature', self.current_time, self.PRT_temperature))
				self.mq_back_to_front.put((1, 'Current_flowrate', self.current_time, self.flow_rate))
				if self.setpoint_flag == True:
					self.mq_back_to_front.put((1, 'Current_setpoint', self.current_time, self.setpoint))
				
				# Check for coolant flow fault start/end and update front end.
				if ((self.flow_rate < 1.0) and (self.flow_fault_flag == False)):
					self.flow_fault_flag = True
					self.mq_back_to_front.put((2, 'Flow_fault'))
				elif ((self.flow_rate > 1.0) and (self.flow_fault_flag == True)):
					self.flow_fault_flag = False
					self.mq_back_to_front.put((2, 'Flow_success'))
				
				#~# Check for peltier module overload fault start/end and update front end.
				#~if self.mode != 'idle':
					#~if (((self.throttle_setting > 95.0) and (self.temperature_rates['1st_derivative'] > 0.0)) or ((self.throttle_setting < -95.0) and (self.temperature_rates['1st_derivative'] < 0.0))):
						#~if ((self.overload_fault_flags['suspected'] == False) and (self.overload_fault_flags['confirmed'] == False)):
							#~self.overload_fault_flags['suspected'] = True
							#~self.overload_fault_flags['confirmed'] = False
							#~self.overload_fault_flags['start_time'] = time.time()
						#~elif ((self.overload_fault_flags['suspected'] == True) and (self.overload_fault_flags['confirmed'] == False)):
							#~if (time.time() - self.overload_fault_flags['start_time']) > self.device_parameter_defaults['overload_fault_threshold_seconds']:
								#~self.overload_fault_flags['confirmed'] = True
								#~self.mq_back_to_front.put((2, 'Overload_fault_start'))
					#~else:
						#~if ((self.overload_fault_flags['suspected'] == True) and (self.overload_fault_flags['confirmed'] == False)):
							#~self.overload_fault_flags['suspected'] = False
						#~elif ((self.overload_fault_flags['suspected'] == True) and (self.overload_fault_flags['confirmed'] == True)):
							#~self.overload_fault_flags['suspected'] = False
							#~self.overload_fault_flags['confirmed'] = False
							#~self.mq_back_to_front.put((2, 'Overload_fault_end'))
						
		return comms_success_flag
	
	def ServiceMessages(self, most_recent_message, comms_success_flag):
		if most_recent_message[0] == 'Throttle':
			self.SwitchToThrottleMode(new_throttle_setting = float(most_recent_message[1]))
		elif most_recent_message[0] == 'SetPoint':
			self.SwitchToSetpointMode(new_setpoint = float(most_recent_message[1]))
		elif most_recent_message[0] == 'Ramp':
			self.SwitchToRampMode(profile_repeats = most_recent_message[1], log_end_on_profile_end = most_recent_message[2], profile_path = most_recent_message[3], profile_table = most_recent_message[4])
		elif most_recent_message[0] == 'PIDConfig':
			self.pd.P = float(most_recent_message[1])
			self.pd.I = float(most_recent_message[2])
			self.pd.D = float(most_recent_message[3])
		elif most_recent_message[0] == 'LoggingRate':
			self.logging_rate = float(most_recent_message[1])
		elif most_recent_message[0] == 'StartLogging':
			if self.logging_flag == False:
				self.log_file_path = most_recent_message[1]
				self.force_video_off = bool(most_recent_message[2])
				self.force_log_data_file_path = bool(most_recent_message[3])
				self.StartLogging(self.force_video_off, self.force_log_data_file_path)
		elif most_recent_message[0] == 'StopLogging':
			if self.logging_flag == True:
				self.ShutdownLogger()
				if ((self.video_enabled_flag == True) and (self.force_video_off == False)):
					self.StopVideo()
		elif most_recent_message[0] == 'SetTimeStep':
			self.time_step = float(most_recent_message[1])
			self.backend_object.ShutdownTimer()
			self.backend_object.InitialiseTimer(self.time_step)
			self.ramp_manager.SetTimeStep(self.time_step)
			self.pd.time_step = self.time_step
		elif most_recent_message[0] == 'NewDatumTime':
			self.datum_time = time.time()
			self.mq_back_to_front.put((2, 'New_datum_time', self.datum_time))
		elif most_recent_message[0] == 'CalibrationOff':
			self.DisableTCCalibration()
			self.DisableTempLimits()
		elif most_recent_message[0] == 'CalibrationOn':
			self.EnableTCCalibration()
			self.LoadTempLimits()
		elif most_recent_message[0] == 'SetCalibrationLimit':
			if most_recent_message[1] is not None:
				self.calibration_limit = float(most_recent_message[1])
			else:
				self.calibration_limit = most_recent_message[1]
		elif most_recent_message[0] == 'Off':
			self.mq_back_to_front.put((2, 'Set_mode_label', 'Idle'))
			self.setpoint_flag = False
			self.setpoint = 'NA'
			self.ramping_flag = False
			self.mode = 'idle'
			if ((self.force_video_off == False) and (self.video_enabled_flag == True) and (self.log_video_split_flag == True) and (self.logging_flag == True)):
				self.SwitchVideoLogPath(self.base_log_path + self.mode + '/')
			if comms_success_flag == True:
				comms_success_flag, responses = self.comms_manager.StageThrottle(0.0, self.channel_id)
		elif most_recent_message[0] == 'ChangeVideoRes':
			x_resolution = int(most_recent_message[1].split('x')[0])
			y_resolution = int(most_recent_message[1].split('x')[1])
			self.SwitchVideoCaptureResolution(x_resolution, y_resolution)
		elif most_recent_message[0] == 'ChangeLogVideoSplitFlag':
			self.log_video_split_flag == most_recent_message[1]
		elif most_recent_message[0] == 'ShutDown':
			self.ShutDown(comms_success_flag)
		elif most_recent_message[0] == 'AllShutDown':
			self.backend_object.AllShutDown()
		return comms_success_flag
	
	def SwitchVideoLogPath(self, new_video_path):
		self.mq_back_to_vlogger.put(('Path', new_video_path))
	
	def SwitchVideoCaptureResolution(self, x, y):
		self.mq_back_to_vlogger.put(('Resolution', x, y))
	
	def StartLogging(self, force_video_off, force_log_data_file_path):
		self.logging_flag = True
		if not force_log_data_file_path:
			self.base_log_path = self.log_file_path + '/channel_' + str(self.channel_id) + '/'
			print('Creating base log folder ' + self.base_log_path)
			os.makedirs(self.base_log_path)
			self.InitialiseLogger(self.base_log_path + 'log_data.csv')
		else:
			self.base_log_path = self.log_file_path
			self.InitialiseLogger(self.base_log_path)
		if ((self.video_enabled_flag == True) and (force_video_off == False)):
			if self.log_video_split_flag == True:
				if self.ramping_flag == False:
					self.SwitchVideoLogPath(self.base_log_path + self.mode + '/')
				else:
					current_ramp_state = self.ramp_manager.GetRampState()
					self.SwitchVideoLogPath(self.base_log_path + current_ramp_state + '/')
			else:
				self.SwitchVideoLogPath(self.base_log_path)
			self.StartVideo()
		self.mq_back_to_front.put((2, 'Set_logging_label', 'ON'))
	
	def StartVideo(self):
		self.mq_back_to_vlogger.put(('Logon',))
	
	def StopVideo(self):
		self.mq_back_to_vlogger.put(('Logoff',))
	
	def InitialiseLogger(self, file_path):
		# Create a thread in which the data-logger will run (so that the back end loop never has to wait on file access).
		self.logging_flag = True
		self.logging_sub_counter = 1
		self.logging_counter = 0
		self.logging_start_time = time.time()
		self.mq_back_to_logger = Queue()
		self.logger_thread = Thread.Thread(target = Logger.Logger, args = (self.mq_back_to_logger, file_path))
		self.logger_thread.start()
		print('Logger for channel ' + str(self.channel_id) + ' started...')
		message_to_logger = 'Time (secs), Frame Number, Setpoint (°C), TC Temperature (°C), PRT Temperature (°C), Coolant Flowrate (L/min), Throttle (%)'
		if self.video_enabled_flag == True:
			message_to_logger = message_to_logger + ', Video Fault Flag'
		self.mq_back_to_logger.put((message_to_logger))
	
	def ShutdownLogger(self):
		self.mq_back_to_logger.put('Shutdown')
		self.logger_thread.join()
		print('Logger for channel ' + str(self.channel_id) + ' stopped...')
		self.logging_flag = False
		self.mq_back_to_front.put((2, 'Set_logging_label', 'OFF'))
	
	def ShutDown(self, comms_success_flag):
		self.setpoint_flag = False
		self.ramping_flag = False
		self.mode = 'shutdown'
		if comms_success_flag == True:
			success_flag, responses = self.comms_manager.StageOff(self.channel_id)
		if self.logging_flag == True:
			self.ShutdownLogger()
		if self.video_enabled_flag == True:
			self.ShutdownVideo()
		self.shut_down_flag = True
		print('Channel ' + str(self.channel_id) + ' shut down.')
		# This is the big one! When the tkinter event loop ends following the arrival of the shutdown command below,
		# we drop back into the runtime file and the main process ends after join()ing the back end and video handling
		# processes.
		self.mq_back_to_front.put('ShutDownConfirm')
		
	def ShutdownVideo(self):
		# We will use the mpevent between vlogger and backend to detect when the video logging process has finished.
		self.event_vlogger_fault.set()
		self.mq_back_to_vlogger.put(('ShutDown',))
		# Wait here until the mpevent from the vlogger is cleared to indicate that the vlogger process has flushed the 
		# vlogger_to_front queue and stopped.
		while self.event_vlogger_fault.is_set() == True:
			pass
		print('Channel ' + str(self.channel_id) + ' video logger shut down.')
	
	def LoadTempLimits(self):
		print("-----------------------------------------------------------------------------------")
		print('Loading calibrated temperature limits...')
		file_exists = os.path.isfile(self.device_parameter_defaults['calibrated_temp_limits_filepath'][self.channel_id])
		if file_exists:
			with open(self.device_parameter_defaults['calibrated_temp_limits_filepath'][self.channel_id], 'r') as temp_limit_file:
				calibrated_max_temp_limit = float(temp_limit_file.readline())
				calibrated_min_temp_limit = float(temp_limit_file.readline())
			self.temperature_limits['max'] = calibrated_max_temp_limit
			self.temperature_limits['min'] = calibrated_min_temp_limit
			print('Calibrated temperature limits found:')
			print('    Max = ' + '{:0.2f}'.format(calibrated_max_temp_limit) + ' °C')
			print('    Min = ' + '{:0.2f}'.format(calibrated_min_temp_limit) + ' °C')
			self.mq_back_to_front.put((2, 'Set_temp_limits', '{:0.2f}'.format(calibrated_max_temp_limit), '{:0.2f}'.format(calibrated_min_temp_limit)))
		else:
			print('No calibrated minimum temperature limits found, defaulting to:')
			print('    Max = ' + str(self.temperature_limits['max']) + ' °C')
			print('    Min = ' + str(self.temperature_limits['min']) + ' °C')
		print("--------------------------------------------------------------------------------")
	
	def DisableTempLimits(self):
		hard_max_limit = self.device_parameter_defaults['max_temperature_limit'][self.channel_id]
		hard_min_limit = self.device_parameter_defaults['min_temperature_limit'][self.channel_id]
		print("-----------------------------------------------------------------------------------")
		print('Temperature limits set to maximum range:')
		print('    Max = ' + '{:0.2f}'.format(hard_max_limit) + ' °C')
		print('    Min = ' + '{:0.2f}'.format(hard_min_limit) + ' °C')
		print("-----------------------------------------------------------------------------------")
		self.temperature_limits['min'] = hard_min_limit
		self.temperature_limits['max'] = hard_max_limit
		self.mq_back_to_front.put((2, 'Set_temp_limits', '{:0.2f}'.format(hard_max_limit), '{:0.2f}'.format(hard_min_limit)))
	
	def LoadCalibration(self, identity_string, calibration_path):
		print("--------------------------------------------------------------------------------")
		print('Loading calibration coefficients for ' + identity_string + ':')
		file_exists = os.path.isfile(calibration_path)
		if file_exists:
			with open(calibration_path, 'r') as csvfile:
				reader = csv.reader(csvfile, delimiter=',', quotechar='|')
				for row in reader:
					if not row[0].startswith('#'):
						calibration_coeffs = [float(i) for i in row]
						break
			# Formatting below specifies number of digits shown to the left of the decimal place in standard
			# notation, as shown at https://stackoverflow.com/a/34032934
			print('Calibration coefficients loaded:' + str(['{:0.3e}'.format(i) for i in calibration_coeffs]))
			print('(Shown to 3.d.p.)')
		else:
			print('No calibration file loaded, defaulting to y = x.')
			calibration_coeffs = [1.0, 0.0]
		print("--------------------------------------------------------------------------------")
		return calibration_coeffs
	
	def EnableTCCalibration(self):
		# Load the thermocouple calibration coefficients.
		self.tc_calibration_coeffs = self.LoadCalibration('Channel ' + str(self.channel_id) + ' internal thermocouple', self.device_parameter_defaults['tc_calibration_coeffs_filepath'][self.channel_id])
		self.event_back_to_front['calibration_zeroed_flag'].clear()
	
	def DisableTCCalibration(self):
		print("--------------------------------------------------------------------------------")
		print('Disabling calibration of ' + str(self.channel_id) + ' internal thermocouple.')
		print("--------------------------------------------------------------------------------")
		self.tc_calibration_coeffs = [1.0, 0.0]	
		self.event_back_to_front['calibration_zeroed_flag'].set()
	
	def SwitchToSetpointMode(self, new_setpoint):
		self.mq_back_to_front.put((2, 'Set_mode_label', 'Setpoint = ' + str(new_setpoint) + ' °C.'))
		self.mode = 'setpoint'
		self.setpoint_flag = True
		self.setpoint = new_setpoint
		self.pd.Initialise(self.temperature, self.setpoint)
		if self.ramping_flag == True:
			self.ramping_flag = False
		if ((self.force_video_off == False) and (self.video_enabled_flag == True) and (self.log_video_split_flag == True) and (self.logging_flag == True)):
			self.SwitchVideoLogPath(self.base_log_path + self.mode + '/')
	
	def SwitchToThrottleMode(self, new_throttle_setting):
		self.mq_back_to_front.put((2, 'Set_mode_label', 'Throttle = ' + str(new_throttle_setting) + ' %.'))
		self.mode = 'throttle'
		self.setpoint_flag = False
		self.setpoint = 'NA'
		self.throttle_setting = new_throttle_setting
		self.ramping_flag = False
		if ((self.force_video_off == False) and (self.video_enabled_flag == True) and (self.log_video_split_flag == True) and (self.logging_flag == True)):
			self.SwitchVideoLogPath(self.base_log_path + self.mode + '/')
		self.rolling_gradient = RollingGradient(window_width = 10, first_sample = [self.temperature, self.current_time])
		self.rolling_gradient_start_timestamp = self.current_time
	
	def SwitchToRampMode(self, profile_repeats, log_end_on_profile_end, profile_path, profile_table):
		self.setpoint_flag = True
		self.ramping_flag = True
		self.mode, self.setpoint, message_to_front_end, ramp_state_change = self.ramp_manager.NewProfile(self.temperature, profile_repeats, profile_path, profile_table)
		self.pd.Initialise(self.temperature, self.setpoint)
		self.log_end_on_profile_end_flag = log_end_on_profile_end
		if message_to_front_end[0] == True:
			self.mq_back_to_front.put((2, 'Set_mode_label', message_to_front_end[1]))
			print(message_to_front_end[1])
		if ((self.force_video_off == False) and (self.logging_flag == True) and (self.video_enabled_flag == True) and (ramp_state_change[0] == True) and (self.log_video_split_flag == True)):
			self.SwitchVideoLogPath(self.base_log_path + ramp_state_change[1] + '/')

class RollingGradient():
	def __init__ (self, window_width, first_sample):
		self.samples = [[0.0, 0.0] for i in range(window_width)]
		self.samples[0] = first_sample
		self.number_of_samples = 1
	
	def AddSample(self, sample):
		if self.number_of_samples < len(self.samples):
			self.number_of_samples += 1
		for i in range(self.number_of_samples - 1, 0, -1):
			self.samples[i] = self.samples[i - 1]
		self.samples[0] = sample		
		temps = np.array([self.samples[i][0] for i in range(self.number_of_samples)])
		times = np.array([self.samples[i][1] for i in range(self.number_of_samples)])
		fit_coeffs = np.polyfit(times, temps, 1)
		gradient = fit_coeffs[0]
		return gradient
		
#~class RollingAverage():
	#~def __init__ (self, window_width):
		#~self.number_of_samples = 0
		#~self.samples = [0.0 for i in range(window_width)]
	
	#~def GetAverage(self):
		#~return sum(self.samples) / len(self.samples)
	
	#~def AddSample(self, sample):
		#~if self.number_of_samples < len(self.samples):
			#~self.number_of_samples += 1
		#~for i in range(self.number_of_samples - 1, 0, -1):
			#~self.samples[i] = self.samples[i - 1]
		#~self.samples[0] = float(sample)
		#~return sum(self.samples[0:self.number_of_samples]) / self.number_of_samples

#~class FiFo():
	#~def __init__ (self, buffer_size):
		#~self.number_of_samples = 0
		#~self.samples = [0.0 for i in range(buffer_size)]
	
	#~def AddSample(self, sample):
		#~if self.number_of_samples < len(self.samples):
			#~self.number_of_samples += 1
		#~for i in range(self.number_of_samples - 1, 0, -1):
			#~self.samples[i] = self.samples[i - 1]
		#~self.samples[0] = float(sample)
		#~return self.samples[self.number_of_samples - 1]
		
