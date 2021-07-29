"""
########################################################################
#                                                                      #
#                  Copyright 2021 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
########################################################################

	This file is part of Cold Stage 4.
	PRE RELEASE 3.1

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
from tkinter import NORMAL, DISABLED
import tkinter.constants, tkinter.ttk
from os import path

class DropAssayWidget():
	def __init__ (self, parent, channel_id, root_tk, device_parameter_defaults, mq_front_to_back, event_back_to_front):
		self.device_parameter_defaults = device_parameter_defaults
		self.parent = parent
		self.channel_id = channel_id
		self.mq_front_to_back = mq_front_to_back
		self.event_back_to_front = event_back_to_front
		self.root_tk = root_tk
		self.calibration_fit_polynomial_order = self.device_parameter_defaults['calibration_fit_polynomial_order']
		self.poll_id = ''
		self.assay_parameters = {'room_temp': 0.0, 'start_temp': 0.0, 'end_temp': 0.0, 'ramp_rate': 0.0, 'log_path': ''}
		self.aborted_flag = False
		self.modal_dialog_open = False
		self.window_open_flag = False
		
	def Run(self, time_step, logging_rate, video_log_split_flag):
		self.aborted_flag = False
		self.modal_dialog_open = False
		self.original_time_step = time_step
		self.original_logging_rate = logging_rate
		self.GenerateDropAssayWidget()
		self.window_open_flag = True
		# Modes 0 = adjusting to room temp
		self.mode = 0
		# Ensure the stage is 'off' to begin.
		self.mq_front_to_back.put(('Off',))
		# Store existing log_video_split_flag value and turn it off.
		self.existing_video_log_split_flag = video_log_split_flag
		self.mq_front_to_back.put(('ChangeLogVideoSplitFlag', False))
		# Store existing time-step and logging rate and then set the time-step to 0.2 seconds (5 Hz) and logging rate of every 5th point (1 Hz).
		self.existing_time_step = time_step
		self.existing_logging_rate = logging_rate
		self.mq_front_to_back.put(('SetTimeStep', 0.2))
		self.mq_front_to_back.put(('LoggingRate', 5))
		self.SetDisplay(0)
		self.PollEvent()
	
	def PollEvent(self):
		if self.aborted_flag == False:
			repeat_poll_flag = False
			if self.mode == 0:
				# Waiting for user to enter room temperature...
				repeat_poll_flag = True
			elif self.mode == 1:
				# Waiting for user to enter assay parameters...
				repeat_poll_flag = True
			elif self.mode == 2:
				# Waiting for user to select log file location...
				if self.parent.AreFaultWarningsOpen() == False:
					# ----------------------
					self.modal_interface_window = tk.Toplevel(self.widget_window)
					self.modal_interface_window.withdraw()
					self.modal_dialog_open = True
					try:
						log_path = tkinter.filedialog.asksaveasfilename(initialdir = "./", title = "Select channel " + str(self.channel_id) + " log file location", filetypes = (("all files", "*.*"),), confirmoverwrite = True, parent = self.modal_interface_window)
					except:
						log_path = None
					if self.modal_dialog_open == True:
						self.modal_dialog_open = False
						self.modal_interface_window.destroy()
					else:
						print(" --- KILLED --- ")
					print(log_path)
					# ----------------------
					if log_path is None:
						# Modal dialog was killed by something external!
						if self.aborted_flag == False:
							# Might have been closed by transient comms or video fault warning without closing drop assay widget...
							repeat_poll_flag = True
					elif log_path == ():
						# User clicked cancel.
						self.Abort()
					else:
						# Log path selected.
						self.assay_parameters['log_path'] = log_path
						self.SetDisplay(3)
						self.action_button_next.configure(text = "Start assay")
						self.action_button_next.configure(state = DISABLED)
						self.mode = 3
						repeat_poll_flag = True
				else:
					repeat_poll_flag = True
			elif self.mode == 3:
				# Waiting for event_back_to_front to be clear()ed by the backend when we hit room temp...
				if self.event_back_to_front['ramp_running_flag'].is_set() == False:
					self.action_button_next.configure(state = NORMAL)
					self.SetDisplay(4)
					self.mode = 4
				else:
					pass
				repeat_poll_flag = True
			elif self.mode == 4:
				repeat_poll_flag = True
			elif self.mode == 5:
				# Waiting for event_back_to_front to be clear()ed by the backend when we hit the end of the ramp...
				if self.event_back_to_front['ramp_running_flag'].is_set() == False:
					self.action_button_abort.configure(state = NORMAL)
					self.action_button_next.configure(text = "Next Assay")
					self.SetDisplay(6);
					self.mode = 6
				repeat_poll_flag = True
			elif self.mode == 6:
				repeat_poll_flag = True
			if repeat_poll_flag == True:
				self.poll_id = self.widget_window.after(250, self.PollEvent)
	
	def ClicksAreActive(self):
		return ((self.parent.comms_fault_warning_open == False) and (self.parent.flow_fault_warning_open == False) and (self.parent.video_fault_warning_open == False) and (self.parent.generic_warning_window_open == False))
	
	def ClickNext(self):
		if self.ClicksAreActive() == True:
			self.Next()
	
	def ClickAbort(self):
		if self.ClicksAreActive() == True:
			self.Abort()
	
	def Next(self):
		if self.mode == 0:
			room_temp = self.entry_room_temp.get()
			success, room_temp, error_message = self.ValidateRoomTemperature(room_temp)
			if success == True:	
				self.assay_parameters['room_temp'] = room_temp
				self.event_back_to_front['ramp_running_flag'].set()
				self.mq_front_to_back.put(('Ramp', 1, False, None, [['setpoint', self.assay_parameters['room_temp']]]))
				self.SetDisplay(1)
				self.mode = 1
			else:
				self.entry_room_temp.delete(0, 'end')
				self.entry_room_temp.insert(0, str(room_temp))
				self.parent.GenerateGenericWarningWindow("Parameter entry error", error_message)
		elif self.mode == 1:
			start_temp = self.entry_start_temp.get()
			end_temp = self.entry_end_temp.get()
			ramp_rate = self.entry_ramp_rate.get()
			# ------------------------ VALIDATE THE ASSAY PARAMETERS HERE --------------------------------------------------------
			success, start_temp, error_message = self.ValidateStartTemperature(self.assay_parameters['room_temp'], start_temp)
			if success == True:
				self.assay_parameters['start_temp'] = start_temp
				success, end_temp, error_message = self.ValidateEndTemperature(self.assay_parameters['start_temp'], end_temp)
				if success == True:
					self.assay_parameters['end_temp'] = end_temp
					success, ramp_rate, error_message = self.ValidateRampRate(ramp_rate)
					if success == True:
						# Everything internally works in deg/sec, so convert if necessary.
						if self.ramp_rate_units.get() == "°C/min":
							ramp_rate = ramp_rate / 60.0
						self.assay_parameters['ramp_rate'] = ramp_rate
						self.SetDisplay(2)
						self.mode = 2
					else:
						self.entry_ramp_rate.delete(0, 'end')
						self.entry_ramp_rate.insert(0, str(ramp_rate))
						self.parent.GenerateGenericWarningWindow("Parameter entry error - Start temp", error_message)
				else:
					self.entry_end_temp.delete(0, 'end')
					self.entry_end_temp.insert(0, str(end_temp))
					self.parent.GenerateGenericWarningWindow("Parameter entry error - End temp", error_message)
			else:
				self.entry_start_temp.delete(0, 'end')
				self.entry_start_temp.insert(0, str(start_temp))
				self.parent.GenerateGenericWarningWindow("Parameter entry error - Ramp rate", error_message)
			# --------------------------------------------------------------------------------------------------------------------
		elif self.mode == 2:
			print("Mode = 2")
		elif self.mode == 3:
			print("Mode = 3")
		elif self.mode == 4:
			self.action_button_next.configure(text = "Finish assay")
			self.action_button_abort.configure(state = DISABLED)
			self.event_back_to_front['ramp_running_flag'].set()
			self.mq_front_to_back.put(('Ramp', 1, True, None, [['ramp', self.assay_parameters['start_temp'], self.assay_parameters['end_temp'], self.assay_parameters['ramp_rate']]]))
			self.mq_front_to_back.put(('StartLogging', self.assay_parameters['log_path'], False, False))
			self.SetDisplay(5);
			self.mode = 5
		elif self.mode == 5:
			# Stop logging.
			self.mq_front_to_back.put(('StopLogging',))
			# Cancel the ramp if it's running by turning the stage 'off'.
			self.mq_front_to_back.put(('SetPoint', self.assay_parameters['room_temp']))
			self.event_back_to_front['ramp_running_flag'].clear()
			self.action_button_abort.configure(state = NORMAL)
			self.action_button_next.configure(text = "Next Assay")
			self.SetDisplay(6);
			self.mode = 6
		elif self.mode == 6:
			self.action_button_next.configure(text = "Next")
			self.SetDisplay(1)
			self.mode = 1
	
	def ValidateRoomTemperature(self, room_temp):
		error_message = ''
		try:
			room_temp = float(room_temp)
			success = True
		except:
			room_temp = room_temp
			success = False
			error_message = "Room temperature must be numerical."
		if success == True:
			if room_temp > self.parent.temperature_limits['max']:
				success = False
				room_temp = self.parent.temperature_limits['max']
				error_message = "Room temperature cannot be > " + str(self.parent.temperature_limits['max']) + " °C."
			elif room_temp < self.parent.temperature_limits['min']:
				success = False
				room_temp = self.parent.temperature_limits['min']
				error_message = "Room temperature cannot be < " + str(self.parent.temperature_limits['min']) + " °C."
		return success, room_temp, error_message
	
	def ValidateStartTemperature(self, room_temp, start_temp):
		error_message = ''
		try:
			start_temp = float(start_temp)
			success = True
		except:
			start_temp = start_temp
			success = False
			error_message = "Start temperature must be numerical."
		if success == True:
			if start_temp > room_temp:
				success = False
				start_temp = room_temp
				error_message = "Start temperature cannot be > Room temperature."
			elif start_temp < self.parent.temperature_limits['min']:
				success = False
				start_temp = self.parent.temperature_limits['min']
				error_message = "Start temperature cannot be < " + str(self.parent.temperature_limits['min']) + " °C."
		return success, start_temp, error_message
	
	def ValidateEndTemperature(self, start_temp, end_temp):
		error_message = ''
		try:
			end_temp = float(end_temp)
			success = True
		except:
			end_temp = end_temp
			success = False
			error_message = "End temperature must be numerical."
		if success == True:
			if end_temp > start_temp:
				success = False
				end_temp = start_temp
				error_message = "End temperature cannot be > Start temperature."
			elif end_temp < self.parent.temperature_limits['min']:
				success = False
				end_temp = self.parent.temperature_limits['min']
				error_message = "End temperature cannot be < " + str(self.parent.temperature_limits['min']) + " °C."
		return success, end_temp, error_message
	
	def ValidateRampRate(self, ramp_rate):
		error_message = ''
		try:
			ramp_rate = float(ramp_rate)
			success = True
		except:
			ramp_rate = ramp_rate
			success = False
			error_message = "Ramp rate must be numerical."
		if success == True:
			if ramp_rate > 0.0:
				success = False
				ramp_rate = ramp_rate * -1.0
				error_message = "Ramp rate must be negative."
		return success, ramp_rate, error_message
			
		
	def Abort(self):
		self.aborted_flag = True
		if self.poll_id in self.widget_window.tk.call("after", "info"):
			self.widget_window.after_cancel(self.poll_id)
		# Kill the modal save dialog if it is open.
		if self.modal_dialog_open == True:
			self.modal_interface_window.destroy()
			self.modal_interface_window = False
		# Stop the logger if it's running
		self.mq_front_to_back.put(('StopLogging',))
		# Cancel the ramp if it's running by turning the stage 'off'.
		self.mq_front_to_back.put(('Off',))
		self.mq_front_to_back.put(('ChangeLogVideoSplitFlag', self.existing_video_log_split_flag))
		self.mq_front_to_back.put(('SetTimeStep', self.existing_time_step))
		self.mq_front_to_back.put(('LoggingRate', self.existing_logging_rate))
		self.parent.UnbindParentClicks(self.parent.top)
		if self.parent.video_enabled == True:
			self.parent.UnbindParentClicks(self.parent.video_window)
		self.window_open_flag = False
		self.widget_window.destroy()
	
	def GenerateDropAssayWidget(self):
		self.widget_window = tk.Toplevel(self.root_tk)
		self.widget_window.title("Channel " + str(self.channel_id) + " Prompted Drop-Assay Wizard")
		#~self.widget_window.geometry("800x400")
		# For the widget window we'll just have it ignore any request to close the widget (with the exception of it's 
		# destroy()/quit() method, etc...).
		self.widget_window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.widget_window.resizable(False, False)
		
		self.widget_window_frame = tk.Frame(self.widget_window, width = 800, height = 250, bd = 1, relief = tk.RIDGE)
		self.widget_window_frame.pack(side = "top", expand = True, fill = tk.BOTH)
		self.widget_window_frame.grid_columnconfigure(0, minsize = 400)
		self.widget_window_frame.grid_columnconfigure(1, minsize = 400)
		self.widget_window_frame.grid_rowconfigure(0, minsize = 250)
		
		self.widget_window_left_frame = tk.Frame(self.widget_window_frame, bd = 1, relief = tk.RIDGE)
		self.widget_window_right_frame = tk.Frame(self.widget_window_frame, bd = 1, relief = tk.RIDGE)
		self.widget_window_left_frame.grid(row = 0, column = 0, sticky = "nsew")
		self.widget_window_right_frame.grid(row = 0, column = 1, sticky = "nsew")
		self.widget_window_left_frame.grid_rowconfigure(0, minsize = 250)
		self.widget_window_left_frame.grid_columnconfigure(0, minsize = 400)
		
		self.widget_window_wizard_frame = tk.Frame(self.widget_window_right_frame)
		self.widget_window_buttons_frame = tk.Frame(self.widget_window_right_frame)
		self.widget_window_wizard_frame.grid(row = 0, column = 0, sticky = "nsew")
		self.widget_window_buttons_frame.grid(row = 1, column = 0, sticky = "nsew")
		self.widget_window_right_frame.grid_rowconfigure(0, minsize = 230)
		self.widget_window_right_frame.grid_rowconfigure(1, minsize = 20)
		self.widget_window_right_frame.grid_columnconfigure(0, minsize = 400)
		
		stage_titles = ['1. Configure room temperature (°C)', '2. Configure assay start temperature (°C)', '3. Configure log file location', 
						'4. Stage not yet at room temperature\n...Please wait...', '5. Prepare droplets', '6. Ramping', '7. Done']
		self.labels = [tk.Label(self.widget_window_left_frame, text = i, foreground = "grey", font = ("Arial", 12)) for i in stage_titles]
		for i, label in enumerate(self.labels):
			label.pack(side = "top", expand = True, fill = tk.BOTH)
		self.labels[0].configure(foreground = "black", font = ("Arial", 12, "bold"))
		
		self.action_button_abort = tk.Button(self.widget_window_buttons_frame, text="Abort", font = ("Arial", 12), command=self.ClickAbort)
		self.action_button_next = tk.Button(self.widget_window_buttons_frame, text="Next", font = ("Arial", 12), command=self.ClickNext)
		self.action_button_abort.grid(row = 0, column = 0, sticky = "nsew")
		self.action_button_next.grid(row = 0, column = 1, sticky = "nsew")
		self.widget_window_buttons_frame.grid_columnconfigure(0, minsize = 200)
		self.widget_window_buttons_frame.grid_columnconfigure(1, minsize = 200)
		self.widget_window_buttons_frame.grid_rowconfigure(0, minsize = 20)
		
		self.wizard_frames = dict([[i, tk.Frame(self.widget_window_wizard_frame)] for i in range(7)])
		
		self.wizard_frames[0].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp = tk.Label(self.wizard_frames[0], text = "Room temperature (°C)", font = ("Arial", 11))
		self.entry_room_temp = tk.Entry(self.wizard_frames[0], width = 8, font = ("Arial", 11))
		self.entry_room_temp.insert(0, "20.0")
		self.label_room_temp.grid(row = 0, column = 0, sticky = "", pady = (10, 5), padx = (5, 5))
		self.entry_room_temp.grid(row = 0, column = 1, sticky = "", pady = (10, 5), padx = (5, 5))
		self.wizard_frames[0].grid_columnconfigure(0, minsize = 200)
		self.wizard_frames[0].grid_columnconfigure(1, minsize = 200)
		
		self.wizard_frames[1].grid(row = 0, column = 0, sticky = "nsew")
		self.label_start_temp = tk.Label(self.wizard_frames[1], text = "Start temperature (°C)", font = ("Arial", 11))
		self.entry_start_temp = tk.Entry(self.wizard_frames[1], width = 8, font = ("Arial", 11))
		self.label_start_temp.grid(row = 0, column = 0, sticky = "", pady = (10, 5), padx = (5, 5))
		self.entry_start_temp.grid(row = 0, column = 1, sticky = "", pady = (10, 5), padx = (5, 5))
		self.label_end_temp = tk.Label(self.wizard_frames[1], text = "End temperature (°C)", font = ("Arial", 11))
		self.entry_end_temp = tk.Entry(self.wizard_frames[1], width = 8, font = ("Arial", 11))
		self.label_end_temp.grid(row = 1, column = 0, sticky = "", pady = (5, 5), padx = (5, 5))
		self.entry_end_temp.grid(row = 1, column = 1, sticky = "", pady = (5, 5), padx = (5, 5))
		self.label_ramp_rate = tk.Label(self.wizard_frames[1], text = "Ramp rate", font = ("Arial", 11))
		self.entry_ramp_rate = tk.Entry(self.wizard_frames[1], width = 8, font = ("Arial", 11))
		self.ramp_rate_units = tk.StringVar(self.widget_window)
		units = ["°C/sec", "°C/min"]
		self.units = units[1]
		self.optionmenu_ramp_rate_units = tk.OptionMenu(*(self.wizard_frames[1], self.ramp_rate_units) + tuple(units))
		# Set default here...
		self.ramp_rate_units.set(units[1])
		self.ramp_rate_units_trace_id = self.ramp_rate_units.trace("w", self.AdjustUnits)
		self.label_ramp_rate.grid(row = 2, column = 0, sticky = "", pady = (5, 5), padx = (5, 5))
		self.entry_ramp_rate.grid(row = 2, column = 1, sticky = "", pady = (5, 5), padx = (5, 5))
		self.optionmenu_ramp_rate_units.grid(row = 2, column = 2, sticky = "", pady = (5, 5), padx = (5, 5))
		self.entry_start_temp.insert(0, "0.0")
		self.entry_end_temp.insert(0, str(self.parent.temperature_limits['min']))
		self.entry_ramp_rate.insert(0, "-1.0")
		self.wizard_frames[1].grid_columnconfigure(0, minsize = 100)
		self.wizard_frames[1].grid_columnconfigure(1, minsize = 50)
		self.wizard_frames[1].grid_columnconfigure(2, minsize = 50)
		
		self.wizard_frames[2].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp2 = tk.Label(self.wizard_frames[2], text = "Please select temperature and video log location.", font = ("Arial", 11), anchor = tk.E, justify = "left")
		self.label_room_temp2.grid(row = 0, column = 0, sticky = "ew", pady = (5, 5), padx = (5, 5))
		
		self.wizard_frames[3].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp3 = tk.Label(self.wizard_frames[3], text = "Stage not yet at room temperature...Please wait...", font = ("Arial", 11), anchor = tk.E, justify = "left")
		self.label_room_temp3.grid(row = 0, column = 0, sticky = "ew", pady = (5, 5), padx = (5, 5))
		
		self.wizard_frames[4].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp4 = tk.Label(self.wizard_frames[4], text = "Stage at room temperature - Please prepare your slide\n/filter, pippette your droplets and then click Start assay. ", font = ("Arial", 11), anchor = tk.E, justify = "left")
		self.label_room_temp4.grid(row = 0, column = 0, sticky = "ew", pady = (5, 5), padx = (5, 5))
		
		self.wizard_frames[5].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp5 = tk.Label(self.wizard_frames[5], text = "Assay running - Click Finish to stop when all droplets are\nfrozen.", font = ("Arial", 11), anchor = tk.E, justify = "left")
		self.label_room_temp5.grid(row = 0, column = 0, sticky = "ew", pady = (5, 5), padx = (5, 5))
		
		self.wizard_frames[6].grid(row = 0, column = 0, sticky = "nsew")
		self.label_room_temp6 = tk.Label(self.wizard_frames[6], text = "Assay completed - Click Next assay to run another drop\nassay or Abort to finish.", font = ("Arial", 11), anchor = tk.E, justify = "left")
		self.label_room_temp6.grid(row = 0, column = 0, sticky = "ew", pady = (5, 5), padx = (5, 5))
		
		self.widget_window.lift()
		self.parent.BindParentClicks(self.parent.top, self.widget_window)
		if self.parent.video_enabled == True:
			self.parent.BindParentClicks(self.parent.video_window, self.widget_window)
	
	def PassFunc(self):
		pass
	
	def AdjustUnits(self, *args):
		if self.ClicksAreActive() == True:
			new_units = self.ramp_rate_units.get()
			old_rate_value = float(self.entry_ramp_rate.get())
			new_rate_value = 0.0
			if ((new_units == "°C/sec") and (self.units == "°C/min")):
				new_rate_value = old_rate_value / 60.0
			elif ((new_units == "°C/min") and (self.units == "°C/sec")):
				new_rate_value = old_rate_value * 60.0
			else:
				new_rate_value = old_rate_value
			self.units = new_units
			self.entry_ramp_rate.delete(0, "end")
			self.entry_ramp_rate.insert(0, str(new_rate_value))
			self.previous_units = self.units
		else:
			self.ramp_rate_units.trace_vdelete("w", self.ramp_rate_units_trace_id)
			self.widget_window.after(0, self.__UndoAdjustUnits)
	
	def __UndoAdjustUnits(self):
		self.ramp_rate_units.set(self.previous_units)
		self.ramp_rate_units_trace_id = self.ramp_rate_units.trace("w", self.AdjustUnits)
	
	def SetDisplay(self, index):
		for label in self.labels:
			label.configure(foreground = "grey", font = ("Arial", 12))
		self.labels[index].configure(foreground = "black", font = ("Arial", 12, "bold"))
		self.wizard_frames[index].lift()

#~class AssayParamsDialog(tk.simpledialog.Dialog):
	#~def __init__(self, parent, room_temp, **kwargs):
		#~self.room_temp = room_temp
		#~tk.simpledialog.Dialog.__init__(self, parent, **kwargs)
		
	#~def body(self, master):
		#~#tk.Label(master, text = "Please enter assay ramp start temperature and ramp rate
		#~tk.Label(master, text = "Start temp (deg C):").grid(row = 0, sticky = tk.E)
		#~tk.Label(master, text = "End temp (deg C):").grid(row = 1, sticky = tk.E)
		#~tk.Label(master, text = "Ramp rate :").grid(row = 2, sticky = tk.E)
		#~self.entry_start_temp = tk.Entry(master)
		#~self.entry_end_temp = tk.Entry(master)
		#~self.entry_ramp_rate = tk.Entry(master)
		#~self.entry_start_temp.grid(row = 0, column = 1)
		#~self.entry_end_temp.grid(row = 1, column = 1)
		#~self.entry_ramp_rate.grid(row = 2, column = 1)
		#~self.entry_start_temp.insert(0, "0.0")
		#~self.entry_end_temp.insert(0, "-40.0")
		#~self.entry_ramp_rate.insert(0, "1.0")
		#~self.ramp_rate_units = tk.StringVar(master)
		#~units = ["deg/sec", "deg/min"]
		#~self.optionmenu_units = tk.OptionMenu(*(master, self.ramp_rate_units) + tuple(units)) # OptionMenu is linked to self.device_name StringVar.
		#~self.optionmenu_units.grid(row = 2, column = 2)
		#~# Set default here...
		#~self.ramp_rate_units.set(units[1])
		#~self.ramp_rate_units.trace("w", self.adjustUnits)
		#~return self.entry_start_temp # initial focus
	
	#~def adjustUnits(self, *args):
		#~new_units = self.ramp_rate_units.get()
		#~old_rate_value = float(self.entry_ramp_rate.get())
		#~new_rate_value = 0.0
		#~if new_units == "deg/sec":
			#~new_rate_value = old_rate_value / 60.0
		#~elif new_units == "deg/min":
			#~new_rate_value = old_rate_value * 60.0
		#~self.entry_ramp_rate.delete(0, "end")
		#~self.entry_ramp_rate.insert(0, str(new_rate_value))
	
	#~def validate(self):
		#~try:
			#~start_temp = float(self.entry_start_temp.get())
			#~end_temp = float(self.entry_end_temp.get())
			#~ramp_rate = float(self.entry_ramp_rate.get())
			#~# System expects ramp rate in deg/sec so convert if necessary.
			#~if self.ramp_rate_units.get() == "deg/min":
				#~ramp_rate = ramp_rate / 60.0
			#~if ((start_temp > 40.0) or (start_temp < -40.0) or (end_temp > 40.0) or (end_temp < -40.0)):
				#~tk.messagebox.showwarning("Invalid temperature", "Assay start and end temperatures must be > -40 deg C and < +40 deg C.")
				#~return 0
			#~if start_temp < end_temp:
				#~tk.messagebox.showwarning("Invalid temperature", "Assay start temperature must be greater than assay end temperature.")
				#~return 0
			#~if start_temp > self.room_temp:
				#~tk.messagebox.showwarning("Invalid temperature", "Assay start temperature must be lower than room temp.")
				#~return 0
			#~if ramp_rate > 0.0:
				#~ramp_rate = ramp_rate * -1.0
			#~self.result = start_temp, end_temp, ramp_rate
			#~return 1
		#~except:
			#~tk.messagebox.showwarning("Bad input", "Assay start temp and ramp rate must be floating point values!")
			#~return 0
		
