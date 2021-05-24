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
import time
import cv2
import os
import threading as Thread
from PIL import Image, ImageFont, ImageDraw

class VideoHandler():
	def __init__ (self, channel_id, simulation_flag, device_parameter_defaults, mq_back_to_vlogger, mq_vlogger_to_front, mq_timestamp, event_vlogger_fault, timing_flag, video_device_number):
		
		self.channel_id = channel_id
		self.mq_back_to_vlogger = mq_back_to_vlogger
		self.mq_vlogger_to_front = mq_vlogger_to_front
		self.mq_timestamp = mq_timestamp
		self.event_vlogger_fault = event_vlogger_fault
		
		self.video_device_number = video_device_number
		self.timing_flag = timing_flag
		self.simulation_flag = simulation_flag
		self.shut_down = False
		self.video_fault_flag = False
		self.logging = False
		self.output_path = ''
		
		self.image_x_dimension, self.image_y_dimension = [int(i) for i in device_parameter_defaults['webcam_default_dimensions'][self.channel_id].split('x')]
		self.image_file_format = device_parameter_defaults['webcam_image_file_format']
		
		self.text_font = ImageFont.truetype("./DejaVuSansMono.ttf", 12)
		
		self.video_fault_flag = not self.VideoConnect(self.video_device_number, self.image_x_dimension, self.image_y_dimension)
		if self.video_fault_flag == True:
			self.event_vlogger_fault.set()
		
		print("Video Logger ready.")
		
		frontend_timestamp = time.time()
		
		while not self.shut_down:
			# OpenCVs VideoCapture object uses a 5 frame fifo buffer internally, which it keeps topped-up with frames
			# captured from the capture hardware as quickly as it can. If we call the objects read() method, the oldest frame
			# in the buffer is decoded and returned, and a new frame is captured from the hardware to the buffer. 
			#
			# The result of this is that after 5 calls to read() at a constant rate, we end up 5 * rate 'behind' the present - Not ideal.
			#
			# To mitigate this we want to empty the buffer completely every time, then call read() to return the decoded next frame
			# captured to the internal buffer. This involves a lot of overhead,however, so instead we call grab() as often as possible,
			# which causes a new frame to be captured from hardware and stored in the buffer. When we actually want to return the
			# decoded newest frame in the buffer we call retrieve().
			#
			
			if self.video_fault_flag == True:
				reconnect_successful = self.VideoConnect(self.video_device_number, self.image_x_dimension, self.image_y_dimension)
				if reconnect_successful == True:
					self.video_fault_flag = False
					self.event_vlogger_fault.clear()
			
			if self.video_fault_flag == False:
				try:
					ret = self.capture_object.grab()
				except:
					ret = False
			else:
				ret = False
			
			if ((ret == False) and (self.video_fault_flag == False)):
				self.video_fault_flag = True
				self.event_vlogger_fault.set()
				
			capture_timestamp = time.time()
			
			if self.logging == False:
				# If we aren't logging then we are in 'live view' mode which we run at ~4 Hz.
				if time.time() - frontend_timestamp > 0.25:
					if self.video_fault_flag == False:
						try:
							ret, capture = self.capture_object.retrieve()
						except:
							ret = False
					else:
						ret = False
						
					if ret == True:
						rgb_capture = cv2.cvtColor(capture, cv2.COLOR_BGR2RGB)
						rgb_image = Image.fromarray(rgb_capture)
						text = [time.strftime("%Y/%m/%d %H:%M:%S %Z", time.localtime())]
						if self.simulation_flag == True:
							text.append('SIMULATION RUNNING!')
						text_spacing = 12
						draw_text = ImageDraw.Draw(rgb_image)
						offset = 0
						for i, row in enumerate(text):
							draw_text.text((0, offset), text[i], font = self.text_font, fill = "#0000FF")
							offset += text_spacing
						self.mq_vlogger_to_front.put(rgb_image)
						frontend_timestamp = time.time()
					else:
						if self.video_fault_flag == False:
							self.event_vlogger_fault.set()
							self.video_fault_flag = True
			
			# We need to check the message queue from the back end for commands:
			try:
				last_command = self.mq_back_to_vlogger.get(False, None)
			except:
				last_command = (0,)
			if last_command[0] != 0 :
				if last_command[0] == 'Logon':
					# Turn webcam auto focus off.
					self.AutoFocusOff()
					print('Video logging for channel ' + str(self.channel_id) + ' started')
					self.logging = True
				elif last_command[0] == 'Logoff':
					self.logging = False
					# Turn webcam auto focus back on.
					self.AutoFocusOn()
					print('Video logging for channel ' + str(self.channel_id) + ' stopped')
				elif last_command[0] == 'ShutDown':
					self.shut_down = True
				elif last_command[0] == 'Path':
					self.output_path = last_command[1]
					self.CreatePath(self.output_path)
					print('Video capture output path changed to ' + last_command[1])
				elif last_command[0] == 'Resolution':
					self.image_x_dimension = last_command[1]
					self.image_y_dimension = last_command[2]
					self.capture_object.set(3, self.image_x_dimension)
					self.capture_object.set(4, self.image_y_dimension)
					print('Video capture resolution changed to ' + str(last_command[1]) + 'x' + str(last_command[2]))
				elif last_command[0] == 'Go':
					if self.logging == True:
						self.Capture(timestamp = capture_timestamp, frame_params = last_command[1])
		
		# Try and release the video capture device cleanly.
		try:
			self.capture_object.release()
		except:
			pass
		# Flush vlogger_to_front queue to ensure that this process can finish and be joined.
		while True:
			try:
				self.mq_vlogger_to_front.get(False, None)
			except:
				break
		# Set vlogger mpevent to indicate videologger has been shut down.
		self.event_vlogger_fault.clear()
		
	def Capture(self, timestamp, frame_params):
		if self.video_fault_flag == False:
			try:
				ret, capture = self.capture_object.retrieve()
			except:
				ret = False
		else:
			ret = False
		
		if ret == True:
			# If we are storing a frame, put the aquisition time (temp_timestamp) on the timestamp
			# queue, then put the 'canning' time on the timestamp queue as the end of aquisition.
			if self.timing_flag:
				self.mq_timestamp.put([4, timestamp])
				self.mq_timestamp.put([5, time.time()])
			
			if self.timing_flag:
				self.mq_timestamp.put([6, time.time()])
				# Lastly, put the timestamp terminator for this timestep.
				self.mq_timestamp.put([0,])
			
			rgb_capture = cv2.cvtColor(capture, cv2.COLOR_BGR2RGB)
			rgb_image = Image.fromarray(rgb_capture)
			
			text = [time.strftime("%Y/%m/%d %H:%M:%S %Z", time.localtime()), '#         : ' + frame_params['index'], 'T (deg C) : ' + frame_params['temp'], 'SP (deg C): ' + frame_params['setpoint']]
			if self.simulation_flag == True:
				text.append('SIMULATION RUNNING!')
			text_spacing = 10
			draw_text = ImageDraw.Draw(rgb_image)
			offset = 0
			for i, row in enumerate(text):
				draw_text.text((0, offset), text[i], font = self.text_font, fill = "#0000FF")
				offset += text_spacing
			# We store the frame using a small function spun-out into another thread.
			# This way, if something else starts thrashing the disk, because we aren't waiting on the disk
			# access to continue running the event loop here (at least some of the time!), we won't be late
			# for the next timing event trigger from the back end.
			frame_canner = Thread.Thread(target = FrameCanner, args = (self.output_path + frame_params['index'] + self.image_file_format, rgb_image))
			frame_canner.start()
			self.mq_vlogger_to_front.put(rgb_image)
		else:
			self.video_fault_flag = True
			self.event_vlogger_fault.set()
	
	def AutoFocusOff(self):
		print('Autofocus OFF.')
		if os.name == 'posix':
			os.system('v4l2-ctl -c focus_auto=0 -d ' + str(self.video_device_number))
		elif os.name == 'nt':
			os.chdir('CameraPrefsOff')
			os.system('CameraPrefs.exe')
			os.chdir('..')
	
	def AutoFocusOn(self):
		if os.name == 'posix':
			os.system('v4l2-ctl -c focus_auto=1 -d ' + str(self.video_device_number))
			print('Autofocus ON.')
		elif os.name == 'nt':
			os.chdir('CameraPrefsOn')
			os.system('CameraPrefs.exe')
			print('If autofocus not on, it can be turned back on via the Microsoft Lifecam Utilities found via the Start menu.')
			os.chdir('..')
	
	def CreatePath(self, path):
		if not os.path.exists(path):
			os.makedirs(path)    

	def VideoConnect(self, video_device_number, x_dimension, y_dimension):
		# Create the opencv webcam video capture object. 1 is the external webcam, 0 would
		# be the built-in webcam on this laptop, for instance.
		try:
			self.capture_object.release()
		except:
			pass
		time.sleep(0.2)
		
		print('Attempting to connect to video source...')
		self.capture_object = cv2.VideoCapture(video_device_number)
		if self.capture_object.isOpened():
			print('Connected to video source.')
			self.capture_object.set(3, x_dimension)
			self.capture_object.set(4, y_dimension)
				
			try:	
				# Try and capture a few frames from the video device to make sure the image buffer is freshly filled-up.
				ret = False
				print('Attempting to read frames from video source...')
				for i in range(10):	
					ret, capture = self.capture_object.read()
				if ret == False:
					print('Could not read frame from video source!')
			except:
				ret = False
		else:
			print('...failed!')
			try:
				self.capture_object.release()
				ret = False
			except:
				ret = False
		
		if ret == True:
			return True
		else:
			return False
			
		
class FrameCanner():
	def __init__(self, filename, image):
		self.image = image
		self.filename = filename
		self.image.save(filename)
		
