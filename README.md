# centralite_eLite
Centralite for home assistant (this developed using an Elegance system, will be testing on a Jetstream)

I'm new to HA and this was my first ever python project.  I admit I don't understand everything in how this all works. Many thanks to pashar1's github repo for the structure and working light setup so I could largely mimic what was done to modify his scene & switch skeleton he already had stubbed. I've tried to document with comments things I learned.  

I also have a jetstream system so I'll be updating this and likely creating a fork of it for Jetstream.  I'm sure there are bugs -- I'm surprised I got it this far with my new python and HA experience.

My setup:
Raspberry Pi 4 running on an SSD
Home Assistant OS 5.10 (using the HA OS image for install)

Centralite System Prep:

You must enable a few settings in the Centralite System configuration software. 
- You must enable CR being sent with commands to the 3rd party system.  
- Enable the loads for "load report". There is a global setting for this but it won't save on my Elegance system so I had to set it per load.
- Also, for switches you will need to enable "Third party spontaneous output".  
- This setup uses the RS232 port on the Centralite to communicate.  An RS232->USB adapter on the HA side works for me (rPi HA OS)


On Home Assistant, make this directory and put github files in: config/custom_components/centralite

configuration.yaml should have these added (find usb via command line using: dmesg |grep usb  ):

```
homeassistant:
  customize: !include centralite_desc.yaml

centralite:
  port: /dev/ttyUSB1
```

In the pycentralite.py file, you need to modify these variables to support your system and which devices you want in HA:
- LOADS_LIST
- ACTIVE_SCENES_DICT
- SWITCHES_LIST

centralite_desc.yaml should look like this:

  """ NOTE THAT Scenes do not support friendly_name.  Their name is their only identifier """
```
  switch.sw044:
    friendly_name: "Office ALL On Switch"  
  switch.sw046:
    friendly_name: "Office Recessed Switch"
  switch.sw075:
    friendly_name: "Master Bath - Shower Switch"
    
  light.l001:
    friendly_name: "Upstairs Hall Recessed Lights"
  light.l002:
    friendly_name: "Upstairs West Rm - Closet Light"
  light.l003:
    friendly_name: "Upstairs North Rm - Vanity/sink light"
```
