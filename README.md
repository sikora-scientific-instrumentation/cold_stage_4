Cold Stage 4 - PRERELEASE 1
---------------------------

A software program for the control of a solid-state experimental temperature control platform.


Installation instructions:
--------------------------

General:
* Install linux package v4l-utils (>=1.12.3-1)
* Add user to linux users group 'dialout' to give full access to usb serial port

Python:
* Install Anaconda Python 3 (>= 3.8.5) - this will come with all the popular Python modules.

Further to this you will need:
* pyserial >=3.4 (conda install pyserial)
* opencv >=4.4.0   (conda install -c conda-forge opencv)
* pillow >=7.2.0  (conda install -c anaconda pillow)
* crcmod >=1.7  (conda install -c conda-forge crcmod)


To Run Cold Stage 4:
--------------------

In the program directory, enter ipython ColdStage.py at the command line. If no physical instrument is connected you can select the 'simulation_test_device'
from the device option menu to have a play. If you have a webcam connected (or built-in) you it should detect it. If not, you can run the software without.


Licence:
--------

Cold Stage 4 is published under the terms of the GNU General Public License version 3. You should have received a copy of the GNU General Public License
along with Cold Stage 4. If not, see <http://www.gnu.org/licenses/>.


(C) 2020 Dr Sebastien Sikora.
Sikora Scientific Instrumentation, Ipswich, UK.



