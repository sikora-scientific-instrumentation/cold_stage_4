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

import numpy as np
import tkinter as tk
from tkinter import NORMAL, DISABLED
import tkinter.constants, tkinter.filedialog
import serial
import serial.tools.list_ports
import os
from PIL import Image, ImageTk
import cv2

import ArduinoComms

class StartUpConfig():
	def __init__(self, device_parameter_defaults):
		self.device_parameter_defaults = device_parameter_defaults
		# Configure the config window.
		self.window_open = True
		self.window = tk.Tk()
		self.window.title('Device Configuration')
		self.window.geometry("320x600")
		self.window.protocol("WM_DELETE_WINDOW", self.PassFunc)
		self.window.resizable(False, False)
		
		# Create window frames to hold gui widgets.
		self.serial_config_frame = tk.Frame(self.window, bd = 1, relief = tk.RIDGE)
		self.serial_config_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.video_config_frame = tk.Frame(self.window, bd = 1, relief = tk.RIDGE)
		self.video_config_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.buttons_frame = tk.Frame(self.window, bd = 1, relief = tk.RIDGE)
		self.buttons_frame.pack(side = "top", expand = "true", fill = tk.BOTH)
		
		# Create tk variables to hold config parameters when the window is closed.
		self.device_unique_id = tk.IntVar(self.window)
		self.device_port = tk.StringVar(self.window)
		self.device_number_of_channels = tk.IntVar(self.window)
		
		# Create a labelled drop-down selection box and populate it with the available COM port names.
		self.label_device = tk.Label(self.serial_config_frame, text="Available devices", anchor = tk.CENTER, font = ("Arial", 12, 'bold'))
		self.label_device.pack(side="top", expand="true", fill = tk.BOTH)
		self.optionmenu_selection = tk.StringVar(self.window)
		self.optionmenu_devices = tk.OptionMenu(*(self.serial_config_frame, self.optionmenu_selection) + tuple([0, 1])) # OptionMenu is linked to self.device_name StringVar.
		self.optionmenu_devices.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.label_device_welcome_string = tk.Label(self.serial_config_frame, text = "", anchor = tk.CENTER, font = ("Arial", 12, 'bold'))
		self.label_device_welcome_string.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.optionmenu_selection_trace_id = self.optionmenu_selection.trace("w", self.SerialPortCallBack)
		self.comms = ArduinoComms.ArduinoComms(self)
		self.available_ports = []
		self.PopulateDeviceList()
		
		placeholder_array = np.zeros((240, 320))
		placeholder_image = Image.fromarray(placeholder_array).convert("RGB")
		placeholder_tk_image = ImageTk.PhotoImage(image = placeholder_image)
		self.video_panel = tk.Label(self.video_config_frame, image = placeholder_tk_image)
		self.video_panel.image = placeholder_tk_image
		self.video_panel.pack(side = "top", fill = "both", expand = "yes")
		
		self.video_device_count = self.GetVideoDeviceCount()
		
		self.camera_id = tk.IntVar(self.window)
		self.label_cameras = tk.Label(self.video_config_frame, text="Video device ID:", anchor = tk.CENTER, font = ("Arial", 12, 'bold'))
		self.label_cameras.pack(side="top", expand="true", fill = tk.BOTH)
		self.spinbox = tk.Spinbox(self.video_config_frame, from_=0, to_=self.video_device_count-1, textvariable = self.camera_id)
		self.spinbox.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.camera_id.trace("w", self.VideoCallBack)
		
		self.button_start = tk.Button(self.buttons_frame, text="Start", command=self.Start)
		self.button_start.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_scan = tk.Button(self.buttons_frame, text="Scan for devices", command=self.ForceScan)
		self.button_scan.pack(side = "top", expand = "true", fill = tk.BOTH)
		self.button_quit = tk.Button(self.buttons_frame, text="Quit", command=self.Quit)
		self.button_quit.pack(side = "top", expand = "true", fill = tk.BOTH)
		
		self.action = tk.StringVar(self.window)
		
		self.capture_object = cv2.VideoCapture(self.camera_id.get())
		self.capture_object.set(3, 320)
		self.capture_object.set(4, 240)
		
		self.UpdateVideoPreview()
		self.ScanForDevices()
		self.window.mainloop()
		
	def PassFunc(self):
		pass
		
	def ForceScan(self):
		self.comms.available_ports = []
	
	def Start(self):
		self.capture_object.release()
		self.window_open = False
		# Cancel after() call if queued.
		if self.after_id_video in self.window.tk.call("after", "info"):
			self.window.after_cancel(self.after_id_video)
		if self.after_id_serial in self.window.tk.call("after", "info"):
			self.window.after_cancel(self.after_id_serial)
		self.action.set('start')
		self.window.destroy()
	
	def Quit(self):
		self.capture_object.release()
		self.window_open = False
		# Cancel after() call if queued.
		if self.after_id_video in self.window.tk.call("after", "info"):
			self.window.after_cancel(self.after_id_video)
		if self.after_id_serial in self.window.tk.call("after", "info"):
			self.window.after_cancel(self.after_id_serial)
		self.action.set('quit')
		self.window.destroy()
	
	def ScanForDevices(self):
		change_flag = self.comms.ScanForDevices()
		if change_flag == True:
			self.PopulateDeviceList()
		self.after_id_serial = self.window.after(100, self.ScanForDevices)
		
	def UpdateVideoPreview(self):
		ret, capture = self.capture_object.read()
		colour_corrected_frame_array = cv2.cvtColor(capture, cv2.COLOR_BGR2RGB)
		colour_corrected_image = Image.fromarray(colour_corrected_frame_array)
		self.colour_corrected_tk_image = ImageTk.PhotoImage(colour_corrected_image)
		self.video_panel.configure(image = self.colour_corrected_tk_image)
		self.video_panel.image = self.colour_corrected_tk_image
		self.after_id_video = self.window.after(250, self.UpdateVideoPreview)
		
	def VideoCallBack(self, *args):
		self.capture_object.release()
		self.capture_object = cv2.VideoCapture(self.camera_id.get())
		self.capture_object.set(3, 320)
		self.capture_object.set(4, 240)
	
	def SerialPortCallBack(self, *args):
		entry = self.optionmenu_selection.get()
		device_id = self.optionmenu_ids[entry]
		success_flag = self.comms.ConnectByID(device_id)
		if success_flag == True:
			self.device_unique_id.set(self.comms.unique_id)
			self.device_port.set(self.comms.port)
			self.device_number_of_channels.set(self.comms.number_of_channels)
			self.label_device_welcome_string.configure(text = self.comms.welcome_string)
		else:
			self.device_unique_id.set(None)
			self.device_port.set(None)
			self.device_number_of_channels.set(None)
			self.label_device_welcome_string.configure(text = "Device disconnected!")
			self.ScanForDevices()
	
	def PopulateDeviceList(self):
		self.optionmenu_entries = []
		self.optionmenu_ids = {}
		for device_id in self.comms.available_devices.keys():
			entry = 'Device: ' + str(device_id) + ', ' + self.comms.available_devices[device_id][1] + ' on port: ' + self.comms.available_devices[device_id][0]
			self.optionmenu_entries.append(entry)
			self.optionmenu_ids[entry] = device_id
		self.optionmenu_devices.configure(state = DISABLED)
		self.optionmenu_selection.trace_vdelete("w", self.optionmenu_selection_trace_id)
		self.optionmenu_selection.set('')
		self.optionmenu_devices['menu'].delete(0, "end")
		for new_entry in self.optionmenu_entries:
			self.optionmenu_devices['menu'].add_command(label=new_entry, command=tk._setit(self.optionmenu_selection, new_entry))
		self.optionmenu_selection_trace_id = self.optionmenu_selection.trace("w", self.SerialPortCallBack)
		self.optionmenu_selection.set(self.optionmenu_entries[0])
		self.optionmenu_devices.configure(state = NORMAL)
		
	def GetVideoDeviceCount(self):
		video_device_count = 0
		while True:
			capture_object = cv2.VideoCapture(video_device_count)
			if (capture_object is None) or (not capture_object.isOpened()):
				capture_object.release()
				break
			else:
				video_device_count += 1
			capture_object.release()
		return video_device_count
