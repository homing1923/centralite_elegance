import logging
import serial
import threading
import binascii

WAIT_DELAY = 2

_LOGGER = logging.getLogger(__name__)

class CentraliteThread(threading.Thread):

   def __init__(self, serial, notify_event):
      threading.Thread.__init__(self, name='CentraliteThread', daemon=True)
      self._serial = serial
      self._lastline = None
      self._recv_event = threading.Event()
      self._notify_event = notify_event

   def run(self):
   
      while True:
         line = self._readline()
         _LOGGER.debug('In While True, Incoming Line %s', line)

         # ^K = load level change, P=pressed switch, R=released switch                  
         if len(line)==5 and (line[0]=='P' or line[0]=='R'):
            _LOGGER.info('  Matches P or R: %s', line)
            self._notify_event(line)
            continue            
         elif len(line)==7 and (line[0]=='^' and line[1]=='K'):
            _LOGGER.info('  Matches ^K: %s', line)
            self._notify_event(line)
            continue
         elif len(line)==48:
            # Incoming status for all loads/lights 
            _LOGGER.info('  Matches LOADS 48 hex: %s', line)
            #! this function isn't doing anything, no logging or anything
            #self.set_all_load_states(line)
            continue
         elif len(line)==96:
            # Incoming status for all switches
            _LOGGER.info('  Matches SWITCHES 96 hex: %s', line)            
            continue            
         else:
            _LOGGER.info('  UNRECOGNIZED INPUT, line is %s', line)
            continue
            
         self._lastline = line
         self._recv_event.set()

   def _readline(self):
      # This function requires the Elegance Centralite system to be configured to send third party CR and active load reporting to be ON. Centralite config software is wonky and isn't clear when the settings are saved.  Try a SEND from the main menu after setting them in the config menu.
      _LOGGER.debug('  Start of _readline')
      output = ''
      while True:
         byte = self._serial.read(size=1)
         # if CR found, then it is the end of the command; this also removes the CR from the returned data therefore .strip() not needed
         # why isn't a .read_until('\r') used??? rather than byte-by-byte, might not be supported in this version of pyserial? I tried, couldn't get it to work.
         if (byte[0] == 0x0d):
            break
         output += byte.decode('utf-8')
         
         if len(output) == 100: #max output is likely 96 for switch status
            _LOGGER.info('  Broken? OUTPUT IS 100!!!!!!!!!!!!!!!!')
            break         
         
      _LOGGER.debug('  _readline output is: %s', output)
      return output

   def get_response(self):
      self._recv_event.wait(timeout=WAIT_DELAY)
      self._recv_event.clear()
      return self._lastline

class Centralite:

   # Original Coder loaded all lights/loads by default which is a lot of likely unused devices in HA with a bigger Centralite system.
   #    CW switched code to be a list or dictionary of items to load to slim down HA.    
   # It would be nice if these IDs were defined in YAML rather than in the code but I don't know how to do that at this point.
   
   
   # friendly_name defined in YAML;  add the loads/light IDs you want in HA
   LOADS_LIST = [ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                  21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
                  41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60,
                  61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75 ]

   
   # HA scenes do not use a 'unique id' like the lights do. friendly_name does not work on scenes.  They only have a name which becomes
   #    the unique id and is used in the UI. We need to know the Centralite scene # and then HA GUI needs the name to be 
   #    something human readable/meaningful
   ACTIVE_SCENES_DICT = {
     '4': 'Upstairs Path',
     '5': 'Main Path',
     '6': 'Great Room Scene 1',
     '7': 'Great Room Scene 2',
     '8': 'Outside Eaves Christmas Lights',
     '9': 'Office Scene',
     '10': 'Landscape and Outside Lights',
     '12': 'Goodnight',
     '13': 'Kitchen Scene',
     '14': 'Garage Outside Sconce',
     '21': 'Indoor Christmas Scene',
     '22': 'Upstairs ALL',
     '24': 'Dinning Recessed and Chandelier',
     '25': 'Master Bath and Closet Lights',
     '99': 'Reload Light Status'
   }
      
   # friendly_name defined in YAML;  add the switch IDs you want in HA
   SWITCHES_LIST = [ 44, 46, 75, 100, 106, 107]   
   
   _LOGGER.info('   In pycentralite.py startup "%s"', ACTIVE_SCENES_DICT)    

   def __init__(self, url):
      _LOGGER.info('Start serial setup init using %s', url)
      self._serial = serial.serial_for_url(url, baudrate=19200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
      self._events = {}
      self._thread = CentraliteThread(self._serial, self._notify_event)
      self._thread.start()
      self._command_lock = threading.Lock()

   def _send(self, command):
      with self._command_lock:
         _LOGGER.info('Send via _send "%s"', command)
         self._serial.write(command.encode('utf-8'))

   def _sendrecv(self, command):
      with self._command_lock:
         _LOGGER.debug('Send via _sendrecv "%s"', command)
         self._serial.write(command.encode('utf-8'))
         _LOGGER.debug('   Send via _sendrecv after .write ')

         # Testing note/code that's just here as a note.
         #_LOGGER.info('testing a055')
         # adding a .encode seems to break this, the b is necessary
         #blah = "^A055"
         #self._serial.write(blah.encode('utf-8'))
         # this works too
         #self._serial.write(b"^a055")
         
         
         _LOGGER.debug('   Before read')
         
         #! The main while loop reading the RS232 seems to always capture the output.
         #! Not all of the responses from Centralite have a leading character to indicate what the response is.
         
         #result = self._thread.get_response()
         #result = self._readline()         
                  
         _LOGGER.debug('   Recv "%s"', result)
         
         return result

# Original.  What did I break?
#def _sendrecv(self, command):
#      with self._command_lock:
#         _LOGGER.info('Send "%s"', command)
#         self._serial.write(command.encode('utf-8'))
#         result = self._thread.get_response()
#         _LOGGER.info('Recv "%s"', result)
#         return result


   def _add_event(self, event_name, handler):
      _LOGGER.debug('IN _add_event, event_name is "%s"', event_name)
      event_list = self._events.get(event_name, None)
      if event_list == None:
         event_list = []
         self._events[event_name] = event_list
      event_list.append(handler)

   def _notify_event(self, event_name):
      _LOGGER.debug('Event "%s"', event_name)
      _LOGGER.debug('   Self is "%s"', self)
      
      handler_params=""
      line = str(event_name)
      # LIGHTS pass in a load level
      if line[0]=='^' and line[1]=='K': 
         load = event_name[2:5]
         level = event_name[5:7]
         event_name = '^K' + load         
         _LOGGER.debug('    Updated Event name is: %s', event_name)
         _LOGGER.debug('    Load %s Level %s', load, level)
         handler_params=level         
                     
      elif line[0]=='P' or line[0]=='R': # Pushed/released Switch
         _LOGGER.debug('    Switch, command is %s', line)
         pass  #not currently using this elif
      
      
      # _events.get() calls some HA brains?  Hint: .get() pulls a key off of a dictionary.
      event_list = self._events.get(event_name, None)
      _LOGGER.debug('Event list %s', event_list)
      _LOGGER.debug('   handler_params is %s', handler_params)
      if event_list is not None:
         _LOGGER.debug('   Getting handler')
         for handler in event_list:            
            # There is a handler assigned to each device when it is instantiated (e.g. light is _on_load_changed, call it with the new light level)
            _LOGGER.debug('   Before calling handler funct %s ', handler)
            try:               
               handler(handler_params)
            except: #catch all exceptions
               error_msg = sys.exc_info()[0]
               _LOGGER.debug('   TRY failed for handler error_msg is %s ', error_msg)               
      else:
         _LOGGER.debug('   event_list is NONE, handler not run')
         pass

   # Written by original coder for eLite, same intent as hex2bin?, I have not evaluated _hex2bits
   def _hex2bits(self, response, input_first, input_last, output_first):
      output = {}
      output_number = output_first
      for digit in range(input_first, input_last, 2):
         digit_value = int(response[digit:digit+2], 16)
         for bit in range(0, 8):
            bit_value = (digit_value & (1 << bit)) != 0
            output[output_number] = bit_value
            output_number += 1
      return output
 
   def _hex2bin_loads(self, response):
      # THIS code works, but has not be validated inside HA -- cw      
      # In this case the use of the word binary simply means the bit is 0 or 1 (e.g. on/off), each bit represents a light
      
      hex2bin_map = {
         "0":"0000", "1":"0001", "2":"0010", "3":"0011", "4":"0100", "5":"0101",
         "6":"0110", "7":"0111", "8":"1000", "9":"1001", "A":"1010", "B":"1011",
         "C":"1100", "D":"1101", "E":"1110", "F":"1111",
      }
      # break it into 6 character sets
      i = 0
      bytes = []
      while i < len(hex):
          bytes.append(hex[i:i+6])
          i = i + 6

      reversed_bytes = []
      for byteset in bytes:
          i = 0
          newbytes = ""
          while i < 6:
              newbytes = newbytes + byteset[i+1] + byteset[i]
              i = i + 2
          reversed_bytes.append(newbytes[::-1])

      binary_bytes = []
      for byteset in reversed_bytes:
          binary_rep = "".join(hex2bin_map[x] for x in byteset)
          binary_bytes.append(binary_rep[::-1])

      binary_string = "".join(binary_bytes) # collapse into a single string, each bit represents a light/load

      return binary_string

   def _hex2bin_switches(self, response):
      # Taken from loads version and tweaked for switches, which break this up in 4-digit entries instead of 6-digit.
      
      #!  Not validated as working yet.
      
      # In this case the use of the word binary simply means the bit is 0 or 1 (e.g. on/off), each bit represents a light
      
      hex2bin_map = {
         "0":"0000", "1":"0001", "2":"0010", "3":"0011", "4":"0100", "5":"0101",
         "6":"0110", "7":"0111", "8":"1000", "9":"1001", "A":"1010", "B":"1011",
         "C":"1100", "D":"1101", "E":"1110", "F":"1111",
      }
      # break it into 4 character sets
      i = 0
      bytes = []
      while i < len(hex):
          bytes.append(hex[i:i+4])
          i = i + 4

      reversed_bytes = []
      for byteset in bytes:
          i = 0
          newbytes = ""
          while i < 4:
              newbytes = newbytes + byteset[i+1] + byteset[i]
              i = i + 2
          reversed_bytes.append(newbytes[::-1])

      binary_bytes = []
      for byteset in reversed_bytes:
          binary_rep = "".join(hex2bin_map[x] for x in byteset)
          binary_bytes.append(binary_rep[::-1])

      binary_string = "".join(binary_bytes) # collapse into a single string, each bit represents a switch

      return binary_string

       
   def on_load_activated(self, index, handler):
      self._add_event('N{0:03d}'.format(index), handler)

   def on_load_deactivated(self, index, handler):
      self._add_event('F{0:03d}'.format(index), handler)

   def on_load_change(self, index, handler):
      self._add_event('^K{0:03}'.format(index), handler)

   def on_switch_pressed(self, index, handler):
      # This is called when switch.py adds all the switch devices.  When else could it run?  - cw
      _LOGGER.debug('IN on_switch_pressed, index is "%s"', index)
      _LOGGER.debug('   IN on_switch_pressed, handler is "%s"', handler)
      
      # NOTE! Centralite uses a 0 for a single board system here, format is P0 and then the 3 digit switch #
      self._add_event('P{0:04d}'.format(index), handler)

   def on_switch_released(self, index, handler):
      # NOTE! Centralite uses a 0 for a single board system here, format is P0 and then the switch # for a single board system
      _LOGGER.debug('IN on_switch_released, index is "%s"', index)
      _LOGGER.debug('   IN on_switch_released, handler is "%s"', handler)      
      self._add_event('R{0:04d}'.format(index), handler)

   def activate_load(self, index):
      self._send('^A{0:03d}'.format(index))

   def deactivate_load(self, index):
      self._send('^B{0:03d}'.format(index))

   def activate_scene(self, index, scene_name):
      # HA can't do an on/off on a single scene, so each Centralite scene has two HA scenes (one for off, one for on)
      _LOGGER.debug('IN pycentralite.py activate_scene, index is "%s"', index)
      _LOGGER.debug('IN pycentralite.py activate_scene, scene_name is "%s"', scene_name)
      index=int(index)
      if "-ON" in scene_name.upper():
        self._send('^C{0:03d}'.format(index))
      elif "-OFF" in scene_name.upper():
        self._send('^D{0:03d}'.format(index))        

   # unused, HA does not support OFF for a scene
   #def deactivate_scene(self, index):
   #   self._send('^D{0:03d}'.format(index))

   def activate_load_at(self, index, level, rate):
      self._send('^E{0:03d}{1:02d}{2:02d}'.format(index, level, rate))

   def get_load_level(self, index):
      return int(self._sendrecv('^F{0:03d}'.format(index)))

   # ^G: Get instant on/off status of all loads on this board
   # ^H: Get instant on/off status of all switches on this board.

   #! this function under developement
   def set_all_load_states(self, _incoming_hex):
      _LOGGER.debug('   IN set_all_load_states, _incoming_hex is %s', _incoming_hex)

      #t_lights = hass.data[CENTRALITE_CONTROLLER].loads()
      #_LOGGER.debug('   IN set_all_load_states, hass.data loads %s', t_lights)
      
      #_bin_string_loads = self._hex2bin_loads(_incoming_hex)

      #_LOGGER.debug('   IN set_all_load_states, after hex2bin_loads')
      
      # Process binary string bit-by-bit, start at 1 to use as light id below
      #i = 1 
      #while i < len(_bin_string_loads)+1:
      #    _light_id = str(i).zfill(3)  # zero pad for centralight id                  
      #    _light_id_state = _bin_string_loads[i:1] # get 1/0 from string for on/off in corresponding position
      #    # Update device state
      #    _LOGGER.debug('   IN set_all_load_states, centralight id should be %s', _light_id)
      #    _LOGGER.debug('   IN set_all_load_states, centralight state should be %s', _light_id_state)
      #              
      #    i = i + 1      # Increment for loop      
      return

   #! this function under developement
   def get_all_load_states(self):
      _LOGGER.debug('   IN get_all_load_states')
      # THIS CODE hasn't been validated -- where should it be triggered and when? -- cw
      response = self._sendrecv('^G')
      #return self._hex2bits(response, 0, 47, Centralite.FIRST_LOAD)  # old original code
      
      _bin_string = self._hex2bin(response)
      _LOGGER.debug('   IN get_all_load_states, _bin_string is %s', _bin_string)
      
      # Where to update light state?  Should be in light.py right????
      
      # Process binary string bit-by-bit, start at 1 to use as light id below
      #i = 1 
      #while i < len(_bin_string)+1:
      #    _light_id = str(i).zfill(3)  # zero pad for centralight id
      #    i = i + 1      
            
      #return self._hex2bits(response, 0, 47, Centralite.FIRST_LOAD)  # old original code
      return self._hex2bin(response)

   #! not used. Reads if led light on switch is active? This code is original, not adapted to CW hex2bin 
   def get_all_switch_states(self):
      _LOGGER.debug('   IN TOP get_all_switch_states')      
      _bin_string = ''
      #response = self._sendrecv('^H')
      response = self._send('^H')
      _LOGGER.debug('   IN TOP get_all_switch_states, AFTER _sendrecv response %s', response)
      #return self._hex2bits(response, 0, 39, Centralite.FIRST_SWITCH)
      #_bin_string = self._hex2bin(response)
      _LOGGER.debug('   IN get_all_switch_states, after hex2bin and _bin_string is %s', _bin_string)      
      return _bin_string

   def press_switch(self, index):
      # THIS IS NOT FULLY TESTED BUT IT DOES SEND THE COMMANDS but I didn't see any activity in real life from it
      
      # only sending a press ^I makes Centralite think a user is holding down the button causing a dim rather than an on/off
      #! I got my system stuck and it ignored my physical button presses for the single switch I was testing with, 
      #  I had to hook a laptop up to the rs232 and send it a ^Jxxx or maybe ^J0xxx and it stopped.
      
      # I'm not sure there's a need to send a button press from HA since loads/lights/scenes can be triggered/read directly.  
      # If you enable this, an immediate release button should be sent too?      
      
      #! It is not clear if these should be I0xxx or if Ixxx is sufficient.  Manual says just Ixxx for single system.
      #command_string = ""
      #command_string = '^I{0:03d}'.format(index) + '^J{0:03d}'.format(index)  # Centralite allows stacked commands
      #_LOGGER.debug('   IN press_switch, command is "%s"', command_string)
      #self._send(command_string)
      
      # A button press without a release causes, dimming right?  This isn't doing anything anymore in testing. 
      # I have no use case for it so I'm leaving code as is.
      self._send('^I{0:03d}'.format(index))   #! old, single command that hung my button      
      self._send('^J{0:03d}'.format(index))
      return

   def release_switch(self, index):
      _LOGGER.debug('   IN release_switch, index is "%s"', index)
      # HA never needs to press and hold a button, in my opinion. 
      # Centralite uses a press-and-hold for dimming. In HA we can dimm by just setting the target load level.  
      # Therefore, a release is really a simulation of a physical press/release combination.
      self._send('^I{0:03d}'.format(index))
      self._send('^J{0:03d}'.format(index))

   # friendly_name defined in YAML
   def get_switch_name(self, index):
      return 'SW{0:03d}'.format(index)

   # friendly_name defined in YAML
   def get_load_name(self, index):
      return 'L{0:03d}'.format(index)

   # Called by __init__.py
   def loads(self):
      return (Centralite.LOADS_LIST)

   def button_switches(self):
      return(Centralite.SWITCHES_LIST)

   def scenes(self):
      return(Centralite.ACTIVE_SCENES_DICT)