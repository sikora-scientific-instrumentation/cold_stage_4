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
 
class Logger():
    def __init__ (self, mq_back_to_logger, file_path):
        self.mq_back_to_logger = mq_back_to_logger
        self.file_path = file_path
        
        shut_down = False
        
        print("Logger ready.")
        
        while shut_down == False:
            most_recent_row = self.mq_back_to_logger.get(True, timeout=None)
            if most_recent_row == 'Shutdown':
                shut_down = True
            else:
                log_file = open(self.file_path, 'a')
                self.AppendRow(log_file, most_recent_row)
                self.CloseFile(log_file)
        
        print("Logger shut down.")
        # Function ends.
    
    def AppendRow(self, log_file, row):
        log_file.write(str(row) + '\n')
    
    def CloseFile(self, log_file):
        log_file.close()
