# cold_stage_4
A software program for the control of a solid-state experimental temperature control platform.

Installation instructions:
--------------------------

General:
* Install linux package v4l-utils
* Add user to linux users group 'dialout' to give full access to usb serial port

Python:
* Install Anaconda Python 3 (>= 3.8.5) - this will come with all the popular Python modules.

Further to this you will need:
* pyserial (conda install pyserial)
* opencv   (conda install -c conda-forge opencv)
* pillow   (conda install -c anaconda pillow)
* crcmod   (conda install -c conda-force crcmod)

To Run Cold Stage 4:
--------------------

In the program directory, enter ipython ColdStage.py at the command line. If no physical instrument is connected you can select the 'simulation_test_device'
from the device option menu to have a play.


