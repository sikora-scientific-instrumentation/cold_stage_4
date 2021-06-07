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

import csv

class RampManager():
	def __init__ (self, parent, mode, time_step):
		self.parent = parent
		self.mode = mode
		self.time_step = time_step
		self.ramp = None
		self.hold = None
		
	def NewProfile(self, current_temperature, repeats, profile_path = None, profile_table = None):
		self.repeats = repeats
		self.repeat_count = 1
		if ((profile_path is not None) and (profile_table is None)):
			self.profile = self.__LoadProfile(profile_path)
		elif ((profile_path is None) and (profile_table is not None)):
			self.profile = profile_table
		else:
			print('Help!')
		print(self.profile)
		self.stages = len(self.profile)
		self.current_stage = 0
		self.setpoint = current_temperature
		self.last_temperature = current_temperature
		# Load initial profile setpoint.
		self.mode, self.setpoint, message, ramp_state_change = self.__NextStage()
		return self.mode, self.setpoint, message, ramp_state_change
	
	def __NextStage(self):
		if self.current_stage < len(self.profile):
			new_stage = self.profile[self.current_stage]
			print('Repeat ' + str(self.repeat_count) + '/' + str(self.repeats) + ', Stage ' + str(self.current_stage + 1) + '/' + str(len(self.profile)) + ',')
		else:
			self.current_stage = 0
			if self.repeat_count < self.repeats:
				self.repeat_count += 1
				new_stage = self.profile[self.current_stage]
				print('Repeat ' + str(self.repeat_count) + '/' + str(self.repeats) + ', Stage ' + str(self.current_stage + 1) + '/' + str(len(self.profile)) + ',')
			else:
				new_stage = ['completed']
				print('Profile completed, ')
		if new_stage[0] == 'hold':
			new_mode = 'holding'
			new_setpoint = self.setpoint
			hold_duration = float(new_stage[1])
			self.hold = Hold(self.time_step, hold_duration)
			message = [True, 'Holding at ' + str(round(new_setpoint, 3)) + ' °C for ' + str(hold_duration) + ' seconds.']
		elif new_stage[0] == 'ramp':
			ramp_start_temperature = float(new_stage[1])
			ramp_end_temperature = float(new_stage[2])
			ramp_rate = float(new_stage[3])
			if (((ramp_end_temperature < ramp_start_temperature) and (ramp_rate > 0.0)) or ((ramp_end_temperature > ramp_start_temperature) and (ramp_rate < 0.0))):
				ramp_rate = ramp_rate * -1.0
			new_setpoint = ramp_start_temperature
			self.ramp = Ramp(self.time_step, ramp_start_temperature, ramp_end_temperature, ramp_rate)
			# Determine if we should immediately start ramping the setpoint, or if we need to 'pre-cool' to the
			# ramp start temperature.
			# We will define the acceptable threshold range around the ramp start temperature to be +/- 10 times the ramp
			# setpoint increment-per-tick, unless this is < 0.02, in which case it will be capped at 0.02. This prevents
			# the situation whereby at very slow ramp rates +/- 10 times the ramp increment around the ramp start temperature
			# would actually lie between two adjacent discrete temperature values at our sensing resolution limit.
			if (10.0 * abs(self.ramp.increment)) <= 0.02:
				threshold = 0.02
			else:
				threshold = 10.0 * abs(self.ramp.increment)
			if ((self.last_temperature <= (ramp_start_temperature + threshold)) and (self.last_temperature >= (ramp_start_temperature - threshold))):
				new_mode = 'ramping'
				message = [True, 'Ramping from ' + str(round(ramp_start_temperature, 3)) + ' °C to ' + str(round(ramp_end_temperature, 3)) + ' °C at ' + str(round(ramp_rate, 3)) + ' °/sec.']
			else:
				new_mode = 'precooling'
				message = [True, 'Pre-cooling to ' + str(round(new_setpoint, 3)) + ' °C.']
		elif new_stage[0] == 'setpoint':
			new_mode = 'profile_setpoint'
			new_setpoint = float(new_stage[1])
			message = [True, 'Adjusting to ' + str(round(new_setpoint, 3)) + ' °C.']
		elif new_stage[0] == 'completed':
			new_mode = 'setpoint'
			new_setpoint = self.setpoint
			message = [True, 'End of profile, holding at ' + str(round(new_setpoint, 3)) + ' °C.']
		self.current_stage += 1
		print('Switching to mode: ' + str(new_mode))
		ramp_state_change = [True, new_mode + '_' + str(self.repeat_count) + '_' + str(self.current_stage)]
		return new_mode, new_setpoint, message, ramp_state_change
	
	def NextSetpoint(self, current_temperature):
		message_to_front_end = [False, '']
		ramp_state_change = [False, '']
		if self.mode == 'precooling':
			# Determine if we have reached an acceptable temperature to begin ramping the temperature setpoint.
			# We will define the acceptable threshold range around the ramp start temperature to be +/- 10 times the ramp
			# setpoint increment-per-tick, unless this is < 0.02, in which case it will be capped at 0.02. This prevents
			# the situation whereby at very slow ramp rates +/- 10 times the ramp increment around the ramp start temperature
			# would actually lie between two adjacent discrete temperature values at our sensing resolution limit.
			# ...this happened, true story...
			if (10.0 * abs(self.ramp.increment)) <= 0.02:
				threshold = 0.02
			else:
				threshold = 10.0 * abs(self.ramp.increment)
			if ((self.last_temperature <= (self.ramp.start_temperature + threshold)) and (self.last_temperature >= (self.ramp.start_temperature - threshold))):
				self.mode = 'ramping'
				ramp_message = 'Ramping from ' + str(round(self.ramp.start_temperature, 3)) + ' °C to ' + str(round(self.ramp.end_temperature, 3)) + ' °C at ' + str(round(self.ramp.rate, 3)) + ' °/sec.'
				ramp_state = self.mode + '_' + str(self.repeat_count) + '_' + str(self.current_stage)
				message_to_front_end = [True, ramp_message]
				ramp_state_change = [True, ramp_state]
				print('Switching to mode: ramping')
		elif self.mode == 'ramping':
			new_setpoint, finished_flag = self.ramp.Ramp()
			if finished_flag == True:
				self.mode, self.setpoint, message_to_front_end, ramp_state_change = self.__NextStage()
			else:
				self.setpoint = new_setpoint
		elif self.mode == 'holding':
			finished_flag = self.hold.Hold()
			if finished_flag == True:
				self.mode, self.setpoint, message_to_front_end, ramp_state_change = self.__NextStage()
		elif self.mode == 'profile_setpoint':
			if (((self.last_temperature >= self.setpoint) and (current_temperature <= self.setpoint)) or ((self.last_temperature <= self.setpoint) and (current_temperature >= self.setpoint))):
				self.mode, self.setpoint, message_to_front_end, ramp_state_change = self.__NextStage()
		self.last_temperature = current_temperature
		# Prevent ramp manager from setting setpoint outside current limits.
		if self.setpoint < self.parent.temperature_limits['min']:
			self.setpoint = self.parent.temperature_limits['min']
		elif self.setpoint > self.parent.temperature_limits['max']:
			self.setpoint = self.parent.temperature_limits['max']
		return self.mode, self.setpoint, message_to_front_end, ramp_state_change
	
	def SetTimeStep(self, time_step):
		self.time_step = time_step
		if self.ramp is not None:
			self.ramp.SetTimeStep(time_step)
		if self.hold is not None:
			self.hold.SetTimeStep(time_step)
	
	def __LoadProfile(self, profile_path):
		profile = []
		with open(profile_path, 'r') as csvfile:
			reader = csv.reader(csvfile, delimiter=',', quotechar='|')
			for row in reader:
				if len(row) > 0:
					if ((row[0] == 'hold') or (row[0] == 'setpoint') or (row[0] == 'ramp')):
						profile.append(row)
		return profile
	
	def GetRampState(self):
		ramp_state = self.mode + '_' + str(self.repeat_count) + '_' + str(self.current_stage)
		return ramp_state

class Hold():
	def __init__(self, time_step, hold_duration):
		self.time_step = time_step
		self.hold_duration = hold_duration
		self.hold_duration_ticks = self.hold_duration / self.time_step
		self.hold_counter = 0
	
	def Hold(self):
		if self.hold_counter < self.hold_duration_ticks:
			self.hold_counter += 1
			finished_flag = False
		else:
			finished_flag = True
		return finished_flag
	
	def SetTimeStep(self, new_time_step):
		remaining_time_in_ticks = self.hold_duration_ticks = self.hold_counter
		remaining_time_in_seconds = remaining_time_in_ticks * self.time_step
		self.hold_duration_ticks = remaining_time_in_seconds / new_time_step
		self.time_step = new_time_step
		self.hold_counter = 0

class Ramp():
	def __init__(self, time_step, ramp_start_temperature, ramp_end_temperature, ramp_rate):
		self.start_temperature = float(ramp_start_temperature)
		self.end_temperature = float(ramp_end_temperature)
		self.rate = float(ramp_rate)
		self.time_step = float(time_step)
		self.current_setpoint = self.start_temperature 
		self.increment = (self.rate * self.time_step)
	
	def Ramp(self):
		if (((self.increment < 0.0) and (self.current_setpoint <= (self.end_temperature + (-0.5 * self.increment)))) or ((self.increment > 0.0) and (self.current_setpoint >= (self.end_temperature - (-0.5 * self.increment))))):
			finished_flag = True
		else:
			finished_flag = False
			self.current_setpoint += self.increment
		return self.current_setpoint, finished_flag
	
	def SetTimeStep(self, new_time_step):
		if new_time_step <= 0.0:
			new_time_step = 0.1
		self.time_step = new_time_step
		self.increment = (self.ramp_rate * self.time_step)
