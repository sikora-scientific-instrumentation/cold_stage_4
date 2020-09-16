==============
 INSTRUCTIONS 
==============

Below are instructions for installing and using my little utility for forcing LifeCam settings. It's a command-line tool that reads in settings via XML—admittedly not the most elegant solution, but it worked great for our needs. Hopefully it will help you, too.

1. Move this folder to a permanent location, such as C:\Program Files\CameraPrefs
2. Create a shortcut to CameraPrefs.exe in your Start Menu's Startup folder.
3. Open CameraPrefs.xml in Wordpad or another text editor (Notepad has difficulties with the line endings).
4. Open the Microsoft LifeCam tool from your Start Menu.
5. Click the little white right arrow/triangle along the right border of the application to expand the settings panel.
6. Click the gear icon at the top.
7. Note the name listed in the Select Webcam drop down (e.g. "Microsoft LifeCam Cinema")
8. Scroll down and click the Properties… button under Image Adjustments.
9. Adjust the camera settings to your preference.
10. Go back to the CameraPrefs.xml document.
11. Set the name attribute in the <camera> tag to the name noted in step 7.
12. Modify the rest of the properties in the XML to match the values you set in the Properties dialog in the LifeCam tool.

===============
     NOTES     
===============

* Requires the .NET 3.5 runtime. If you're running Windows Vista or Windows 7, you should be fine.
* Higher zoom levels don't seem to take effect. For the LifeCam Studio, it seems to ignore values above 60.
* Setting auto exposure doesn't seem to work, either. To enable (or disable) this feature, set the trueColorEnabled tag's value to true (on) or false (off).

===============
    CONTACT    
===============

For information or help, feel free to contact me: 

Marcel Ray
info@marcelray.com