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
         _LOGGER.debug('In While True, Incoming Line "%s"', line)

         # ^K = load level change, P=pressed switch, R=released switch                  
         if len(line)==5 and (line[0]=='P' or line[0]=='R'):
            _LOGGER.info('  Matches P or R: %s"', line)
            self._notify_event(line)
            continue            
         if len(line)==7 and (line[0]=='^' and line[1]=='K'):
            _LOGGER.info('  Matches ^K: %s"', line)
            self._notify_event(line)
            continue
         self._lastline = line
         self._recv_event.set()

   def _readline(self):
      output = ''
      while True:
         byte = self._serial.read(size=1)
         # if CR found, then it is the end of the command; this also removes the CR from the returned data therefore .strip() not needed
         # why isn't a .read_until('\r') used??? rather than byte-by-byte, might not be supported in this version of pyserial? I tried, couldn't get it to work.
         if (byte[0] == 0x0d):
            break
         output += byte.decode('utf-8')
      return output

   def get_response(self):
      self._recv_event.wait(timeout=WAIT_DELAY)
      self._recv_event.clear()
      return self._lastline

class Centralite:

   # Original Coder loaded all lights/loads by default which is a lot of likely unused devices in HA with a bigger Centralite system.
   #    CW switched code to be a list or dictionary of items to load to slim down HA
   #FIRST_LOAD = 1  #!unused now?
   # I'm choosing the last load that I have documented, I may have others past this number that I have not named yet or needed to control
   #LAST_LOAD = 72 #!unused now?
   #FIRST_SCENE = 1 #!unused now?
   #LAST_SCENE = 41 #!unused now?
   #FIRST_SWITCH = 1  #!unused now?
   #LAST_BUTTON_SWITCH = 96
   #LAST_BUTTON_SWITCH = 50 #!unused now?
   #LAST_SWITCH = 138  
   #LAST_SWITCH = 60 #!unused now?
   
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
     '9': 'Office Scene',
     '10': 'Landscape and Outside Lights',
     '12': 'Goodnight',
     '13': 'Kitchen Scene',
     '14': 'Garage Outside Sconce',
     '21': 'Indoor Christmas Scene',
     '22': 'Upstairs ALL',
     '24': 'Dinning Recessed and Chandelier',
     '25': 'Master Bath and Closet Lights'
   }
      
   # friendly_name defined in YAML;  add the loads/light IDs you want in HA
   SWITCHES_LIST = [ 44, 46, 75]
   
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
         #_LOGGER.debug('Send via _sendrecv "%s"', command)
         self._serial.write(command.encode('utf-8'))

         #_LOGGER.info('testing a055')
         # adding a .encode seems to break this, the b is key
         #blah = "^A055"
         #self._serial.write(blah.encode('utf-8'))
         # this works too
         #self._serial.write(b"^a055")
         
         result = self._thread.get_response()
         #_LOGGER.debug('Recv "%s"', result)
         
         return result

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

   # Written by original coder, duplicate intent as hex2bin I think
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
 
   def _hex2bin(self, response):
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
      if "-ON" in scene_name.upper():
        self._send('^C{0:03d}'.format(index))
      elif "-OFF" in scene_name.upper():
        self._send('^D{0:03d}'.format(index))

   # unused, HA does not support OFF for a scene, commenting this out causes the scene.py not to run
   #def deactivate_scene(self, index):
   #   self._send('^D{0:03d}'.format(index))

   def activate_load_at(self, index, level, rate):
      self._send('^E{0:03d}{1:02d}{2:02d}'.format(index, level, rate))

   def get_load_level(self, index):
      return int(self._sendrecv('^F{0:03d}'.format(index)))

   # ^G: Get instant on/off status of all loads on this board
   # ^H: Get instant on/off status of all switches on this board.

   def get_all_load_states(self):
      # THIS CODE hasn't been validated -- where should it be triggered and when? -- cw
      response = self._sendrecv('^G')
      #return self._hex2bits(response, 0, 47, Centralite.FIRST_LOAD)  # old original code
      
      _bin_string = self._hex2bin(response)
      
      # Process binary string bit-by-bit, start at 1 to use as light id below
      #i = 1 
      #while i < len(_bin_string)+1:
      #    _light_id = str(i).zfill(3)  # zero pad for centralight id
      #    i = i + 1      
            
      #return self._hex2bits(response, 0, 47, Centralite.FIRST_LOAD)  # old original code
      return self._hex2bin(response)

   #! not used. Reads if led light on switch is active? This code is original, not adapted to CW hex2bin 
   #def get_all_switch_states(self):
   #   response = self._sendrecv('^H')
   #   return self._hex2bits(response, 0, 39, Centralite.FIRST_SWITCH)

   def press_switch(self, index):
      # only sending a press ^I makes Centralite think a user is holding down the button causing a dim rather than an on/off
      #! I got my system stuck ignoring my physical button I was testing with, had to hook a laptop up to the rs232 and send it a ^Jxxx or maybe ^J0xxx and it stopped.
      #! I'm not sure there's a need to send a button press from HA since loads/lights/scenes can be triggered directly.  
      # If you enable this, an immediate release button should be sent too?
      
      #! It is not clear if these should be I0xxx or if Ixxx is sufficient.  Manual says just Ixxx for single system.
      #command_string = ""
      #command_string = '^I{0:03d}'.format(index) + '^J{0:03d}'.format(index)
      #_LOGGER.debug('   IN press_switch, command is "%s"', command_string)
      #self._send(command_string)
      
      # A button press without a release causes, dimming right?  This isn't doing anything anymore in testing. 
      # I have no use case for it so I'm leaving code as is.
      self._send('^I{0:03d}'.format(index))   #! old, single command that hung my button      
      self._send('^J{0:03d}'.format(index))
      return

   def release_switch(self, index):
      _LOGGER.debug('   IN release_switch, index is "%s"', index)
      self._send('^J{0:03d}'.format(index))

   # friendly_name defined in YAML
   def get_switch_name(self, index):
      return 'SW{0:03d}'.format(index)

   # friendly_name defined in YAML
   def get_load_name(self, index):
      return 'L{0:03d}'.format(index)

   #! with the move to a dictionary to create the names, I think this function is unused.  -- cw
   #def get_scene_name(self, index):
   #   return 'SC{0:03d}'.format(index)

   # Called by __init__.py
   def loads(self):
      # return a list of numbers starting at FIRST_LOAD and endeding at LAST_LOAD+1
      #return range(Centralite.FIRST_LOAD, Centralite.LAST_LOAD+1)
      return (Centralite.LOADS_LIST)

   def button_switches(self):
      #return range(Centralite.FIRST_SWITCH, Centralite.LAST_BUTTON_SWITCH+1)
      return(Centralite.SWITCHES_LIST)

   #! not used?
   #def all_switches(self):
   #   return range(Centralite.FIRST_SWITCH, Centralite.LAST_SWITCH+1)

   def scenes(self):
      return(Centralite.ACTIVE_SCENES_DICT)