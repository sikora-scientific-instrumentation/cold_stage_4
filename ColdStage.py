"""
########################################################################
#                                                                      #
#                           Cold Stage 4                               #
#                  Copyright 2020 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
#         A software tool for the control of an inexpensive            #
#       multi-channel solid-state temperature control platform         #
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

from multiprocessing import Process, Queue, Event
import threading as Thread
import tkinter as tk
import tkinter.constants
import tkinter.messagebox
import os

import StartUpConfig
import FrontEnd
import BackEnd
import VideoHandler
import Utilities

class CoolerControl():
	def __init__ (self):
		self.device_parameter_defaults = {
			# Device defaults.
			'simulation_number_of_channels': 1,
			'comms_baud_rate': 57600,
			'timing_info_flag' : 0,
			'time_step' : 0.2,
			# Channel defaults.
			#	Logging
			'stop_logging_at_profile_end_flag' : [1, 1, 1, 1],
			'start_logging_at_profile_start_flag' : [1, 1, 1, 1],
			'logging_rate' : [5, 5, 5, 5],
			#	Plotting
			'enable_plotting_flag' : [1, 0, 0, 0],
			'plot_update_rate' : [5, 5, 5, 5],
			'plot_span' : [2000, 2000, 2000, 2000],
			#	Video
			'webcam_image_file_format': '.jpg',
			'webcam_available_dimensions' : ["320x240", "640x480", "800x600", "1280x720"],
			'webcam_default_dimensions': ["640x480", "320x240", "320x240", "320x240"],
			'log_video_split_flag' : [0, 0, 0, 0],
			#	Control
			'drive_mode' : [2, 2, 2, 2],
			'pid_coefficients': [{'P' : 0.4, 'I': 0.0, 'D': 2.1}, {'P' : 0.4, 'I': 0.0, 'D': 2.1}, {'P' : 0.4, 'I': 0.0, 'D': 2.1}, {'P' : 0.4, 'I': 0.0, 'D': 2.1}],
			'max_temperature_limit': [30.0, 30.0, 30.0, 30.0],
			'min_temperature_limit': [-40.0, -40.0, -40.0, -40.0],
			'overload_fault_threshold_seconds': 10.0,
			#	Calibration:
			'tc_calibration_time_step': 0.2,
			'tc_calibration_logging_rate': 5,
			'auto_range_max_throttle': 5.0,
			'auto_range_min_cooling_rate_per_min': -1.0,
			'calibration_fit_polynomial_order': 2,
			'auto_calibration_temperature_steps': 3,
			'prt_calibration_coeffs_filepath' : ['./calibrations/*/channel_' + str(i) + '/prt_calibration_coeffs.csv' for i in range(4)],
			'tc_calibration_temp_data_filepath': ['./calibrations/*/channel_' + str(i) + '/tc_calibration_log_data_TEMP.csv' for i in range(4)],
			'tc_calibration_final_data_filepath': ['./calibrations/*/channel_' + str(i) + '/tc_calibration_log_data.csv' for i in range(4)],
			'tc_calibration_coeffs_filepath' : ['./calibrations/*/channel_' + str(i) + '/tc_calibration_coeffs.csv' for i in range(4)],
			'calibrated_temp_limits_filepath': ['./calibrations/*/channel_' + str(i) + '/calibrated_temp_limits.csv' for i in range(4)],
			#	Ramping
			'path_to_ramp_profile' : ["./ramp_profile.csv" for i in range(4)],
			'ramp_repeats' : [1, 1, 1, 1]
		}
		
		self.start_up_config = StartUpConfig.StartUpConfig(self.device_parameter_defaults)
		self.comms_baud = self.device_parameter_defaults['comms_baud_rate']
		self.comms_unique_id = self.start_up_config.device_unique_id.get()
		self.comms_port = self.start_up_config.device_port.get()
		self.num_channels = self.start_up_config.device_number_of_channels.get()
		self.video_device_id = [int(self.start_up_config.camera_id.get()), 0, 0, 0]
		self.video_enabled = [not bool(self.start_up_config.video_disabled_flag.get()), 0, 0, 0]
		self.timing_flag = self.device_parameter_defaults['timing_info_flag']
		self.time_step = self.device_parameter_defaults['time_step']
		self.plotting_enabled = self.device_parameter_defaults['enable_plotting_flag']
		self.drive_mode = self.device_parameter_defaults['drive_mode']
		self.action = self.start_up_config.action.get()
		
		if self.num_channels < 1:
			self.num_channels = 1
		elif self.num_channels > 4:
			self.num_channels = 4
		
		self.device_parameter_defaults['prt_calibration_coeffs_filepath'] = [self.device_parameter_defaults['prt_calibration_coeffs_filepath'][i].split('*')[0] + str(self.comms_unique_id) + self.device_parameter_defaults['prt_calibration_coeffs_filepath'][i].split('*')[1] for i in range(self.num_channels)]
		self.device_parameter_defaults['tc_calibration_temp_data_filepath'] = [self.device_parameter_defaults['tc_calibration_temp_data_filepath'][i].split('*')[0] + str(self.comms_unique_id) + self.device_parameter_defaults['tc_calibration_temp_data_filepath'][i].split('*')[1] for i in range(self.num_channels)]
		self.device_parameter_defaults['tc_calibration_final_data_filepath'] = [self.device_parameter_defaults['tc_calibration_final_data_filepath'][i].split('*')[0] + str(self.comms_unique_id) + self.device_parameter_defaults['tc_calibration_final_data_filepath'][i].split('*')[1] for i in range(self.num_channels)]
		self.device_parameter_defaults['tc_calibration_coeffs_filepath'] = [self.device_parameter_defaults['tc_calibration_coeffs_filepath'][i].split('*')[0] + str(self.comms_unique_id) + self.device_parameter_defaults['tc_calibration_coeffs_filepath'][i].split('*')[1] for i in range(self.num_channels)]
		self.device_parameter_defaults['calibrated_temp_limits_filepath'] = [self.device_parameter_defaults['calibrated_temp_limits_filepath'][i].split('*')[0] + str(self.comms_unique_id) + self.device_parameter_defaults['calibrated_temp_limits_filepath'][i].split('*')[1] for i in range(self.num_channels)]
		self.simulation_flag = (self.comms_port == 'none')
		
		if self.action == 'start':
			# Create a root tkinter window, and then hide it.
			self.root_tk = tk.Tk()
			self.root_tk.withdraw()
			
			# Warn user if calibration files absent.
			self.CheckCalibrationFiles(self.num_channels, self.comms_unique_id)
			
			# Data queues.
			self.mq_front_to_back = [Queue() for i in range(self.num_channels)]
			self.mq_back_to_front = [Queue() for i in range(self.num_channels)]
			self.mq_back_to_vlogger = [Queue() if self.video_enabled[i] == True else None for i in range(self.num_channels)]
			
			# Image queue(s).
			self.mq_vlogger_to_front = [Queue() if self.video_enabled[i] == True else None for i in range(self.num_channels)]
			# Video fault multiprocessing event.
			self.event_vlogger_fault = [Event() if self.video_enabled[i] == True else None for i in range(self.num_channels)]
			# Calibration logging trigger multiprocessing event.
			self.event_back_to_front = [{'calibration_zeroed_flag': Event(), 'gradient_detect_flag': Event(), 'ramp_running_flag': Event()} for i in range(self.num_channels)]
			
			# Timestamp queue.
			self.InitialiseTimingMonitors(self.timing_flag)
			
			# Spawn required video handler processes.
			self.process_vlogger = [Process(target = VideoHandler.VideoHandler, args = (i, self.simulation_flag, self.device_parameter_defaults, self.mq_back_to_vlogger[i], self.mq_vlogger_to_front[i], self.mq_timestamp[i], self.event_vlogger_fault[i], self.timing_flag, self.video_device_id[i])) for i in range(self.num_channels) if self.video_enabled[i] == True]
			for current_vlogger in self.process_vlogger:
				current_vlogger.start()
			
			# Create instance(s) of the front end object and create a Tkinter variable that it can set when it/they close(s).
			# These will be polled to determine when all front end windows are closed so we can end the root window mainloop().
			self.close_action = [tk.StringVar(self.root_tk) for i in range(self.num_channels)]
			self.front_ends = [FrontEnd.FrontEnd(self, self.root_tk, self.device_parameter_defaults, self.num_channels, i, self.comms_unique_id, self.close_action[i], self.mq_front_to_back[i], self.mq_back_to_front[i], self.mq_vlogger_to_front[i], self.event_back_to_front[i], self.timing_flag, self.timing_monitor[i], self.timing_monitor_kill[i], self.mq_timestamp[i], self.time_step, self.video_enabled[i], self.plotting_enabled[i]) for i in range(self.num_channels)]
			
			# Setup a process to run the back end. Pass Queue()s, Event()s etc to allow inter-process communication.
			self.process_back_end = Process(target = BackEnd.BackEnd, args = (self.device_parameter_defaults, self.num_channels, self.mq_front_to_back, self.mq_back_to_front, self.mq_back_to_vlogger, self.mq_timestamp, self.event_vlogger_fault, self.event_back_to_front, self.video_enabled, self.comms_unique_id, self.time_step, self.timing_flag, self.drive_mode))
			self.process_back_end.start()
			
			# First call of the function that polls to check if all front end windows have been closed, then spin the root
			# Tkinter window mainloop() to generate and begin servicing the GUI elements.
			self.ClosePoll()
			self.root_tk.mainloop()	# That's it, we're live folks!
			
			# When the user exits and the tkinter mainloop quits, having sent the appropriate shutdown command
			# to the back end, we wait for it and the video handler to complete, rejoin them, and finish.
			for current_vlogger in self.process_vlogger:
				current_vlogger.join()
			self.process_back_end.join()
			print('Application closed.')
		else:
			print('Application closed.')
		
	def ClosePoll(self):
		closed_count = 0
		for i in range(self.num_channels):
			if self.close_action[i].get() == 'closed':
				closed_count += 1
		if closed_count == self.num_channels:	
			print('Frontends closed.')
			self.root_tk.quit()
		else:
			self.root_tk.after(500, self.ClosePoll)
	
	def InitialiseTimingMonitors(self, timing_flag):
		if timing_flag == True:
			self.mq_timestamp = [Queue() for i in range(self.num_channels)]
			self.timing_monitor_kill = [Event() for i in range(self.num_channels)]
			for i in range(self.num_channels):
				self.timing_monitor_kill[i].set()
			self.timing_monitor = [Process(target = Utilities.TimingMonitor, args = (i, self.mq_timestamp[i], self.timing_monitor_kill[i])) for i in range(self.num_channels)]
			for i in range(self.num_channels):
				self.timing_monitor[i].start()
				print('Timing monitor ' + str(i) + ' started...')
		else:
			self.mq_timestamp = ['' for i in range(self.num_channels)]
			self.timing_monitor_kill = ['' for i in range(self.num_channels)]
			self.timing_monitor = ['' for i in range(self.num_channels)]
	
	def CheckCalibrationFiles(self, num_channels, unique_id):
		for current_channel in range(num_channels):
			calibration_path = self.device_parameter_defaults['prt_calibration_coeffs_filepath'][current_channel]
			file_exists = os.path.isfile(calibration_path)
			if file_exists == False:
				# Check if calibration file directory for this channel exists, and if not, create it.
				dir_path = '/'.join(self.device_parameter_defaults['prt_calibration_coeffs_filepath'][current_channel].split('/')[0:-1])
				print(dir_path)
				if os.path.isdir(dir_path) == False:
					os.makedirs(dir_path)
					new_prt_calibration_file = open(self.device_parameter_defaults['prt_calibration_coeffs_filepath'][current_channel], 'a')
					new_prt_calibration_file.write('1, 0')
					new_prt_calibration_file.close()
				tkinter.messagebox.showwarning("Warning", "No temperature calibration profile found for Channel " + str(current_channel) + " internal PRT.", icon = 'warning')
				
			calibration_path = self.device_parameter_defaults['tc_calibration_coeffs_filepath'][current_channel]
			file_exists = os.path.isfile(calibration_path)
			if file_exists == False:
				tkinter.messagebox.showwarning("Warning", "No temperature calibration profile found for Channel " + str(current_channel) + " internal thermocouple.\nPlease run auto-calibration before taking measurements.", icon = 'warning')
	
	def CloseAllFrontEndModalDialogs(self):
		for front_end in self.front_ends:
			if front_end.modal_dialog_open == True:
				front_end.modal_dialog_open = False
				front_end.modal_interface_window.destroy()
			if front_end.drop_assay_widget.modal_dialog_open == True:
				front_end.drop_assay_widget.modal_dialog_open = False
				front_end.drop_assay_widget.modal_interface_window.destroy()
				
	
if __name__ == '__main__':
	cooler_control = CoolerControl()
