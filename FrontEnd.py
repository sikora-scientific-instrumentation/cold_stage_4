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
import tkinter as tk
from tkinter import NORMAL, DISABLED
import tkinter.constants, tkinter.filedialog, tkinter.messagebox, tkinter.ttk
import matplotlib
matplotlib.use('TKAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import time
import sys
import cv2
import serial.tools.list_ports
from PIL import Image, ImageTk
from os import makedirs, path

import CalibrationWidget
import DropAssayWidget

class FrontEnd():
	def __init__ (self, parent, root_tk, device_parameter_defaults, num_channels, channel_id, comms_unique_id, close_action, mq_front_to_back, mq_back_to_front, mq_vlogger_to_front, event_back_to_front, timing_flag, timing_monitor, timing_monitor_kill, mq_timestamp, time_step, video_enabled, plotting_enabled):
		self.parent = parent
		self.device_parameter_defaults = device_parameter_defaults
		self.num_channels = num_channels
		self.channel_id = channel_id
		self.comms_unique_id = comms_unique_id
		self.close_action = close_action
		
		self.mq_front_to_back = mq_front_to_back
		self.mq_back_to_front = mq_back_to_front
		self.mq_vlogger_to_front = mq_vlogger_to_front
		self.event_back_to_front = event_back_to_front
		
		self.timing_flag = timing_flag
		self.timing_monitor = timing_monitor
		self.timing_monitor_kill = timing_monitor_kill
		self.mq_timestamp = mq_timestamp
		
		self.sub_tick = 0
		self.stop_signal = False
		self.ready_to_stop = False
		self.logging_flag = False
		self.flow_fault_warning_open = False
		self.video_fault_warning_open = False
		self.comms_fault_warning_open = False
		self.generic_warning_window_open = False
		self.modal_dialog_open = False
		self.video_fault_timestamp = 0.0
		self.flow_fault_timestamp = 0.0
		self.comms_fault_timestamp = 0.0
		
		self.video_enabled = video_enabled
		self.running_flag = False
		self.time_step = time_step
		self.datum_time = time.time()
		
		self.times = []
		self.temperatures = []
		self.setpoint_times = []
		self.setpoint_temperatures = []
		
		self.plotting_enabled = self.device_parameter_defaults['enable_plotting_flag'][self.channel_id]
		self.update_rate = self.device_parameter_defaults['plot_update_rate'][self.channel_id]
		self.logging_rate = self.device_parameter_defaults['logging_rate'][self.channel_id]
		self.plotting_max_span = self.device_parameter_defaults['plot_span'][self.channel_id]
		self.temperature_limits = {'max': self.device_parameter_defaults['max_temperature_limit'][self.channel_id], 'min': self.device_parameter_defaults['min_temperature_limit'][self.channel_id]}
		
		# Create the control panel and video feed tk windows. 
		self.root_tk = root_tk
		self.GenerateTKWindow()
		if self.video_enabled:
			self.GenerateTKVideoWindow()
		self.calibration_widget = CalibrationWidget.CalibrationWidget(self, self.channel_id, self.comms_unique_id, self.root_tk, self.device_parameter_defaults, self.mq_front_to_back, self.event_back_to_front)
		self.drop_assay_widget = DropAssayWidget.DropAssayWidget(self, self.channel_id, self.root_tk, self.device_parameter_defaults, self.mq_front_to_back, self.event_back_to_front)
		
		# Run UpdatePoll to begin checking for messages from the backend process.
		self.UpdatePoll()
	
	# Checks the message queue from the backend and responds appropriately.
	def UpdatePoll(self):
		# Don't re-prime the update-poll if we have started the shutdown process.
		if self.stop_signal == True:
			pass
		else:
			# Function calls itself to run in 500 milliseconds time.
			self.update_poll_id = self.top.after(250, self.UpdatePoll)
		
		most_recent_message = []
		while most_recent_message != [0, ]:
			try:
				most_recent_message = self.mq_back_to_front.get(False, None)
			except:
				most_recent_message = [0, ]
			if most_recent_message[0] == 1:
				if most_recent_message[1] == 'Current_temperature':
					self.sub_tick += 1
					current_temp = round(most_recent_message[3], 3)
					self.times.append((most_recent_message[2] - self.datum_time))
					self.temperatures.append(current_temp)
					self.label_current_temp_reading.configure(text = current_temp)
					if (current_temp > 0.0):
						self.label_current_temp_reading.configure(foreground = "red")
					else:
						self.label_current_temp_reading.configure(foreground = "blue")
				elif most_recent_message[1] == 'Current_PRT_temperature':
					current_PRT_temp = round(most_recent_message[3], 3)
					self.label_current_PRT_temp_reading.configure(text = current_PRT_temp)
					if (current_PRT_temp > 0.0):
						self.label_current_PRT_temp_reading.configure(foreground = "red")
					else:
						self.label_current_PRT_temp_reading.configure(foreground = "blue")
				elif most_recent_message[1] == 'Current_setpoint':
					if most_recent_message[3] != 'NA':
						self.setpoint_times.append((most_recent_message[2] - self.datum_time))
						self.setpoint_temperatures.append(most_recent_message[3])
				elif most_recent_message[1] == 'Current_flowrate':
					current_flowrate = round(float(most_recent_message[3]), 3)
					self.label_current_flowrate_reading.configure(text = str(current_flowrate))
					if current_flowrate < 5.0:
						self.label_current_flowrate_reading.configure(foreground = "red")
					else:
						self.label_current_flowrate_reading.configure(foreground = "black")
			elif most_recent_message[0] == 2:
				if most_recent_message[1] == 'New_datum_time':
					self.datum_time = float(most_recent_message[2])
					self.times = []
					self.temperatures = []
					self.setpoint_times = []
					self.setpoint_temperatures = []
					if self.plotting_enabled == True:
						self.InitialisePlot()
						self.UpdatePlot()
						self.sub_tick = 0
				elif most_recent_message[1] == 'Set_mode_label':
					if most_recent_message[2] == 'Idle':
						self.setpoint_times = []
						self.setpoint_temperatures = []
					elif most_recent_message[2].startswith('End of profile'):
						self.EnableFrontEndRampControls()
						if ((self.logging_flag == True) and (self.checkButton_log_end_on_profile_end_value.get() == True)):
							# Reset the logging controls to their default state.
							self.checkButton_log_video_split.configure(state = NORMAL)
							self.button_log_off.configure(state = DISABLED)
							self.button_log_on.configure(state = DISABLED)
							self.button_log_select.configure(state = NORMAL)
							self.logging_flag = False
					self.label_mode.configure(text = most_recent_message[2])
				elif most_recent_message[1] == 'Set_temp_limits':
					self.temperature_limits['max'] = float(most_recent_message[2])
					self.temperature_limits['min'] = float(most_recent_message[3])
					self.label_current_max_limit_reading.configure(text = most_recent_message[2])
					self.label_current_min_limit_reading.configure(text = most_recent_message[3])
				elif most_recent_message[1] == 'Set_logging_label':
					self.label_logging_reading.configure(text = most_recent_message[2])
				elif most_recent_message[1] == 'All_shutdown_confirm':
					self.ShutDown()
				elif most_recent_message[1] == 'Comms_fault':
					if self.comms_fault_warning_open == False:
						self.OpenCommsFaultAlert()
				elif most_recent_message[1] == 'Comms_success':
					if self.comms_fault_warning_open == True:
						self.CloseCommsFaultAlert()
						print('Transient comms fault lasting ' + str(round(time.time() - (self.comms_fault_timestamp), 1)) + ' seconds occurred.')
				elif most_recent_message[1] == 'Flow_fault':
					if self.flow_fault_warning_open == False:
						self.OpenFlowFaultAlert()
				elif most_recent_message[1] == 'Flow_success':
					if self.flow_fault_warning_open == True:
						self.CloseFlowFaultAlert()
						print('Transient coolant flow fault lasting ' + str(round((time.time() - self.flow_fault_timestamp), 1)) + ' seconds occurred.')
				elif most_recent_message[1] == 'Video_fault':
					if self.video_fault_warning_open == False:
						print('Video source disconnected!')
						self.OpenVideoFaultAlert()
				elif most_recent_message[1] == 'Video_success':
					if self.video_fault_warning_open == True:
						print('Video source successfully connected.')
						print('Transient video device fault lasting ' + str(round(time.time() - (self.video_fault_timestamp), 1)) + ' seconds occurred.')
						self.CloseVideoFaultAlert()
		
		if ((self.plotting_enabled == True) and (self.sub_tick >= self.update_rate)):
			self.UpdatePlot()
			self.sub_tick = 0
		if self.video_enabled == True:
			last_frame_on_queue = [0,]
			while self.mq_vlogger_to_front.qsize() > 0:
				try:
					last_frame_on_queue = self.mq_vlogger_to_front.get(False, None)
				except:
					pass
			if last_frame_on_queue != [0,]:
				# Get dimensions of existing image.
				existing_image_width = self.imageTK.width()
				existing_image_height = self.imageTK.height()
				self.imageTK = ImageTk.PhotoImage(last_frame_on_queue)
				# Get new image dimensions.
				image_width = self.imageTK.width()
				image_height = self.imageTK.height()
				# Resize video window if needed.
				if ((existing_image_height != image_height) or (existing_image_width != image_width)):
					self.video_window.geometry(str(image_width) + 'x' + str(image_height))
				self.video_panel.configure(image = self.imageTK)
	
	def OpenCommsFaultAlert(self):
		for front_end in self.parent.front_ends:
			front_end.comms_fault_warning_open = True
		self.parent.CloseAllFrontEndModalDialogs()
		self.comms_fault_timestamp = time.time()
		self.GenerateTKCommsFaultWindow()
		for front_end in self.parent.front_ends:
			# Take window stacking priority over main frontend window.
			front_end.BindParentClicks(front_end.top, self.comms_fault_window)
			if front_end.video_enabled == True:
				# Take window stacking priority over frontend video window.
				front_end.BindParentClicks(front_end.video_window, self.comms_fault_window)
			if front_end.flow_fault_warning_open == True:
				# Take window stacking priority over flow fault warning window.
				front_end.BindParentClicks(front_end.flow_fault_window, self.comms_fault_window)
			if front_end.video_fault_warning_open == True:
				# Take window stacking priority over video fault warning window.
				front_end.BindParentClicks(front_end.video_fault_window, self.comms_fault_window)
			if front_end.generic_warning_window_open == True:
				# Take window stacking priority over generic warning window.
				front_end.BindParentClicks(front_end.generic_warning_window, self.comms_fault_window)
			if front_end.drop_assay_widget.window_open_flag == True:
				# Take window stacking priority over drop-assay widget window.
				front_end.BindParentClicks(front_end.drop_assay_widget.widget_window, front_end.comms_fault_window)
			if front_end.calibration_widget.window_open_flag == True:
				# Take window stacking priority over auto-calibration widget window.
				front_end.BindParentClicks(front_end.calibration_widget.widget_window, front_end.comms_fault_window)
		
	def CloseCommsFaultAlert(self):
		# When we close the single comms fault alert window, we loop through all front ends and restore window precedence.
		for front_end in self.parent.front_ends:
			if self.parent.close_action[front_end.channel_id].get() != 'closed':
				front_end.comms_fault_warning_open = False
				if front_end.flow_fault_warning_open == True:
					# If flow fault warning window open, this takes precedence, first main frontend window.
					front_end.BindParentClicks(front_end.top, front_end.flow_fault_window)
					if front_end.video_enabled == True:
						# Take window stacking priority over frontend video window.
						front_end.BindParentClicks(front_end.video_window, front_end.flow_fault_window)
					if front_end.video_fault_warning_open == True:
						# Take window stacking priority over video fault warning window.
						front_end.BindParentClicks(front_end.video_fault_window, front_end.flow_fault_window)
					if front_end.generic_warning_window_open == True:
						# Take window stacking priority over generic warning window.
						front_end.BindParentClicks(front_end.generic_warning_window, front_end.flow_fault_window)
				elif ((front_end.flow_fault_warning_open == False) and (front_end.video_fault_warning_open == True)):
					# Else, if video fault warning window open, this takes precedence, first main frontend window.
					front_end.BindParentClicks(front_end.top, front_end.video_fault_window)
					if front_end.video_enabled == True:
						# Take window stacking priority over frontend video window.
						front_end.BindParentClicks(front_end.video_window, front_end.video_fault_window)
					if front_end.generic_warning_window_open == True:
						# Take window stacking priority over generic warning window.
						front_end.BindParentClicks(front_end.generic_warning_window, front_end.video_fault_window)
					if front_end.drop_assay_widget.window_open_flag == True:
						# Take window stacking priority over drop-assay widget window.
						front_end.BindParentClicks(front_end.drop_assay_widget.widget_window, front_end.video_fault_window)
					if front_end.calibration_widget.window_open_flag == True:
						# Take window stacking priority over auto-calibration widget window.
						front_end.BindParentClicks(front_end.calibration_widget.widget_window, front_end.video_fault_window)
				elif ((front_end.flow_fault_warning_open == False) and (front_end.video_fault_warning_open == False) and (front_end.generic_warning_window_open == True)):
					# Else, if generic warning window open, this takes precedence, first main frontend window.
					front_end.BindParentClicks(front_end.top, front_end.generic_warning_window)
					if front_end.video_enabled == True:
						# Take window stacking priority over frontend video window.
						front_end.BindParentClicks(front_end.video_window, front_end.generic_warning_window)
					if front_end.drop_assay_widget.window_open_flag == True:
						# Take window stacking priority over drop-assay widget window.
						front_end.BindParentClicks(front_end.drop_assay_widget.widget_window, front_end.generic_warning_window)
					if front_end.calibration_widget.window_open_flag == True:
						# Take window stacking priority over auto-calibration widget window.
						front_end.BindParentClicks(front_end.calibration_widget.widget_window, front_end.generic_warning_window)
				else:
					# Else, if the frontend widget windows are open, give them priority.
					if front_end.drop_assay_widget.window_open_flag == True:
						front_end.BindParentClicks(front_end.top, front_end.drop_assay_widget.widget_window)
						if front_end.video_enabled == True:
							front_end.BindParentClicks(self.video_window, front_end.drop_assay_widget.widget_window)
					elif front_end.calibration_widget.window_open_flag == True:
						front_end.BindParentClicks(front_end.top, front_end.calibration_widget.widget_window)
						if front_end.video_enabled == True:
							front_end.BindParentClicks(self.video_window, front_end.calibration_widget.widget_window)
					else:
						# If not, we clear the bindings.
						front_end.UnbindParentClicks(front_end.top)
						if front_end.video_enabled == True:
							front_end.UnbindParentClicks(front_end.video_window)
		self.comms_fault_window.destroy()
		self.comms_fault_warning_open = False
	
	def OpenFlowFaultAlert(self):
		# Because a frontend flow fault condition is triggered by a drop in the incoming flow rate values, it can't
		# occur if we are in a comms fault condition, so we don't have to check for this when setting window precendence.
		self.flow_fault_warning_open = True
		if self.drop_assay_widget.window_open_flag == True:
			self.drop_assay_widget.Abort()
		if self.calibration_widget.window_open_flag == True:
			self.calibration_widget.Cancel()
		self.parent.CloseAllFrontEndModalDialogs()
		if self.running_flag == True:
			self.Off()
		self.flow_fault_timestamp = time.time()
		self.GenerateTKFlowFaultWindow()
		self.BindParentClicks(self.top, self.flow_fault_window)
		if self.video_enabled == True:
			self.BindParentClicks(self.video_window, self.flow_fault_window)
		if self.generic_warning_window_open == True:
			self.BindParentClicks(self.generic_warning_window, self.flow_fault_window)
		if self.video_fault_warning_open == True:
			self.BindParentClicks(self.video_fault_window, self.flow_fault_window)
		
	def CloseFlowFaultAlert(self):
		if self.video_fault_warning_open == True:
			self.BindParentClicks(self.top, self.video_fault_window)
			if self.video_enabled == True:
				self.BindParentClicks(self.video_window, self.video_fault_window)
		else:
			if self.generic_warning_window_open == True:
				self.BindParentClicks(self.top, self.generic_warning_window)
				if self.video_enabled == True:
					self.BindParentClicks(self.video_window, self.generic_warning_window)
			else:
				self.UnbindParentClicks(self.top)
				if self.video_enabled == True:
					self.UnbindParentClicks(self.video_window)
		self.flow_fault_window.destroy()
		self.flow_fault_warning_open = False
		
	def OpenVideoFaultAlert(self):
		self.video_fault_warning_open = True
		self.video_fault_timestamp = time.time()
		self.parent.CloseAllFrontEndModalDialogs()
		self.GenerateTKVideoFaultWindow()
		# If there is already a comms fault warning open, this keeps priority.
		if self.comms_fault_warning_open == True:
			self.BindParentClicks(self.video_fault_window, self.comms_fault_window)
		else:
			# Else, if there is already a flow fault warning open, this keeps priority.
			if self.flow_fault_warning_open == True:
				self.BindParentClicks(self.video_fault_window, self.flow_fault_window)
			else:
				# Else, the video fault window takes priority over the main frontend window...
				self.BindParentClicks(self.top, self.video_fault_window)
				# ...the frontend widget windows if open...
				if self.drop_assay_widget.window_open_flag == True:
					self.BindParentClicks(self.drop_assay_widget.widget_window, self.video_fault_window)
				if self.calibration_widget.window_open_flag == True:
					self.BindParentClicks(self.calibration_widget.widget_window, self.video_fault_window)
				# ...the main video window if open...
				if self.video_enabled == True:
					self.BindParentClicks(self.video_window, self.video_fault_window)
				# ...and the generic warning window if open.
				if self.generic_warning_window_open == True:
					self.BindParentClicks(self.generic_warning_window, self.video_fault_window)
	
	def CloseVideoFaultAlert(self):
		# When we close video fault warning window we only make any changes to window priority if there are no comms or fault warnings open.
		if ((self.comms_fault_warning_open == False) and (self.flow_fault_warning_open == False)):
			# If the generic warning window open, this takes priority over the main frontend window...
			if self.generic_warning_window_open == True:
				self.BindParentClicks(self.top, self.generic_warning_window)
				# ...the main video window if open...
				if self.video_enabled == True:
					self.BindParentClicks(self.video_window, self.generic_warning_window)
				# ...and the frontend widget windows if open.
				if self.drop_assay_widget.window_open_flag == True:
					self.BindParentClicks(self.drop_assay_widget.widget_window, self.generic_warning_window)
				if self.calibration_widget.window_open_flag == True:
					self.BindParentClicks(self.calibration_widget.widget_window, self.generic_warning_window)
			else:
				# Else, if the frontend widget windows are open they take priority...
				if self.drop_assay_widget.window_open_flag == True:
					self.BindParentClicks(self.top, self.drop_assay_widget.widget_window)
					if self.video_enabled == True:
						self.BindParentClicks(self.video_window, self.drop_assay_widget.widget_window)
				elif self.calibration_widget.window_open_flag == True:
					self.BindParentClicks(self.top, self.calibration_widget.widget_window)
					if self.video_enabled == True:
						self.BindParentClicks(self.video_window, self.calibration_widget.widget_window)
				else:
					# If not, we clear the bindings.
					self.UnbindParentClicks(self.top)
					if self.video_enabled == True:
						self.UnbindParentClicks(self.video_window)
		self.video_fault_window.destroy()
		self.video_fault_warning_open = False
		
	def CloseGenericWarningWindow(self):
		if self.generic_warning_window_open == True:
			# Only any changes to window priority if no other warning windows open.
			if ((self.flow_fault_warning_open == False) and (self.comms_fault_warning_open == False) and (self.video_fault_warning_open == False)):
				# Frontend widget windows take priority if open.
				if self.drop_assay_widget.window_open_flag == True:
					self.BindParentClicks(self.top, self.drop_assay_widget.widget_window)
					if self.video_enabled == True:
						self.BindParentClicks(self.video_window, self.drop_assay_widget.widget_window)
				elif self.calibration_widget.window_open_flag == True:
					self.BindParentClicks(self.top, self.calibration_widget.widget_window)
					if self.video_enabled == True:
						self.BindParentClicks(self.video_window, self.calibration_widget.widget_window)
				else:
					# If not, we clear the bindings.
					self.UnbindParentClicks(self.top)
					if self.video_enabled == True:
						self.UnbindParentClicks(self.video_window)
			self.generic_warning_window.destroy()
			self.generic_warning_window_open = False
	
	def WidgetWindowToFrontCallBack(self, event):
		self.target_child_window.lift()
	
	def BindParentClicks(self, bound_parent, target_child):
		bound_parent.bind("<Button-1>", self.WidgetWindowToFrontCallBack)
		bound_parent.bind("<Button-2>", self.WidgetWindowToFrontCallBack)
		bound_parent.bind("<Button-3>", self.WidgetWindowToFrontCallBack)
		bound_parent.bind("<Key>", self.WidgetWindowToFrontCallBack)
		self.target_child_window = target_child
	
	def UnbindParentClicks(self, bound_parent):
		bound_parent.unbind("<Button-1>")
		bound_parent.unbind("<Button-2>")
		bound_parent.unbind("<Button-3>")
		bound_parent.unbind("<Key>")
	
	def InitialisePlot(self):
		# Called when initially creating or clearing and re-creating figure axes.
		# Delete existing figure axes (if any) and then create anew. Set axes title and label, then 
		# create two 'empty' subplots, for stage temperature (red) and setpoint (blue).
		try:
			self.fig.delaxes(self.subplot)
			self.subplot = self.fig.add_subplot(111)
		except:
			self.subplot = self.fig.add_subplot(111)
		self.subplot.set_title('Channel ' + str(self.channel_id))
		self.subplot.set_xlabel('Time (seconds)')
		self.subplot.set_ylabel('Temperature (°C)')
		self.temp_plot, = self.subplot.plot([], [], lw = 2, color = 'red')
		self.setpoint_plot, = self.subplot.plot([], [], lw = 2, color = 'blue')
	
	def UpdatePlot(self):
		if len(self.times) > self.plotting_max_span:
			range_start = -1 * self.plotting_max_span
		else:
			range_start = 0
		self.temp_plot.set_data(self.times[range_start:], self.temperatures[range_start:])
		if self.setpoint_times:
			self.setpoint_plot.set_data(self.setpoint_times[range_start:], self.setpoint_temperatures[range_start:])
		# Scale the plot axes. Pad the y-axis by +/- 5% of the data y-range.
		if len(self.temperatures[range_start:]) > 1:
			max_val = 0.0
			min_val = 0.0
			#~print(self.temperatures[range_start:])
			#~print(self.setpoint_temperatures[range_start:])
			if len(self.setpoint_times)>0:
				min_val = min(min(self.temperatures[range_start:]), min(self.setpoint_temperatures[range_start:]))
				max_val = max(max(self.temperatures[range_start:]), max(self.setpoint_temperatures[range_start:]))
			else:
				min_val = min(self.temperatures[range_start:])
				max_val = max(self.temperatures[range_start:])
			val_range = max_val - min_val
			if val_range == 0:
				val_range = min_val
			min_val = min_val - (val_range * 0.05)
			max_val = max_val + (val_range * 0.05)
			self.subplot.set_ylim(min_val, max_val)
			self.subplot.set_xlim(min(self.times[range_start:]), max(self.times[range_start:]))
		elif len(self.temperatures[range_start:]) == 1:
			min_val = min(self.temperatures[range_start:]) * 0.95
			max_val = max(self.temperatures[range_start:]) * 1.05
			self.subplot.set_ylim(min_val, max_val)
			self.subplot.set_xlim(min(self.times[range_start:]), max(self.times[range_start:]))
		else:
			self.subplot.set_ylim(0.0, 1.0)
			self.subplot.set_xlim(0.0, 1.0)
		self.fig.canvas.draw()
	
	def SetThrottle(self):
		if self.ClicksAreActive() == True:
			try:
				new_throttle_percentage = float(self.entry_throttle.get())
				if (new_throttle_percentage >= -100.0) and (new_throttle_percentage <= 100.0):
					failed = 0
					self.throttle_percentage = new_throttle_percentage
				else:
					failed = 1
			except:
				failed = 1
			if failed == 0:
				self.mq_front_to_back.put(('Throttle', self.throttle_percentage))
				self.running_flag = True
				self.EnableFrontEndRampControls()
			else:
				self.GenerateGenericWarningWindow("Warning", "Throttle setting must be numerical where -100.0 >= throttle <= 100.0.")
	
	def Setpoint(self):
		if self.ClicksAreActive() == True:
			try:
				new_setpoint = float(self.entry_setpoint.get()) 
				if new_setpoint < self.temperature_limits['min']:
					new_setpoint = self.temperature_limits['min']
				elif new_setpoint > self.temperature_limits['max']:
					new_setpoint = self.temperature_limits['max']
				self.setpoint = new_setpoint
				self.running_flag = True
				self.mq_front_to_back.put(('SetPoint', self.setpoint))
				self.EnableFrontEndRampControls()
			except:
				self.GenerateGenericWarningWindow("Warning", "Setpoint must be numerical between " + str(self.temperature_limits['min']) + " and " + str(self.temperature_limits['max']) + " °C.")
	
	def SetTimestep(self):
		if self.ClicksAreActive() == True:
			try:
				new_time_step = float(self.entry_timestep.get())
				if new_time_step > 0.0:
					self.time_step = new_time_step
					self.mq_front_to_back.put(('SetTimeStep', self.time_step))
					failed = 0
				else:
					failed = 1
			except:
				failed = 1
			if failed == 1:
				self.GenerateGenericWarningWindow("Warning", "Time step must be numerical and positive.")
	
	def SetUpdateRate(self):
		if self.ClicksAreActive() == True:
			try:
				new_update_rate = int(self.entry_update_rate.get())
				if new_update_rate > 0:
					self.update_rate = new_update_rate
			except:
				self.GenerateGenericWarningWindow("Warning", "Update rate must be a positive integer.")
	
	def SetLoggingRate(self):
		if self.ClicksAreActive() == True:
			try:
				new_logging_rate = int(self.entry_log_rate.get())
				if new_logging_rate > 0:
					self.mq_front_to_back.put(('LoggingRate', new_logging_rate))
			except:
				self.GenerateGenericWarningWindow("Warning", "Logging rate must be a positive integer.")
	
	def SetPlotSpan(self):
		if self.ClicksAreActive() == True:
			try:
				new_plotting_span = int(self.entry_plot_span.get())
				if new_plotting_span > 0:
					self.plotting_max_span = new_plotting_span
			except:
				self.GenerateGenericWarningWindow("Warning", "Plotting span must be a positive integer.")
	
	def PIDConfig(self):
		if self.ClicksAreActive() == True:
			try:
				new_P_value = float(self.entry_P.get())
				new_I_value = float(self.entry_I.get())
				new_D_value = float(self.entry_D.get())
				self.mq_front_to_back.put(('PIDConfig', new_P_value, new_I_value, new_D_value))
			except:
				self.GenerateGenericWarningWindow("Warning", "Coefficients must be numerical.")
	
	def Ramp(self):
		if self.ClicksAreActive() == True:
			new_ramp_path = self.entry_ramp_path.get()
			new_ramp_repeats = int(self.entry_ramp_repeats.get())
			new_ramp_log_end_on_profile_end = self.checkButton_log_end_on_profile_end_value.get()
			new_ramp_log_start_on_profile_start = self.checkButton_log_start_on_profile_start_value.get()
			if ((new_ramp_log_start_on_profile_start == True) and (self.entry_log_file.get() == '')):
				self.GenerateGenericWarningWindow("Warning", "Cannot start logging as no log location selected.")
			else:		
				self.running_flag = True
				self.mq_front_to_back.put(('Ramp', new_ramp_repeats, new_ramp_log_end_on_profile_end, new_ramp_path, None))
				self.DisableFrontEndRampControls()
				if new_ramp_log_start_on_profile_start == True:
					self.StartLogging()
					# Set the logging controls to their 'logging' state.
					self.checkButton_log_video_split.configure(state = DISABLED)
					self.button_log_off.configure(state = NORMAL)
					self.button_log_on.configure(state = DISABLED)
					self.button_log_select.configure(state = DISABLED)
	
	def EnableFrontEndRampControls(self):
		# Restore ramp management controls to their default state.
		self.entry_ramp_path.configure(state = NORMAL)
		self.entry_ramp_repeats.configure(state = NORMAL)
		self.checkButton_log_end_on_profile_end.configure(state = NORMAL)
		self.checkButton_log_start_on_profile_start.configure(state = NORMAL)
		self.button_ramp_select.configure(state = NORMAL)
		self.button_ramp.configure(state = NORMAL)
	
	def DisableFrontEndRampControls(self):
		# Grey out ramp management controls while ramp is running.
		self.entry_ramp_path.configure(state = DISABLED)
		self.entry_ramp_repeats.configure(state = DISABLED)
		self.checkButton_log_end_on_profile_end.configure(state = DISABLED)
		self.checkButton_log_start_on_profile_start.configure(state = DISABLED)
		self.button_ramp_select.configure(state = DISABLED)
		self.button_ramp.configure(state = DISABLED)
	
	def SelectLogLocation(self):
		if self.ClicksAreActive() == True:
			# Create a tkinter save-as dialog box to allow the user to stipulate the location and name of the log file.
			self.modal_interface_window = tk.Toplevel(self.top)
			self.modal_interface_window.withdraw()
			self.modal_dialog_open = True
			try:
				file_path = tkinter.filedialog.asksaveasfilename(initialdir = "./", title = "Select log file location", filetypes = (("all files", "*.*"),), confirmoverwrite = True, parent = self.modal_interface_window)
			except:
				file_path = None
			if self.modal_dialog_open == True:
				self.modal_interface_window.destroy()
				self.modal_dialog_open = False
			if file_path is not None:
				# If neither, clear the existing contents of the log location entry field and replace with the full path returned by the dialog box.
				# To keep the entry field 'read only', we need to enable it, change the contents, then disable it again.
				self.entry_log_file.configure(state = NORMAL)
				self.entry_log_file.delete(0, 'end')
				self.entry_log_file.insert(0, file_path)
				self.entry_log_file.configure(state = DISABLED)
				# Once a log location has been stipulated, enable the start logging button.
				self.button_log_on.configure(state = NORMAL)
			else:
				print("--- KILLED ---")
	
	def StartLogging(self):
		if self.ClicksAreActive() == True:
			# Get the log file path from the log location entry field.
			self.log_file_path = self.entry_log_file.get()
			# Instruct the back end process to begin logging.
			self.mq_front_to_back.put(('StartLogging', self.log_file_path, False, False))
			# Deactivate the video log spolit checkbox, activate the stop logging button, deactivate the start logging button
			# and deactivate the set log location button.
			self.DisableFrontEndLoggingControls()
			self.logging_flag = True
	
	def DisableFrontEndLoggingControls(self):
		if self.video_enabled == True:
			self.checkButton_log_video_split.configure(state = DISABLED)
		self.button_log_off.configure(state = NORMAL)
		self.button_log_on.configure(state = DISABLED)
		self.button_log_select.configure(state = DISABLED)
		
	def EnableFrontEndLoggingControls(self):
		# Activate the video log split checkbox, deactivate start logging button, deactivate stop logging button
		# and activate the set log location button.
		if self.video_enabled == True:
			self.checkButton_log_video_split.configure(state = NORMAL)
		self.button_log_off.configure(state = DISABLED)
		self.button_log_on.configure(state = DISABLED)
		self.button_log_select.configure(state = NORMAL)
	
	def StopLogging(self):
		if self.ClicksAreActive() == True:
			# Send message to back end process to stop logging.
			self.mq_front_to_back.put(('StopLogging',))
			# Clear log path entry field.
			self.entry_log_file.configure(state = NORMAL)
			self.entry_log_file.delete(0, 'end')
			self.entry_log_file.configure(state = DISABLED)
			self.EnableFrontEndLoggingControls()
			self.logging_flag = False
	
	def SelectRamp(self):
		if self.ClicksAreActive() == True:
			self.modal_interface_window = tk.Toplevel(self.top)
			self.modal_interface_window.withdraw()
			self.modal_dialog_open = True
			try:
				file_path = tkinter.filedialog.askopenfilename(initialdir = "./",title = "Select file",filetypes = (("csv files","*.csv"),("all files","*.*")), parent = self.modal_interface_window)
			except:
				file_path = None
			if self.modal_dialog_open == True:
				self.modal_interface_window.destroy()
				self.modal_dialog_open = False
			# If the user does not click cancel...
			if file_path is not None:
				self.entry_ramp_path.delete(0, 'end')
				self.entry_ramp_path.insert(0, file_path)
	
	def ClearPlot(self):
		if self.ClicksAreActive() == True:
			self.mq_front_to_back.put(('NewDatumTime',))
	
	def Off(self):
		if self.ClicksAreActive() == True:
			self.running_flag = False
			self.setpoint_times = []
			self.setpoint_temperatures = []
			self.mq_front_to_back.put(('Off',))
			self.EnableFrontEndRampControls()
	
	def GenerateTKWindow(self):
		# Create the top-level frame (window)
		self.top = tk.Toplevel(self.root_tk)
		self.top.title("Control panel " + str(self.channel_id))
		# Hijack the 'widget is being closed' protocol. When the user clicks on the corner 'X' to close the window,
		# rather than hard closing and breaking everything, we've substituted our own shutdown handler.
		self.top.protocol("WM_DELETE_WINDOW", self.ClickShutDown)
		self.top.resizable(False, False)
		
		# Top-level frame is split into left (controls) and right (plotting) master frames - If plotting is enabled.
		self.left_master_frame = tk.Frame(self.top)
		self.left_master_frame.pack(side = "left", expand = "true", fill = tk.BOTH)
		if self.plotting_enabled == True:
			self.right_master_frame = tk.Frame(self.top)
			self.right_master_frame.pack(side = "left", expand = "true", fill = tk.BOTH)
		
		# Left master frame:
		# Comprises status frame...
		self.status_frame = tkinter.ttk.Frame(self.left_master_frame, borderwidth = 1, relief = "flat")
		self.status_frame.pack(side="top", expand="true", fill = tk.BOTH)
		
		# ...Master tabs.
		self.top_level_notebook = tkinter.ttk.Notebook(self.left_master_frame)
		self.automatic_controls_tab = tkinter.ttk.Frame(self.top_level_notebook)
		self.manual_controls_tab = tkinter.ttk.Frame(self.top_level_notebook)
		self.top_level_notebook.add(self.automatic_controls_tab, text = "Automatic")
		self.top_level_notebook.add(self.manual_controls_tab, text = "Manual")
		self.top_level_notebook.pack(side = "top", expand = "true", fill = tk.BOTH)
		
		# ...'Automatic controls' tabbled (Notebook) frames...
		self.automatic_controls_frame = tkinter.ttk.Frame(self.automatic_controls_tab, borderwidth = 1, relief = "flat")
		self.automatic_controls_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_auto_calibrate = tkinter.ttk.Button(self.automatic_controls_frame, text="Auto calibrate", command=self.AutoCalibrate)
		self.button_auto_calibrate.pack(side = "top", pady = 5, expand = "false", fill = tk.X)
		if self.video_enabled == True:
			self.button_drop_assay = tkinter.ttk.Button(self.automatic_controls_frame, text="Drop assay", command=self.DropAssay)
			self.button_drop_assay.pack(side = "top", pady = 5, expand = "false", fill = tk.X)
		
		# ...'Manual controls' tabbed (Notebook) frames...
		self.N = tkinter.ttk.Notebook(self.manual_controls_tab)
		self.f1 = tkinter.ttk.Frame(self.N)
		self.f2 = tkinter.ttk.Frame(self.N)
		self.f3 = tkinter.ttk.Frame(self.N)
		self.f4 = tkinter.ttk.Frame(self.N)
		self.f5 = tkinter.ttk.Frame(self.N)
		self.f6 = tkinter.ttk.Frame(self.N)
		self.f7 = tkinter.ttk.Frame(self.N)
		self.N.add(self.f1, text = "Throttle")
		self.N.add(self.f2, text = "Setpoint")
		self.N.add(self.f3, text = "Ramp") 
		self.N.add(self.f4, text = "Logging")
		self.N.add(self.f5, text = "Control")
		if self.plotting_enabled == True:
			self.N.add(self.f6, text = "Plotting")
		if self.video_enabled == True:
			self.N.add(self.f7, text = "Video")
		self.N.pack(side = "top", expand = "true", fill = tk.BOTH)
		
		# ...and off/quit buttons frame...
		self.buttons_frame = tkinter.ttk.Frame(self.left_master_frame, borderwidth = 1, relief = "flat")
		self.buttons_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		
		# Status frame:
		# Create the status frame controls
		self.temperature_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.temperature_frame.pack(side="top", expand="true", fill = tk.X)
		self.temperature_PRT_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.temperature_PRT_frame.pack(side="top", expand="true", fill = tk.X)
		self.flowrate_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.flowrate_frame.pack(side="top", expand="true", fill = tk.X)
		self.mode_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.mode_frame.pack(side="top", expand="true", fill = tk.X)
		self.logging_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.logging_frame.pack(side="top", expand="true", fill = tk.X)
		self.limits_frame = tkinter.ttk.Frame(self.status_frame, borderwidth = 1, relief = "sunken")
		self.limits_frame.pack(side="top", expand="true", fill = tk.X)
		self.limits_frame_label = tkinter.ttk.Frame(self.limits_frame, borderwidth = 1, relief = "groove")
		self.limits_frame_label.pack(side="left", expand="true", fill = tk.X)
		self.limits_frame_max = tkinter.ttk.Frame(self.limits_frame, borderwidth = 1, relief = "groove")
		self.limits_frame_max.pack(side="left", expand="true", fill = tk.X)
		self.limits_frame_min = tkinter.ttk.Frame(self.limits_frame, borderwidth = 1, relief = "groove")
		self.limits_frame_min.pack(side="right", expand="true", fill = tk.X)
		
		self.label_mode = tkinter.ttk.Label(self.mode_frame, text="Idle", font = ("Arial", 12))
		self.label_mode.pack(side="top", expand="true", fill = tk.X)
		
		self.label_logging_title = tkinter.ttk.Label(self.logging_frame, text="Logging", font = ("Arial", 12), justify = "left")
		self.label_logging_title.pack(side="left", expand="false")
		self.label_logging_reading = tkinter.ttk.Label(self.logging_frame, text="OFF", font = ("Arial", 14, 'bold'), justify = "right")
		self.label_logging_reading.pack(side="right", expand="false")
		
		self.label_current_temp_title = tkinter.ttk.Label(self.temperature_frame, text="Temp (°C)", font = ("Arial", 12), justify = "center")
		self.label_current_temp_title.pack(side="top", expand="true")
		self.label_current_temp_reading = tkinter.ttk.Label(self.temperature_frame, text="", font = ("Arial", 20, 'bold'), justify = "center")
		self.label_current_temp_reading.pack(side="top", expand="true")
		self.label_current_PRT_temp_title = tkinter.ttk.Label(self.temperature_PRT_frame, text="PRT Temp (°C)", font = ("Arial", 12), justify = "left")
		self.label_current_PRT_temp_title.pack(side="left", expand="false")
		self.label_current_PRT_temp_reading = tkinter.ttk.Label(self.temperature_PRT_frame, text="", font = ("Arial", 12), justify = "right")
		self.label_current_PRT_temp_reading.pack(side="right", expand="false")
		self.label_current_flowrate_title = tkinter.ttk.Label(self.flowrate_frame, text = "Flow rate (l/min)", font = ("Arial", 12), justify = "left")
		self.label_current_flowrate_title.pack(side = "left", expand = "false")
		self.label_current_flowrate_reading = tkinter.ttk.Label(self.flowrate_frame, text = "", font = ("Arial", 12), justify = "right")
		self.label_current_flowrate_reading.pack(side = "right", expand = "false")
		
		self.label_limits_title = tkinter.ttk.Label(self.limits_frame_label, text = "Temp limits (°C)", font = ("Arial", 12), justify = "center")
		self.label_limits_title.pack(side = "left", expand = "true")
		self.label_current_max_limit_title = tkinter.ttk.Label(self.limits_frame_max, text = "Max", font = ("Arial", 12), justify = "center")
		self.label_current_max_limit_title.pack(side = "left", expand = "true")
		self.label_current_max_limit_reading = tkinter.ttk.Label(self.limits_frame_max, text = str(self.temperature_limits['max']), font = ("Arial", 12), justify = "center")
		self.label_current_max_limit_reading.pack(side = "right", expand = "true")
		self.label_current_min_limit_title = tkinter.ttk.Label(self.limits_frame_min, text = "Min", font = ("Arial", 12), justify = "center")
		self.label_current_min_limit_title.pack(side = "left", expand = "true")
		self.label_current_min_limit_reading = tkinter.ttk.Label(self.limits_frame_min, text = str(self.temperature_limits['min']), font = ("Arial", 12), justify = "center")
		self.label_current_min_limit_reading.pack(side = "right", expand = "true")
		
		# Notebook frame:
		# tab f1 contains raw throttle controls
		self.throttle_entry_frame = tkinter.ttk.Frame(self.f1, borderwidth = 1)
		self.throttle_entry_frame.pack(side="top", expand="true", fill = tk.BOTH)
		self.label_throttle = tkinter.ttk.Label(self.throttle_entry_frame, text="Throttle (%)")
		self.label_throttle.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_throttle = tkinter.ttk.Entry(self.throttle_entry_frame)
		self.entry_throttle.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.button_throttle = tkinter.ttk.Button(self.throttle_entry_frame, text="Set Throttle", command=self.SetThrottle)
		self.button_throttle.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		
		# tab f2 contains setpoint controls
		self.setpoint_entry_frame = tkinter.ttk.Frame(self.f2, borderwidth = 1)
		self.setpoint_entry_frame.pack(side="top", expand="true", fill = tk.BOTH)
		self.label_setpoint = tkinter.ttk.Label(self.setpoint_entry_frame, text="Target temperature")
		self.label_setpoint.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_setpoint = tkinter.ttk.Entry(self.setpoint_entry_frame)
		self.entry_setpoint.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.button_set = tkinter.ttk.Button(self.setpoint_entry_frame, text="Setpoint", command=self.Setpoint)
		self.button_set.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		
		# tab f3 contains ramp controls
		self.ramp_config_frame = tkinter.ttk.Frame(self.f3, borderwidth = 1)
		self.ramp_config_frame.pack(side="top", expand="true", fill = tk.BOTH)
		self.label_ramp_path = tkinter.ttk.Label(self.ramp_config_frame, text="Path to ramp profile csv file:")
		self.label_ramp_path.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_ramp_path = tkinter.ttk.Entry(self.ramp_config_frame)
		self.entry_ramp_path.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_ramp_path.insert(0, self.device_parameter_defaults['path_to_ramp_profile'][self.channel_id])
		self.button_ramp_select = tkinter.ttk.Button(self.ramp_config_frame, text="Select ramp", command=self.SelectRamp)
		self.button_ramp_select.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.label_ramp_repeats = tkinter.ttk.Label(self.ramp_config_frame, text="Repeat (n) times:")
		self.label_ramp_repeats.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_ramp_repeats = tkinter.ttk.Entry(self.ramp_config_frame)
		self.entry_ramp_repeats.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_ramp_repeats.insert(0, self.device_parameter_defaults['ramp_repeats'][self.channel_id])
		self.checkButton_log_start_on_profile_start_value = tk.BooleanVar(self.ramp_config_frame)
		self.checkButton_log_start_on_profile_start_value.set(self.device_parameter_defaults['start_logging_at_profile_start_flag'][self.channel_id])
		self.checkButton_log_start_on_profile_start = tk.Checkbutton(self.ramp_config_frame, text = "Start logging at ramp start?", variable = self.checkButton_log_start_on_profile_start_value, onvalue = True, offvalue = False)
		self.checkButton_log_start_on_profile_start.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.checkButton_log_end_on_profile_end_value = tk.BooleanVar(self.ramp_config_frame)
		self.checkButton_log_end_on_profile_end_value.set(self.device_parameter_defaults['stop_logging_at_profile_end_flag'][self.channel_id])
		self.checkButton_log_end_on_profile_end = tk.Checkbutton(self.ramp_config_frame, text = "Stop logging at ramp end?", variable = self.checkButton_log_end_on_profile_end_value, onvalue = True, offvalue = False)
		self.checkButton_log_end_on_profile_end.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.button_ramp = tkinter.ttk.Button(self.ramp_config_frame, text="Ramp", command=self.Ramp)
		self.button_ramp.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		
		# tab f4 contains logging configuration
		self.log_config_frame = tkinter.ttk.Frame(self.f4, borderwidth = 1)
		self.log_config_frame.pack(side="top", expand="false", fill = tk.BOTH)
		self.label_log_rate = tkinter.ttk.Label(self.log_config_frame, text="Log every [n] points:")
		self.label_log_rate.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_log_rate = tkinter.ttk.Entry(self.log_config_frame)
		self.entry_log_rate.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_log_rate.insert(0, self.logging_rate)
		self.button_log_rate = tkinter.ttk.Button(self.log_config_frame, text="Apply logging rate", command=self.SetLoggingRate)
		self.button_log_rate.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.label_log_file = tkinter.ttk.Label(self.log_config_frame, text="Log location:")
		self.label_log_file.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_log_file = tkinter.ttk.Entry(self.log_config_frame)
		self.entry_log_file.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.button_log_select = tkinter.ttk.Button(self.log_config_frame, text="Select log location", command=self.SelectLogLocation)
		self.button_log_select.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.entry_log_file.configure(state = DISABLED)
		self.button_log_on = tkinter.ttk.Button(self.log_config_frame, text="Start Logging", command=self.StartLogging)
		self.button_log_on.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.button_log_on.configure(state = DISABLED)
		self.button_log_off = tkinter.ttk.Button(self.log_config_frame, text="Stop Logging", command=self.StopLogging)
		self.button_log_off.pack(side = "top", expand = "false", fill = tk.X)
		self.button_log_off.configure(state = DISABLED)
		
		# tab f5 contains control settings.
		self.control_config_frame = tkinter.ttk.Frame(self.f5, borderwidth = 1)
		self.control_config_frame.pack(side="top", expand="true", fill = tk.BOTH)
		self.label_control_coefficients = tkinter.ttk.Label(self.control_config_frame, text="PID coefficients:")
		self.label_control_coefficients.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		
		self.P_coefficient_frame = tkinter.ttk.Frame(self.control_config_frame, borderwidth = 1)
		self.P_coefficient_frame.pack(side = "top", expand = "false", fill = tk.X)
		self.label_P = tkinter.ttk.Label(self.P_coefficient_frame, text="P coefficient:")
		self.label_P.pack(side="left", pady = (5, 0), expand="false")
		self.entry_P = tkinter.ttk.Entry(self.P_coefficient_frame)
		self.entry_P.pack(side="right", pady = (5, 0), expand="false")
		self.entry_P.insert(0, self.device_parameter_defaults['pid_coefficients'][self.channel_id]['P'])
		
		self.I_coefficient_frame = tkinter.ttk.Frame(self.control_config_frame, borderwidth = 1)
		self.I_coefficient_frame.pack(side = "top", expand = "false", fill = tk.X)
		self.label_I = tkinter.ttk.Label(self.I_coefficient_frame, text="I coefficient:")
		self.label_I.pack(side="left", pady = (5, 0), expand="false")
		self.entry_I = tkinter.ttk.Entry(self.I_coefficient_frame)
		self.entry_I.pack(side="right", pady = (5, 0), expand="false")
		self.entry_I.insert(0, self.device_parameter_defaults['pid_coefficients'][self.channel_id]['I'])
		
		self.D_coefficient_frame = tkinter.ttk.Frame(self.control_config_frame, borderwidth = 1)
		self.D_coefficient_frame.pack(side = "top", expand = "false", fill = tk.X)
		self.label_D = tkinter.ttk.Label(self.D_coefficient_frame, text="D coefficient:")
		self.label_D.pack(side="left", pady = (5, 0), expand="false")
		self.entry_D = tkinter.ttk.Entry(self.D_coefficient_frame)
		self.entry_D.pack(side="right", pady = (5, 0), expand="false")
		self.entry_D.insert(0, self.device_parameter_defaults['pid_coefficients'][self.channel_id]['D'])
		
		self.button_apply_control = tkinter.ttk.Button(self.control_config_frame, text="Apply new coefficients", command=self.PIDConfig)
		self.button_apply_control.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		self.label_timestep = tkinter.ttk.Label(self.control_config_frame, text="Time step (seconds):")
		self.label_timestep.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_timestep = tkinter.ttk.Entry(self.control_config_frame)
		self.entry_timestep.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
		self.entry_timestep.insert(0, self.time_step)
		self.button_apply_timestep = tkinter.ttk.Button(self.control_config_frame, text="Apply time step", command=self.SetTimestep)
		self.button_apply_timestep.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		
		# tab f6 contains plotting settings - if enabled.
		if self.plotting_enabled == True:
			self.plotting_config_frame = tkinter.ttk.Frame(self.f6, borderwidth = 1)
			self.plotting_config_frame.pack(side="top", expand="true", fill = tk.BOTH)
			self.label_update_rate = tkinter.ttk.Label(self.plotting_config_frame, text="Update plot every [n] points:")
			self.label_update_rate.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
			self.entry_update_rate = tkinter.ttk.Entry(self.plotting_config_frame)
			self.entry_update_rate.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
			self.entry_update_rate.insert(0, self.update_rate)
			self.button_apply_update_rate = tkinter.ttk.Button(self.plotting_config_frame, text="Apply update rate", command=self.SetUpdateRate)
			self.button_apply_update_rate.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
			self.label_plot_span = tkinter.ttk.Label(self.plotting_config_frame, text="Plot spans last [n] points:")
			self.label_plot_span.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
			self.entry_plot_span = tkinter.ttk.Entry(self.plotting_config_frame)
			self.entry_plot_span.pack(side="top", pady = (5, 0), expand="false", fill = tk.X)
			self.entry_plot_span.insert(0, self.plotting_max_span)
			self.button_apply_plot_span = tkinter.ttk.Button(self.plotting_config_frame, text="Apply plot span", command=self.SetPlotSpan)
			self.button_apply_plot_span.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
			
		# tab f7 contains video settings - if enabled.
		if self.video_enabled == True:
			self.video_config_frame = tkinter.ttk.Frame(self.f7, borderwidth = 1)
			self.video_config_frame.pack(side="top", expand="true", fill = tk.BOTH)
			self.label_device = tk.Label(self.video_config_frame, text="Available video resolutions:", font = ("Arial", 12))
			self.label_device.pack(side="top", expand="false", fill = tk.X)
			self.video_resolution = tk.StringVar(self.top)
			self.optionmenu_video_resolutions = tk.OptionMenu(*(self.video_config_frame, self.video_resolution) + tuple(self.device_parameter_defaults['webcam_available_dimensions'])) # OptionMenu is linked to self.device_name StringVar.
			self.optionmenu_video_resolutions.pack(side = "top", expand = "false", fill = tk.X)
			# Set default here...
			self.video_resolution.set(self.device_parameter_defaults['webcam_default_dimensions'][self.channel_id])
			self.previous_video_resolution = self.device_parameter_defaults['webcam_default_dimensions'][self.channel_id]
			self.video_resolution.trace_id = self.video_resolution.trace("w", self.ChangeVideoResolution)
			self.log_video_split_flag = tk.BooleanVar(self.video_config_frame)
			self.previous_log_video_split_flag = self.device_parameter_defaults['log_video_split_flag'][self.channel_id]
			self.log_video_split_flag.set(self.device_parameter_defaults['log_video_split_flag'][self.channel_id])
			self.log_video_split_flag.trace_id = self.log_video_split_flag.trace("w", self.ChangeLogVideoSplitFlag)
			self.checkButton_log_video_split = tk.Checkbutton(self.video_config_frame, text = "Log video split?", variable = self.log_video_split_flag, onvalue = True, offvalue = False)
			self.checkButton_log_video_split.pack(side = "top", pady = (5, 0), expand = "false", fill = tk.X)
		
		# On/off buttons frame:
		# Create the on/off controls.
		self.button_clearplot = tkinter.ttk.Button(self.buttons_frame, text="Clear Plot", command=self.ClearPlot)
		self.button_clearplot.pack(side = "top", expand = "false", fill = tk.X)
		self.button_off = tkinter.ttk.Button(self.buttons_frame, text="Off", command=self.Off)
		self.button_off.pack(side = "top", expand = "false", fill = tk.X)
		self.button_quit = tkinter.ttk.Button(self.buttons_frame, text="Quit", command=self.ClickShutDown)
		self.button_quit.pack(side = "top", expand = "false", fill = tk.X)
		
		# Right master frame:
		# Contains plotting frame - if enabled.
		if self.plotting_enabled == True:
			self.fig = Figure()
			self.plot_frame = tkinter.ttk.Frame(self.right_master_frame, borderwidth = 1)
			self.plot_frame.pack(side = "left", expand =  "true")
			self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
			self.canvas.draw()
			plot_widget = self.canvas.get_tk_widget()
			plot_widget.pack(side = "bottom", expand = "true")
			self.InitialisePlot()
	
	def GenerateTKVideoWindow(self):
		# Create a child window in which the webcam images will be drawn, then create a
		# placeholder image that will be used to start displaying images in the window.
		self.video_window = tk.Toplevel(self.root_tk)
		self.video_window.title("Video " + str(self.channel_id))
		# For the video window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.video_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.video_window.resizable(False, False)
		x_dim, y_dim = [int(i) for i in self.device_parameter_defaults['webcam_default_dimensions'][self.channel_id].split('x')]
		placeholder_array = np.zeros((y_dim, x_dim))
		placeholder_image = Image.fromarray(placeholder_array).convert("RGB")
		self.imageTK = ImageTk.PhotoImage(image = placeholder_image)
		self.video_panel = tk.Label(self.video_window)
		self.video_panel.configure(image=self.imageTK)
		self.video_panel.pack(side = "bottom", fill = "both", expand = "yes")	
	
	def GenerateTKCommsFaultWindow(self):
		self.comms_fault_window = tk.Toplevel(self.root_tk)
		self.comms_fault_window.title("Serial fault!")
		self.comms_fault_window.geometry("500x100")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.comms_fault_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.comms_fault_window.resizable(False, False)
		self.comms_fault_frame = tk.Frame(self.comms_fault_window, bd = 1, relief = tk.RIDGE)
		self.comms_fault_frame.pack(side = "top", expand = "false", fill = tk.BOTH)
		self.label_comms_fault = tkinter.ttk.Label(self.comms_fault_frame, text="Serial fault!\n\nPlease check connections while attempting to recover or click below to abandon and shut down.", font = ("Arial", 12), justify = "center")
		self.label_comms_fault.pack(side="top", expand="false", pady = (5, 0))
		self.button_comms_fault = tk.Button(self.comms_fault_frame, text="Shut down", font = ("Arial", 14), command=self.AllShutDown)
		self.button_comms_fault.pack(side = "top", expand = "true", pady = (5, 5))
		# Brint widget window to the top of all front ends.
		self.comms_fault_window.lift()
		
	def GenerateTKFlowFaultWindow(self):
		self.flow_fault_window = tk.Toplevel(self.root_tk)
		self.flow_fault_window.title("Coolant flow fault!")
		self.flow_fault_window.geometry("500x100")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.flow_fault_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.flow_fault_window.resizable(False, False)
		self.flow_fault_frame = tk.Frame(self.flow_fault_window, bd = 1, relief = tk.RIDGE)
		self.flow_fault_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.label_flow_fault = tkinter.ttk.Label(self.flow_fault_frame, text="Coolant flow rate < 1.0 l/min\n\nCheck coolant pump and connections or click below to abandon and shut down.", font = ("Arial", 12), justify = "center")
		self.label_flow_fault.pack(side="top", expand="false", pady = (5, 0))
		self.button_flow_fault = tk.Button(self.flow_fault_frame, text="Shut down", font = ("Arial", 14), command=self.FlowFaultShutDown)
		self.button_flow_fault.pack(side = "top", expand = "false", pady = (5, 5))
		# Brint widget window to the top.
		self.flow_fault_window.lift()
	
	def FlowFaultShutDown(self):
		if self.comms_fault_warning_open == False:
			self.ShutDown()
	
	def GenerateTKVideoFaultWindow(self):
		self.video_fault_window = tk.Toplevel(self.root_tk)
		self.video_fault_window.title("Video device fault!")
		self.video_fault_window.geometry("500x100")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.video_fault_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.video_fault_window.resizable(False, False)
		self.video_fault_frame = tk.Frame(self.video_fault_window, bd = 1, relief = tk.RIDGE)
		self.video_fault_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.label_video_fault = tkinter.ttk.Label(self.video_fault_frame, text="Video device fault!\n\nCheck connections or click below to abandon and shut down.", font = ("Arial", 12), justify = "center")
		self.label_video_fault.pack(side="top", expand="false", pady = (5, 0))
		self.button_video_fault = tk.Button(self.video_fault_frame, text="Shut down", font = ("Arial", 14), command=self.VideoFaultShutDown)
		self.button_video_fault.pack(side = "top", expand = "false", pady = (5, 5))
		# Brint widget window to the top.
		self.video_fault_window.lift()
	
	def VideoFaultShutDown(self):
		if ((self.comms_fault_warning_open == False) and (self.flow_fault_warning_open == False)):
			self.ShutDown()
		
	def GenerateGenericWarningWindow(self, title, message):
		self.generic_warning_window_open = True
		self.generic_warning_window = tk.Toplevel(self.top)
		self.generic_warning_window.title(title)
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.generic_warning_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.generic_warning_window.resizable(False, False)
		self.generic_warning_frame = tk.Frame(self.generic_warning_window, bd = 1, relief = tk.RIDGE)
		self.generic_warning_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.label_generic_warning = tkinter.ttk.Label(self.generic_warning_frame, text = message, font = ("Arial", 12), justify = "center")
		self.label_generic_warning.pack(side="top", expand="false", pady = (5, 0), padx = (15, 15))
		self.button_generic_warning = tk.Button(self.generic_warning_frame, text="OK", font = ("Arial", 14), command=self.ClickCloseGenericWarningWindow)
		self.button_generic_warning.pack(side = "top", expand = "false", pady = (5, 5))
		self.BindParentClicks(self.top, self.generic_warning_window)
		if self.video_enabled == True:
			self.BindParentClicks(self.video_window, self.generic_warning_window)
		# Brint widget window to the top.
		self.generic_warning_window.lift()
	
	def ClickCloseGenericWarningWindow(self):
		if ((self.video_fault_warning_open == False) and (self.flow_fault_warning_open == False) and (self.comms_fault_warning_open == False)) == True:
			self.CloseGenericWarningWindow()
	
	def PassFunc(self):
		pass
		
	def ClicksAreActive(self):
		return ((self.video_fault_warning_open == False) and (self.generic_warning_window_open == False) and (self.flow_fault_warning_open == False) and (self.comms_fault_warning_open == False) and (self.calibration_widget.window_open_flag == False) and (self.drop_assay_widget.window_open_flag == False))
	
	def ChangeVideoResolution(self, *args):
		if self.ClicksAreActive() == True:
			new_video_resolution = self.video_resolution.get()
			self.mq_front_to_back.put(('ChangeVideoRes', new_video_resolution))
			self.previous_video_resolution = new_video_resolution
		else:
			# Stop tk variable trace on self.video resolution (so we don't start an infinite recursive loop when we change the value in here...)
			self.video_resolution.trace_vdelete("w", self.video_resolution.trace_id)
			# See comment in function declaration for __UndoChangeLogVideoSplit for explanation for why we use after() here rather than changing
			# the value here directly...
			self.top.after(0, self.__UndoChangeVideoResolution)
			
	def __UndoChangeVideoResolution(self):
		self.video_resolution.set(self.previous_video_resolution)
		# Re-apply the variable trace.
		self.video_resolution.trace_id = self.video_resolution.trace("w", self.ChangeVideoResolution)
	
	def ChangeLogVideoSplitFlag(self, *args):
		if self.ClicksAreActive() == True:
			new_log_video_split_flag = self.log_video_split_flag.get()
			self.mq_front_to_back.put(('ChangeLogVideoSplitFlag', new_log_video_split_flag))
			self.previous_log_video_split_flag = new_log_video_split_flag
		else:
			# Stop tk variable trace on self.video resolution (so we don't start an infinite recursive loop when we change the value in here...)
			self.log_video_split_flag.trace_vdelete("w", self.log_video_split_flag.trace_id)
			# See comment in function declaration for __UndoChangeLogVideoSplit for explanation for why we use after() here rather than changing
			# the value here directly...
			self.top.after(0, self.__UndoChangeLogVideoSplitFlag)
	
	def __UndoChangeLogVideoSplitFlag(self):
		# Changing the value of a Tkinter var from within a write trace on the same var is problematic - this would be an infinite loop,
		# if write traces weren't automatically disabled for the duration (including the one that actually updates the widget). 
		# Try root.after(1, var.set, default_text) to delay the change until you're no longer inside the write trace.
		# From StackOverflow https://stackoverflow.com/q/56638253
		self.log_video_split_flag.set(self.previous_log_video_split_flag)
		# Re-apply the variable trace.
		self.log_video_split_flag.trace_id = self.log_video_split_flag.trace("w", self.ChangeLogVideoSplitFlag)
	
	def ClickShutDown(self):
		if self.ClicksAreActive() == True:
			self.ShutDown()
	
	def ShutDown(self):
		# Send a shutdown command to the back end. Then check the back to front queue until a shutdown-ready
		# confirmation message arrives from the back end, confirming that the logger has been allowed
		# to shutdown, before calling the front end mainloop quit().
		shutdown_now = False
		
		if ((self.comms_fault_warning_open == False) and (self.flow_fault_warning_open == False) and (self.video_fault_warning_open == False)):
			if self.running_flag == True:
				self.modal_interface_window = tk.Toplevel(self.top)
				self.modal_interface_window.withdraw()
				self.modal_dialog_open = True
				try:
					choice = tkinter.messagebox.askquestion("Shutdown", "The channel is running, are you sure you want to shut down?", icon = 'warning', parent = self.modal_interface_window)
				except:
					choice = 'no'
				if self.modal_dialog_open == True:
					self.modal_interface_window.destroy()
					self.modal_dialog_open = False
				if choice == 'yes':
					shutdown_now = True
				else:
					shutdown_now = False
			else:
				shutdown_now = True
		else:
			shutdown_now = True
		
		if shutdown_now == True:
			# Instruct front end to no-longer continue priming the update-poll.
			self.stop_signal = True
			# If update-poll pending, cancel it.
			if self.update_poll_id in self.top.tk.call("after", "info"):
				self.top.after_cancel(self.update_poll_id)
			
			# Close any warning windows or modal dialogs still open.
			if self.flow_fault_warning_open == True:
				self.CloseFlowFaultAlert()
			if self.video_fault_warning_open == True:
				self.CloseVideoFaultAlert()
			if self.generic_warning_window_open == True:
				self.CloseGenericWarningWindow()
			if self.modal_dialog_open == True:
				self.modal_interface_window.destroy()
				self.modal_dialog_open = False
			
			# Send shutdown command to back end.
			self.mq_front_to_back.put(('ShutDown',))
			# Flush queue from back end and block until we hit shutdown confirmation, which will be the last item.
			most_recent_message = ' '
			while most_recent_message != 'ShutDownConfirm':
				try:
					most_recent_message = self.mq_back_to_front.get(False, None)
				except:
					most_recent_message = ' '
			if self.video_enabled == True:
				self.video_window.destroy()
			# Shut down the timing monitor (if running).
			if self.timing_flag == True:
				self.ShutDownTimingMonitor()
			# Quit the tkinter window and drop back to the calling script.
			self.close_action.set('closed')
			self.top.destroy()
	
	def AllShutDown(self):
		self.CloseCommsFaultAlert()
		self.mq_front_to_back.put(('AllShutDown',))
	
	def ShutDownTimingMonitor(self):
		self.timing_monitor_kill.clear()
		self.timing_monitor.join()
		print('Timing monitor ' + str(self.channel_id) + ' stopped...')
	
	def AutoCalibrate(self):
		if self.ClicksAreActive() == True:
			self.calibration_widget.Run(self.time_step, self.logging_rate)
	
	def DropAssay(self):
		if self.ClicksAreActive() == True:
			self.drop_assay_widget.Run(self.time_step, self.logging_rate, self.log_video_split_flag.get())
	
	def AreFaultWarningsOpen(self):
		for front_end in self.parent.front_ends:
			if ((front_end.comms_fault_warning_open == True) or (front_end.video_fault_warning_open == True) or (front_end.flow_fault_warning_open == True) or (front_end.generic_warning_window_open == True)):
				return True
		return False
		
