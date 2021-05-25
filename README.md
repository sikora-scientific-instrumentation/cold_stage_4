Cold Stage 4 - PRE-RELEASE 2.3
----------------------------
Updated 25/05/2021.

A software program for the control of a solid-state experimental temperature control platform.


Installation requirements:
-------------------------

Linux specific:
* Install linux package v4l-utils (>=1.12.3-1)
* Add user to linux users group 'dialout' to give full access to usb serial port

Python:
* Install Anaconda Python 3 (>= 3.8.5)
* Create a new Python environment for the coldstage software (conda create -n coldstage python=3.8)
* Activate the new Python environment (conda activate coldstage)
* Install the default anaconda packages (conda install anaconda)

Further to this you will need (may have been installed as part of default packages, run the commands below to confirm):
* pyserial >=3.4 (conda install pyserial)
* opencv >=4.4.0   (conda install -c conda-forge opencv)
* pillow >=7.2.0  (conda install -c anaconda pillow)
* crcmod >=1.7  (conda install -c conda-forge crcmod)

Detailed instructions for installation on Windows can be found [here](getting_started/installation_on_windows.md)

To Run Cold Stage 4:
--------------------

* Using the command line (Linux) or Anaconda Prompt (Windows), navigate to the program directory.
* Activate the coldstage Python environment we created (conda activate coldstage)
* Run ColdStage.py to start the control software (ipython ColdStage.py)

If no physical instrument is connected you can select the 'simulation_test_device' from the device option menu to have a play. If you have a webcam connected (or built-in) it should detect it. If not, you can run the software without.

The cold-stage documentation and knowledge repository can be found [here](documentation/documentation.md)

Licence:
--------

Cold Stage 4 is published under the terms of the GNU General Public License version 3. You should have received a copy of the GNU General Public License
along with Cold Stage 4. If not, see <http://www.gnu.org/licenses/>.


(C) 2021 Dr Sebastien Sikora.
Sikora Scientific Instrumentation, Ipswich, UK.
