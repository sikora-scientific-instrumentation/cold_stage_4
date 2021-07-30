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

import tkinter as tk
import tkinter.constants
import os
import shutil
import datetime
import time
import numpy as np
import csv

import Utilities

class CalibrationWidget():
	def __init__ (self, parent, channel_id, comms_unique_id, root_tk, device_parameter_defaults, mq_front_to_back, event_back_to_front):
		self.device_parameter_defaults = device_parameter_defaults
		self.parent = parent
		self.channel_id = channel_id
		self.comms_unique_id = comms_unique_id
		self.mq_front_to_back = mq_front_to_back
		self.event_back_to_front = event_back_to_front
		self.root_tk = root_tk
		
		self.calibration_fit_polynomial_order = self.device_parameter_defaults['calibration_fit_polynomial_order']
		self.temperature_steps = self.device_parameter_defaults['auto_calibration_temperature_steps']
		self.auto_range_max_throttle = self.device_parameter_defaults['auto_range_max_throttle']
		
		self.tc_calibration_temp_data_filepath = self.device_parameter_defaults['tc_calibration_temp_data_filepath'][self.channel_id]
		self.tc_calibration_final_data_filepath = self.device_parameter_defaults['tc_calibration_final_data_filepath'][self.channel_id]
		self.tc_calibration_coeffs_filepath = self.device_parameter_defaults['tc_calibration_coeffs_filepath'][self.channel_id]
		self.temp_limit_filepath = self.device_parameter_defaults['calibrated_temp_limits_filepath'][self.channel_id]
		
		self.calibration_temperature_limits = {'max': self.device_parameter_defaults['max_temperature_limit'][self.channel_id], 'min': self.device_parameter_defaults['min_temperature_limit'][self.channel_id]}
		self.calibration_limit = None
		self.cancelled_flag = False
		self.window_open_flag = False
		
	def Run(self, time_step, logging_rate):
		self.cancelled_flag = False
		self.GenerateCalibrationWidget()
		self.window_open_flag = True
		
		# Store the original time-step and logging rate.
		self.original_time_step = time_step
		self.original_logging_rate = logging_rate
		
		# Ensure the stage is 'off' to begin.
		self.mq_front_to_back.put(('Off',))
		
		# Set the time-step and logging rate to the calibration defaults.
		self.mq_front_to_back.put(('SetTimeStep', self.device_parameter_defaults['tc_calibration_time_step']))
		self.mq_front_to_back.put(('LoggingRate', self.device_parameter_defaults['tc_calibration_logging_rate']))
		
		# Check if temporary file already exists and if so, delete it.
		file_exists = os.path.isfile(self.tc_calibration_temp_data_filepath)
		if file_exists:
			os.remove(self.tc_calibration_temp_data_filepath)
		else:
			# There should now always be a calibration file directory for each channel, as it will be created at startup
			# if there is not one containing a default PRT calibration file.
			pass
		
		# Zero the thermocouple calibration before logging the calibration ramp.
		self.mq_front_to_back.put(('CalibrationOff',))
		
		self.mode = 0
		self.PollEvent()
	
	def PollEvent(self):
		repeat_poll_flag = False
		if self.cancelled_flag == False:
			if self.mode == 0:
				# We are waiting for confirmation that the backend has zeroed the calibration coeffs.
				if self.event_back_to_front['calibration_zeroed_flag'].is_set() == True:
					self.mode = 1
				repeat_poll_flag = True
			elif self.mode == 1:
				# We are waiting for the user to start the auto-calibration.
				# When they click start, self.mode will be set = 2.
				repeat_poll_flag = True
			elif self.mode == 2:
				# We set the gradient_detect_flag mp event to turn off the back end temp limits and turn on the temperature
				# gradient detector, send a command to the back end to set the lower calibration limit (either a temperature or None)
				# and then send the command to set the cold-stage to 100% throttle mode to begin the auto-ranging.
				self.event_back_to_front['gradient_detect_flag'].set()
				print('Determining minimum temperature at which ' + str(self.device_parameter_defaults['auto_range_min_cooling_rate_per_min']) + ' °C / minute achieveable...')
				self.mq_front_to_back.put(('SetCalibrationLimit', self.calibration_limit))
				self.mq_front_to_back.put(('Throttle', self.device_parameter_defaults['auto_range_max_throttle']))
				self.mode = 3
				repeat_poll_flag = True
			elif self.mode == 3:
				# We are waiting to hit ~1k/min rate at 100% throttle.
				if self.event_back_to_front['gradient_detect_flag'].is_set() == False:
					with open('./min_temperature.tmp', 'r') as temporary_temperature_file:
						minimum_temperature_reached = float(temporary_temperature_file.readline())
					calibration_table = self.GenerateCalibrationTable(minimum_temperature_reached, self.temperature_steps)
					# Start the calibration ramp.
					self.mq_front_to_back.put(('Ramp', 1, True, None, calibration_table))
					# Start logging.
					self.mq_front_to_back.put(('StartLogging', self.tc_calibration_temp_data_filepath, True, True))
					self.event_back_to_front['ramp_running_flag'].set()
					self.mode = 4
				repeat_poll_flag = True
			elif self.mode == 4:
				# We're polling event_back_to_front until it's been cleared by the backend to say that the logger thread has
				# been stopped at the end of the calibration ramp profile.
				if self.event_back_to_front['ramp_running_flag'].is_set() == False:
					# The calibration ramp is completed!
					repeat_poll_flag = False
					self.Finish()
				else:
					repeat_poll_flag = True
			if repeat_poll_flag == True:
				# Re-prime the poll event.
				self.poll_id = self.widget_window.after(250, self.PollEvent)	
	
	def PassFunc(self):
		pass
	
	def ClickStart(self):
		if self.ClicksAreActive() == True:
			self.Start()
	
	def Start(self):
		if self.mode == 1:
			start_now = False
			if self.calibration_limit_flag.get() == True:
				# If the calibration limit checkbox is set, we validate the entry. If it can't be turned into a float or is outside the limits
				# we show a generic warning window and clear the entry field.
				succeded = False
				try:
					limit_entered = float(self.entry_calibration_limit.get())
					if ((limit_entered > self.calibration_temperature_limits['max']) or (limit_entered < self.calibration_temperature_limits['min'])):
						succeded = False
					else:
						succeded = True
				except:
					succeded = False
				if succeded == False:
					self.parent.GenerateGenericWarningWindow("Parameter entry error", "Temperature limit must be floating value between " + str(self.calibration_temperature_limits['max']) + " and " + str(self.calibration_temperature_limits['min']) + " °C.")
					self.entry_calibration_limit.delete(0, "end")
				else:
					self.calibration_limit = limit_entered
					start_now = True
			else:
				self.calibration_limit = None
				start_now = True
			if start_now == True:
				self.button_start.config(state = tk.DISABLED)
				self.entry_calibration_limit.config(state = tk.DISABLED)
				self.checkButton_calibration_limit.config(state = tk.DISABLED)
				self.mode = 2
		
	def ClickCancel(self):
		if self.ClicksAreActive() == True:
			self.Cancel()
		
	def ClicksAreActive(self):
		return ((self.parent.comms_fault_warning_open == False) and (self.parent.flow_fault_warning_open == False) and (self.parent.video_fault_warning_open == False) and (self.parent.generic_warning_window_open == False))
	
	def Cancel(self):
		self.cancelled_flag = True
		# If there is a poll call pending, cancel it.
		if self.poll_id in self.widget_window.tk.call("after", "info"):
				self.widget_window.after_cancel(self.poll_id)
		# If we are in the auto-range part of the auto-calibration clear the 'gradient detection' flag.
		self.event_back_to_front['gradient_detect_flag'].clear()
		# If we are in the main ramp part of the auto-calibration clear the 'ramp running' flag.
		self.event_back_to_front['ramp_running_flag'].clear()
		# Stop logging.
		self.mq_front_to_back.put(('StopLogging',))
		# Cancel the ramp if it's running by turning the stage 'off'.
		self.mq_front_to_back.put(('Off',))
		# Check if temporary file already exists and if so, delete it.
		file_exists = os.path.isfile(self.tc_calibration_temp_data_filepath)
		if file_exists:
			os.remove(self.tc_calibration_temp_data_filepath)
		# Re-load and enable the former thermocouple calibration.
		self.mq_front_to_back.put(('CalibrationOn',))
		# Revert to the original time_step and logging_rate.
		self.mq_front_to_back.put(('SetTimeStep', self.original_time_step))
		self.mq_front_to_back.put(('LoggingRate', self.original_logging_rate))
		self.parent.UnbindParentClicks(self.parent.top)
		if self.parent.video_enabled == True:
			self.parent.UnbindParentClicks(self.parent.video_window)
		self.window_open_flag = False
		self.widget_window.destroy()
		
	def Finish(self):
		# Revert to the original time_step and logging_rate.
		self.mq_front_to_back.put(('SetTimeStep', self.original_time_step))
		self.mq_front_to_back.put(('LoggingRate', self.original_logging_rate))
		
		# We now have the calibration ramp data recorded. Next we need to parse it to get our averaged multi-point
		# calibration data, then we need to fit that to get the calibration coefficients. Lastly, we backup the old
		# calibration coefficients file, write the new one then re-load the coefficients...
		
		# Get indices of last 60 rows for each setpoint...
		setpoint_row_flag = False
		sampling_ranges = []
		tc_averages = []
		prt_averages = []
		with open(self.tc_calibration_temp_data_filepath, 'r') as csvfile:
			reader = csv.reader(csvfile, delimiter=',', quotechar='|')
			row_index = 0
			for row_index, row in enumerate(reader):
				if row_index == 0:
					continue
				elif row_index > 0:
					if row[2] == 'NA':
						setpoint_row_flag = False
						continue
					elif (row[2] != 'NA') and (setpoint_row_flag == False):
						last_setpoint = row[2]
						setpoint_row_flag = True
					elif (row[2] != 'NA') and (setpoint_row_flag == True):
						if row[2] != last_setpoint:
							sampling_ranges.append([row_index - 60, row_index])
							last_setpoint = row[2]
			if setpoint_row_flag == True:
				sampling_ranges.append([row_index - 60, row_index])
			
		# Get averages of each of these sampling ranges, for both tc and prt.
		with open(self.tc_calibration_temp_data_filepath, 'r') as csvfile:
			reader = csv.reader(csvfile, delimiter=',', quotechar='|')
			tc_samples = [[] for i in range(len(sampling_ranges))]
			prt_samples = [[] for i in range(len(sampling_ranges))]
			for i, row in enumerate(reader):
				if i > sampling_ranges[-1][1]:
					break
				for j, current_sampling_range in enumerate(sampling_ranges):
					if (i >= current_sampling_range[0]) and (i < current_sampling_range[1]):
						tc_samples[j].append(float(row[3]))
						prt_samples[j].append(float(row[4]))
			for tc_sample in tc_samples:
				tc_averages.append(np.mean(tc_sample))
			for prt_sample in prt_samples:
				prt_averages.append(np.mean(prt_sample))
			
		# Determine the fit coefficients and build the string to write to the calibration csv file.
		fit_coefficients = np.polyfit(tc_averages, prt_averages, self.calibration_fit_polynomial_order)
		coeffs_row_to_write = str(fit_coefficients[0])
		for current_coefficient in fit_coefficients[1:]:
			coeffs_row_to_write += ','
			coeffs_row_to_write += str(current_coefficient)
		
		# If there is an existing calibration coefficients file, back it up.
		stamp = datetime.datetime.today()
		date_stamp = str(stamp).split(' ')[0]
		time_stamp = str(stamp).split(' ')[1].replace(':','-')
		file_exists = os.path.isfile(self.tc_calibration_coeffs_filepath)
		if file_exists:
			new_filename = self.tc_calibration_coeffs_filepath[:-4] + '_backed_up_on_' + date_stamp + '_at_' + time_stamp + '.csv'
			os.rename(self.tc_calibration_coeffs_filepath, new_filename)
		
		# If there is an existing calibration data file, back it up.
		file_exists = os.path.isfile(self.tc_calibration_final_data_filepath)
		if file_exists:
			new_filename = self.tc_calibration_final_data_filepath[:-4] + '_backed_up_on_' + date_stamp + '_at_' + time_stamp + '.csv'
			os.rename(self.tc_calibration_final_data_filepath, new_filename)
		
		# Create the new calibration coefficients file.
		calibration_timestamp_string = '# Calibrated on ' + date_stamp + ' at ' + time_stamp + '\n'
		new_tc_calibration_file = open(self.tc_calibration_coeffs_filepath, 'w')
		new_tc_calibration_file.write(calibration_timestamp_string)
		new_tc_calibration_file.write(coeffs_row_to_write)
		new_tc_calibration_file.close()
		
		# Create the new calibration data file.
		shutil.copy2(self.tc_calibration_temp_data_filepath, self.tc_calibration_final_data_filepath)
		
		# Check if temporary file exists and if so, delete it.
		file_exists = os.path.isfile(self.tc_calibration_temp_data_filepath)
		if file_exists:
			os.remove(self.tc_calibration_temp_data_filepath)
		
		# If there is an existing temperature limit file, back it up.
		file_exists = os.path.isfile(self.temp_limit_filepath)
		if file_exists:
			new_filename = self.temp_limit_filepath[:-4] + '_backed_up_on_' + date_stamp + '_at_' + time_stamp + '.csv'
			os.rename(self.temp_limit_filepath, new_filename)
		
		# Create the new minimum temperature limit file.
		max_temperature_reached = tc_averages[0]
		min_temperature_reached = tc_averages[-1]
		new_temp_limit_file = open(self.temp_limit_filepath, 'w')
		corrected_max_temp_limit = Utilities.PolynomialCorrection(max_temperature_reached, fit_coefficients)
		corrected_min_temp_limit = Utilities.PolynomialCorrection(min_temperature_reached, fit_coefficients)
		new_temp_limit_file.write('{:0.3f}'.format(corrected_max_temp_limit) + '\n')
		new_temp_limit_file.write('{:0.3f}'.format(corrected_min_temp_limit) + '\n')
		new_temp_limit_file.close()
		
		# Re-load and enable the thermocouple calibration (freshly updated!).
		self.mq_front_to_back.put(('CalibrationOn',))
		# Turn the stage 'off'.
		self.mq_front_to_back.put(('Off',))
		
		# And we are done!
		print('*** AUTO-CALIBRATION COMPLETE ***')
		self.parent.UnbindParentClicks(self.parent.top)
		if self.parent.video_enabled == True:
			self.parent.UnbindParentClicks(self.parent.video_window)
		self.window_open_flag = False
		self.widget_window.destroy()
	
	def GenerateCalibrationWidget(self):
		self.widget_window = tk.Toplevel(self.root_tk)
		self.widget_window.title("Thermocouple Calibration")
		self.widget_window.geometry("300x120")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.widget_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.widget_window.resizable(False, False)
		self.widget_window_frame = tk.Frame(self.widget_window, bd = 1, relief = tk.RIDGE)
		self.widget_window_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.calibration_limit_flag = tk.BooleanVar()
		self.calibration_limit_flag.set(False)
		self.checkButton_calibration_limit = tk.Checkbutton(self.widget_window_frame, text = "Apply calibration lower temperature limit (°C)", variable = self.calibration_limit_flag, onvalue = True, offvalue = False, command = self.ToggleCalibrationLimit)
		self.checkButton_calibration_limit.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.entry_calibration_limit = tk.Entry(self.widget_window_frame, width = 8, font = ("Arial", 11))
		self.entry_calibration_limit.insert(0, "-40.0")
		self.entry_calibration_limit.configure(state = tk.DISABLED)
		self.entry_calibration_limit.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_start = tk.Button(self.widget_window_frame, text="Start", font = ("Arial", 14), command=self.ClickStart)
		self.button_start.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_cancel = tk.Button(self.widget_window_frame, text="Cancel", font = ("Arial", 14), command=self.ClickCancel)
		self.button_cancel.pack(side = "top", expand = "true", fill = tk.BOTH)
		#~# Route all events to the new widget - In effect prevents user interaction with the parent front end window.
		#~# Once we 'destroy' this widget, control will be passed back to the parent front end window.
		self.widget_window.lift()
		self.parent.BindParentClicks(self.parent.top, self.widget_window)
		if self.parent.video_enabled == True:
			self.parent.BindParentClicks(self.parent.video_window, self.widget_window)
	
	def ToggleCalibrationLimit(self):
		if self.entry_calibration_limit.cget('state') == tk.DISABLED:
			self.entry_calibration_limit.config(state = tk.NORMAL)
		else:
			self.entry_calibration_limit.config(state = tk.DISABLED)
	
	def GenerateCalibrationTable(self, minimum_temperature_reached, steps):
		temperatures = np.linspace(self.device_parameter_defaults['max_temperature_limit'][self.channel_id], minimum_temperature_reached, steps)
		calibration_table = []
		for i in range(steps):
			calibration_table.append(['setpoint', temperatures[i]])
			calibration_table.append(['hold', 120.0])
		return calibration_table
