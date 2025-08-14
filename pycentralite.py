import logging
import serial
import threading
import sys  # needed by your exception handler

WAIT_DELAY = 2
SERIAL_TIMEOUT = 1.0  # seconds, tune as needed
ENCODING = "utf-8"

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
            if line is None:
                continue  # timeout or decode issue; try again

            _LOGGER.debug('In While True, Incoming Line %s', line)

            handled = False
            if len(line) == 5 and (line[0] in ('P', 'R')):
                _LOGGER.info('  Matches P or R: %s', line)
                self._notify_event(line)
                handled = True
            elif len(line) == 7 and line.startswith('^K'):
                _LOGGER.info('  Matches ^K: %s', line)
                self._notify_event(line)
                handled = True
            elif len(line) == 48:
                _LOGGER.info('  Matches LOADS 48 hex: %s', line)
                try:
                  states = Centralite.decode_loads_48hex(line)
                except Exception as e:
                  _LOGGER.debug("decode error on ^G frame: %s", e)
                  continue

                # fire pseudo-^K events so existing light handlers update
                for load_id, is_on in states.items():
                  level = "99" if is_on else "00"
                  self._notify_event(f"^K{load_id:03d}{level}")
                # fall through to record last line/signal

            elif len(line) == 96:
                _LOGGER.info('  Matches SWITCHES 96 hex: %s', line)
                handled = True
            else:
                _LOGGER.info('  UNRECOGNIZED INPUT, line is %s', line)

            # Always store last line & signal
            self._lastline = line
            self._recv_event.set()

   def _readline(self):
        _LOGGER.debug('  Start of _readline')
        output_bytes = bytearray()
        while True:
            b = self._serial.read(size=1)
            if not b:  # timeout
                if output_bytes:
                    break  # return partial (best effort)
                return None
            if b[0] == 0x0D:  # CR
                break
            output_bytes.extend(b)
            if len(output_bytes) >= 100:
                _LOGGER.info('  Broken? OUTPUT IS 100!!!!!!!!!!!!!!!!')
                break
        try:
            s = output_bytes.decode(ENCODING, errors='replace')
        except Exception as e:
            _LOGGER.warning("  Decode error in _readline: %s", e)
            return None
        _LOGGER.debug('  _readline output is: %s', s)
        return s

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
        self._serial = serial.serial_for_url(
            url,
            baudrate=19200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=SERIAL_TIMEOUT,   # add timeout
            write_timeout=SERIAL_TIMEOUT,
        )
        self._events: dict[str, list] = {}
        self._command_lock = threading.Lock()
        self._thread = CentraliteThread(self._serial, self._notify_event)
        self._thread.start()

   def _send(self, command):
        with self._command_lock:
            if not command.endswith('\r'):
                command = command + '\r'
            _LOGGER.info('Send via _send "%s"', command.rstrip())
            self._serial.write(command.encode(ENCODING))

   def _sendrecv(self, command):
        with self._command_lock:
            if not command.endswith('\r'):
                command = command + '\r'
            _LOGGER.debug('Send via _sendrecv "%s"', command.rstrip())
            self._serial.write(command.encode(ENCODING))
            _LOGGER.debug('   Before read')
        # release lock before waiting for thread signal
        result = self._thread.get_response()
        _LOGGER.debug('   Recv "%s"', result)
        return result

   def get_response(self):
      got = self._recv_event.wait(timeout=WAIT_DELAY)
      self._recv_event.clear()
      return self._lastline if got else None

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
   # response is 48 hex chars, grouped in 6-char chunks (3 bytes)
      hex2bin_map = {
         "0":"0000","1":"0001","2":"0010","3":"0011","4":"0100","5":"0101",
         "6":"0110","7":"0111","8":"1000","9":"1001","A":"1010","B":"1011",
         "C":"1100","D":"1101","E":"1110","F":"1111",
      }
      s = response.upper()
      i = 0
      chunks = []
      while i < len(s):
         chunks.append(s[i:i+6])  # 3 bytes per chunk
         i += 6

      reversed_bytes = []
      for chunk in chunks:
         nb = ""
         for j in range(0, len(chunk), 2):
               nb += chunk[j+1] + chunk[j]  # swap each byte’s nibbles (AB→BA)
         reversed_bytes.append(nb[::-1])  # reverse byte order for this chunk

      bits = []
      for rb in reversed_bytes:
         bits.append("".join(hex2bin_map[x] for x in rb)[::-1])
      return "".join(bits)

   def _hex2bin_switches(self, response):
      hex2bin_map = {
         "0":"0000","1":"0001","2":"0010","3":"0011","4":"0100","5":"0101",
         "6":"0110","7":"0111","8":"1000","9":"1001","A":"1010","B":"1011",
         "C":"1100","D":"1101","E":"1110","F":"1111",
      }
      s = response.upper()
      i = 0
      chunks = []
      while i < len(s):
         chunks.append(s[i:i+4])  # 2 bytes per chunk
         i += 4

      reversed_bytes = []
      for chunk in chunks:
         nb = ""
         for j in range(0, len(chunk), 2):
               nb += chunk[j+1] + chunk[j]
         reversed_bytes.append(nb[::-1])

      bits = []
      for rb in reversed_bytes:
         bits.append("".join(hex2bin_map[x] for x in rb)[::-1])
      return "".join(bits)


       
   def on_load_activated(self, index, handler):
      self._add_event('N{0:03d}'.format(index), handler)

   def on_load_deactivated(self, index, handler):
      self._add_event('F{0:03d}'.format(index), handler)

   def on_load_change(self, index, handler):
      self._add_event('^K{0:03d}'.format(index), handler)

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
   def get_all_load_states(self) -> dict[int, bool]:
      """Send ^G and return {load#: on/off}."""
      _LOGGER.debug("   IN get_all_load_states")
      resp = self._sendrecv('^G')
      try:
         states = self.decode_loads_48hex(resp)
      except Exception as e:
         _LOGGER.debug("decode_loads_48hex failed: %s (resp=%r)", e, resp)
         return {}
      _LOGGER.debug("   load states decoded for %d loads", len(states))
      return states

   def get_all_switch_states(self) -> dict[int, bool]:
        """Send ^H and return {switch#: on/off} (LED/logic state per manual)."""
        _LOGGER.debug("   IN get_all_switch_states")
        resp = self._sendrecv('^H')
        try:
            states = self.decode_switches_96hex(resp)
        except Exception as e:
            _LOGGER.debug("decode_switches_96hex failed: %s (resp=%r)", e, resp)
            return {}
        _LOGGER.debug("   switch states decoded for %d switches", len(states))
        return states


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


   # ---- ASCII-hex -> boolean maps (per manual) -----------------------------
   @staticmethod
   def _bits_from_byte(byte_val: int):
        """Yield 8 booleans LSB->MSB (bit0..bit7)."""
        for bit in range(8):
            yield bool((byte_val >> bit) & 0x01)

   @staticmethod
   def decode_loads_48hex(response: str) -> dict[int, bool]:
        """
        Decode ^G response: 48 ASCII hex digits (or any multiple of 6).
        Every 6 hex digits represent 3 bytes = 24 loads (bits), LSB-first.
        Chunks map sequentially: loads 1..24, 25..48, etc.
        Returns { load_number(1-based): on(bool) }.
        """
        if not response:
            return {}
        s = response.strip().upper()
        if len(s) % 6 != 0:
            # be tolerant; ignore trailing partial
            s = s[: len(s) // 6 * 6]

        result: dict[int, bool] = {}
        load_base = 0  # 0, 24, 48, ...

        for off in range(0, len(s), 6):
            chunk = s[off : off + 6]
            # bytes: least-significant, middle, most-significant
            b0 = int(chunk[0:2], 16)  # loads 1..8   (relative)
            b1 = int(chunk[2:4], 16)  # loads 9..16
            b2 = int(chunk[4:6], 16)  # loads 17..24

            # Map 3 bytes -> 24 loads
            idx = load_base + 1  # convert to 1-based
            for bitval in Centralite._bits_from_byte(b0):  # 8 bits -> loads 1..8
                result[idx] = bitval
                idx += 1
            for bitval in Centralite._bits_from_byte(b1):  # 9..16
                result[idx] = bitval
                idx += 1
            for bitval in Centralite._bits_from_byte(b2):  # 17..24
                result[idx] = bitval
                idx += 1

            load_base += 24

        return result

   @staticmethod
   def decode_switches_96hex(response: str) -> dict[int, bool]:
        """
        Decode ^H response: 96 ASCII hex digits (or any multiple of 4).
        Every 4 hex digits represent 2 bytes = 16 switches (bits), LSB-first.
        Chunks map sequentially: switches 1..16, 17..32, etc.
        Returns { switch_number(1-based): on(bool) }.
        """
        if not response:
            return {}
        s = response.strip().upper()
        if len(s) % 4 != 0:
            s = s[: len(s) // 4 * 4]

        result: dict[int, bool] = {}
        sw_base = 0  # 0, 16, 32, ...

        for off in range(0, len(s), 4):
            chunk = s[off : off + 4]
            # bytes: least-significant, most-significant
            b0 = int(chunk[0:2], 16)  # switches 1..8 (relative)
            b1 = int(chunk[2:4], 16)  # switches 9..16

            idx = sw_base + 1
            for bitval in Centralite._bits_from_byte(b0):  # 1..8
                result[idx] = bitval
                idx += 1
            for bitval in Centralite._bits_from_byte(b1):  # 9..16
                result[idx] = bitval
                idx += 1

            sw_base += 16

        return result
   