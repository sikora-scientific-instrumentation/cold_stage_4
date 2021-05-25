How to install the cold-stage control software on Microsoft Windows.  
---------------------------------------------------------------
Updated 25/05/2021.

Introduction:
--------------
This guide details how to obtain and install the cold-stage control software and prerequisites. It assumes no prior knowledge, and that none of the prerequisites are installed already. It strongly reccomends the use of a freely-available curated Python distribution and package manager (Anaconda). If you are not able or willing to use Anaconda, it is not strictly necessary as long as your system can meet the runtime requirements detailed below. It also reccomends the use of Git to make it easier for you to keep the software up-to-date with future changes/bugfixes.

Runtime requirements:
---------------------
* Python >= 3.8.5 (note - Python >=3.9 will *not* run on Windows < 8)

Further to this you will need the following Python modules, and their dependencies:
* pyserial >=3.4
* opencv >=4.4.0
* numpy >=1.18.5
* matplotlib >=3.3.0
* pillow >=8.0
* crcmod >=1.7

Instructions:
--------------

1. Install Git for Windows. It is most likely that you require the 64-bit version, the installer for which can be downloaded [Here](https://github.com/git-for-windows/git/releases/download/v2.31.1.windows.1/Git-2.31.1-64-bit.exe). Run the installer and follow the on-screen prompts selecting the default installation options.

2. Install Anaconda Python 3. It is most likely that you require the 64-bit version, the installer for which can be downloaded [Here](https://repo.anaconda.com/archive/Anaconda3-2021.05-Windows-x86_64.exe). Run the installer and follow the on-screen prompts selecting the default installation options.

3. Create a Python environment that we will configure with the required Python modules. You can think of a Python environment as a virtual workspace within which we can install a particular Python interpreter and selection of Python modules such that they will not interact or conflict with the system Python interpreter and Python modules. The only down-side is that whenever we start the control-software we will need to ensure that the newly created environment is 'activated'. First, run Anaconda Prompt via the start-menu. At the prompt, enter `conda create -n coldstage python=3.8`, which will create a new Python environment (coldstage), and within it install a Python interpreter (>=3.8) and the bare-minimum required modules. To activate the new environment, at the prompt enter `conda activate coldstage`.

4. Install the default Anaconda package selection. At the prompt, enter `conda install anaconda`.

5. Install the following additional Python packages, entering the commands shown at the prompt:
	* pyserial >=3.4 `conda install pyserial`
	* opencv >=4.4.0 `conda install -c conda-forge opencv`
	* pillow >=8.0 `conda install -c anaconda pillow`
	* crcmod >=1.7 `conda install -c conda-forge crcmod`
	* It is also reccommended that you install ipython, a nicer interactive python shell for the command line `conda install ipython` 

6. Obtain the control software from Github. In Windows file explorer, navigate to the folder where you wish to install the control software, right click within the folder and select 'Git Bash Here' to open the Git prompt. At the prompt, enter `git clone https://github.com/sikora-scientific-instrumentation/cold_stage_4.git` to download the software repository and unpack it at the chosen location.

That's it, we're done. To launch the control-software, return to the Anaconda Prompt. If you closed it previously, you will need to reactivate the Python environment that we created previously (At the prompt, enter `conda activate coldstage`). Navigate to the folder containing the control-software, created in step 6, and at the prompt, enter `ipython ColdStage.py`. If you did not install ipython in step 5, instead enter `python ColdStage.py`.

**NOTE - You will need to activate the coldstage environment *every* time you launch the Anaconda Prompt.**

In the event that you wish to update your local version of the control-software, launch Git Bash via the right-click menu from within the control-software folder, and at the prompt, enter `git pull origin master`.


The cold-stage documentation and knowledge repository can be found [here](../documentation.md)

(C) 2021 Dr Sebastien Sikora.
Sikora Scientific Instrumentation, Ipswich, UK.
