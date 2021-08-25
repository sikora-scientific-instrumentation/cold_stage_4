"""
########################################################################
#                                                                      #
#                  Copyright 2021 Sebastien Sikora                     #
#                    sikora.scientific@gmail.com                       #
#                                                                      #
########################################################################

	This file is part of Cold Stage 4.
	PRE RELEASE 3.5

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
 
from multiprocessing import Queue, Process, Event
import threading as Thread
import time

import ArduinoComms
import CoolerChannel
import Utilities

class BackEnd():
	def __init__ (self, device_parameter_defaults, num_channels, mq_front_to_back, mq_back_to_front, mq_back_to_vlogger, mq_timestamp, event_vlogger_fault, event_back_to_front, video_enabled_flag, comms_unique_id, time_step, timing_flag, drive_mode):
		print('Backend starting.')
		self.device_parameter_defaults = device_parameter_defaults
		self.num_channels = num_channels
		
		self.mq_front_to_back = mq_front_to_back
		self.mq_back_to_front = mq_back_to_front
		self.mq_timestamp = mq_timestamp
		self.mq_back_to_vlogger = mq_back_to_vlogger
		self.event_vlogger_fault = event_vlogger_fault
		self.event_back_to_front = event_back_to_front
		
		self.setpoint = 0.0
		self.last_temperature = 0.0
		self.shut_down_flag = False
		self.comms_success_flag = False
		self.all_shutdown_initiated = False
		self.timing_flag = timing_flag
		self.time_step = time_step
		self.logging_rates = self.device_parameter_defaults['logging_rate']
		self.drive_mode = drive_mode
		self.video_enabled_flag = video_enabled_flag
		
		# Open up the serial communication link with the Arduino.
		self.comms_manager = ArduinoComms.ArduinoComms(self)
		self.comms_success_flag = self.comms_manager.ConnectByID(comms_unique_id)
		
		# Instantiate the cooler channels.
		self.cooler_channels = [CoolerChannel.CoolerChannel(self.device_parameter_defaults, self, i, self.mq_back_to_front[i], self.mq_back_to_vlogger[i], self.event_vlogger_fault[i], self.event_back_to_front[i], self.mq_timestamp[i], self.logging_rates[i], self.drive_mode[i], self.timing_flag, self.video_enabled_flag[i], self.comms_manager, self.time_step, self.device_parameter_defaults['default_pid_coefficients'][i]) for i in range(self.num_channels)]
		
		if self.comms_success_flag == True:
			# Send the datum time to the front ends via the message queue.
			for i in range(self.num_channels):
				self.mq_back_to_front[i].put((1, 'New_datum_time', (time.time() + self.time_step)))
			print("Backend(s) running.")
		else:	
			print('System startup cancelled due to comms failure.')
			self.AllShutDown()
		
		# Start the event loop timer.
		self.InitialiseTimer(self.time_step)
		# Start the main back end event loop
		self.EventLoop()
	
	# Backend event loop.
	def EventLoop(self):
		while self.shut_down_flag == False:
			# Block until the drift-free timer sets the flag to begin the current time-step.
			# Once the flag is set, reset it and then service all channels in sequence.
			while self.timer_thread_signal.wait():
				self.timer_thread_signal.clear()
				
				# Loop through and update cooler channels.
				for channel_index in range(self.num_channels):
					if self.cooler_channels[channel_index].shut_down_flag == False:
						if self.comms_success_flag == True:
							# Send messages to the hardware platform to switch to the channel-select state and then select the current channel.
							self.comms_success_flag, responses = self.comms_manager.StageChannelSelect(channel_index)
						
						if self.comms_success_flag == True:
							# Service the current channel hardware ie - Send Idle or Throttle commands to cold-stage.
							self.comms_success_flag = self.cooler_channels[channel_index].ServiceHardware()
						
						# Iterate through pending control messages from the frontend.
						next_message = ('1',)
						while next_message[0] != '':
							try:
								next_message = self.mq_front_to_back[channel_index].get(False, None)
								print(next_message)
								self.comms_success_flag = self.cooler_channels[channel_index].ServiceMessages(next_message, self.comms_success_flag)
							except:
								next_message = ('',)
						
						if ((self.comms_success_flag == False) and (self.all_shutdown_initiated == False)):
							self.AllShutDown()
				
				# Poll all channels to determine which are shut down. If they are all shut down then begin the sequence to
				# shut down the back end and close the application.
				shut_down_flags = [1 if self.cooler_channels[i].shut_down_flag == True else 0 for i in range(self.num_channels)]
				if sum(shut_down_flags) == self.num_channels:
					print('All channels stopped.')
					self.ShutdownTimer()
					self.shut_down_flag = True
					break
		
		# And we are done!
		print("Backend shut down.")
	
	def InitialiseTimer(self, interval_seconds):
		# Create a thread in which the drift-free timer will run. Set up thread events that will allow the triggering of the
		# back end event loop (by becoming 'set') and kill the timer thread before starting a new one (by becoming 'cleared').
		self.timer_thread_signal = Thread.Event()
		self.timer_thread_kill = Thread.Event()
		self.timer_thread_kill.set()
		self.timer_thread = Thread.Thread(target = Utilities.DriftFreeTimer, args = (self.timer_thread_signal, self.timer_thread_kill, interval_seconds))
		self.timer_thread.start()
		print('Drift-free timer started.')
	
	def ShutdownTimer(self):
		self.timer_thread_kill.clear()
		self.timer_thread.join()
		print('Drift-free timer stopped.')
	
	def AllShutDown(self):
		print('All channels shutting down...')
		self.all_shutdown_initiated = True
		for i in range(self.num_channels):
			self.mq_back_to_front[i].put((2, 'All_shutdown_confirm'))
