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

import tkinter as tk
import tkinter.constants
import os
import shutil
import datetime
import time
import numpy as np
import csv

class CalibrationWidget():
	def __init__ (self, parent, channel_id, comms_unique_id, root_tk, device_parameter_defaults, mq_front_to_back, event_back_to_front):
		self.device_parameter_defaults = device_parameter_defaults
		self.parent = parent
		self.channel_id = channel_id
		self.comms_unique_id = comms_unique_id
		self.mq_front_to_back = mq_front_to_back
		self.event_back_to_front = event_back_to_front
		self.root_tk = root_tk
		
		if str(self.comms_unique_id) == '0':
			self.type_identifier = '0'
		else:
			self.type_identifier = str(self.comms_unique_id)[0:2]
		print("TYPE", self.type_identifier)
		self.calibration_fit_polynomial_order = self.device_parameter_defaults['calibration_fit_polynomial_order'][self.type_identifier]
		self.tc_calibration_temp_data_filepath = self.device_parameter_defaults['tc_calibration_temp_data_filepath'][self.channel_id]
		self.tc_calibration_final_data_filepath = self.device_parameter_defaults['tc_calibration_final_data_filepath'][self.channel_id]
		self.tc_calibration_coeffs_filepath = self.device_parameter_defaults['tc_calibration_coeffs_filepath'][self.channel_id]
		self.tc_calibration_ramp_profile_filepath = self.device_parameter_defaults['tc_calibration_ramp_profile_filepath'][self.type_identifier]
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
		
		# Zero the thermocouple calibration before logging the calibration ramp.
		self.mq_front_to_back.put(('CalibrationOff',))
		
		# Check if temporary file already exists and if so, delete it.
		file_exists = os.path.isfile(self.tc_calibration_temp_data_filepath)
		if file_exists:
			os.remove(self.tc_calibration_temp_data_filepath)
		else:
			# Check if calibration file directory for this channel exists, and if not, create it.
			dir_path = '/'.join(self.tc_calibration_temp_data_filepath.split('/')[0:-1])
			print(dir_path)
			if os.path.isdir(dir_path) == False:
				os.mkdir(dir_path)
		
		# Set the back_to_front mpevent. We are going to poll on this until it is cleared by the back end to signal
		# the end of the ramp.
		self.event_back_to_front.set()
		# Start the calibration ramp.
		self.mq_front_to_back.put(('Ramp', 1, True, self.tc_calibration_ramp_profile_filepath, None))
		# Start logging.
		self.mq_front_to_back.put(('StartLogging', self.tc_calibration_temp_data_filepath, True, True))
		self.PollEvent()
	
	def PollEvent(self):
		# We're polling event_back_to_front until it's been cleared by the backend to say that the logger thread has
		# been stopped at the end of the calibration ramp profile.
		if self.cancelled_flag == False:
			#~self.widget_window.grab_set()
			if self.event_back_to_front.is_set() == False:
				# The calibration ramp is completed!
				self.Finish()
			else:
				# Re-prime the poll event.
				self.poll_id = self.widget_window.after(250, self.PollEvent)	
	
	def PassFunc(self):
		pass
	
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
		row_to_write = str(fit_coefficients[0])
		for current_coefficient in fit_coefficients[1:]:
			row_to_write += ','
			row_to_write += str(current_coefficient)
		
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
		new_tc_calibration_file = open(self.tc_calibration_coeffs_filepath, 'a')
		new_tc_calibration_file.write(row_to_write)
		new_tc_calibration_file.close()
		
		# Create the new calibration data file.
		shutil.copy2(self.tc_calibration_temp_data_filepath, self.tc_calibration_final_data_filepath)
		
		# Check if temporary file exists and if so, delete it.
		file_exists = os.path.isfile(self.tc_calibration_temp_data_filepath)
		if file_exists:
			os.remove(self.tc_calibration_temp_data_filepath)
		
		# Re-load and enable the thermocouple calibration (freshly updated!).
		self.mq_front_to_back.put(('CalibrationOn',))
		# Turn the stage 'off'.
		self.mq_front_to_back.put(('Off',))
		
		# And we are done!
		self.parent.UnbindParentClicks(self.parent.top)
		if self.parent.video_enabled == True:
			self.parent.UnbindParentClicks(self.parent.video_window)
		self.window_open_flag = False
		self.widget_window.destroy()
	
	def GenerateCalibrationWidget(self):
		self.widget_window = tk.Toplevel(self.root_tk)
		self.widget_window.title("Thermocouple Calibration")
		self.widget_window.geometry("300x100")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.widget_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.widget_window.resizable(False, False)
		self.widget_window_frame = tk.Frame(self.widget_window, bd = 1, relief = tk.RIDGE)
		self.widget_window_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_cancel = tk.Button(self.widget_window_frame, text="Cancel", font = ("Arial", 14), command=self.Cancel)
		self.button_cancel.pack(side = "bottom", expand = "true", fill = tk.BOTH)
		#~# Route all events to the new widget - In effect prevents user interaction with the parent front end window.
		#~# Once we 'destroy' this widget, control will be passed back to the parent front end window.
		#~self.widget_window.grab_set()
		self.widget_window.lift()
		self.parent.BindParentClicks(self.parent.top, self.widget_window)
		if self.parent.video_enabled == True:
			self.parent.BindParentClicks(self.parent.video_window, self.widget_window)
