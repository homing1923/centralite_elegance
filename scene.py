"""Support for Centralite scenes."""
import logging

from custom_components import centralite
from homeassistant.components.scene import Scene

from custom_components.centralite import (
    CENTRALITE_CONTROLLER, CENTRALITE_DEVICES, LJDevice)

DEPENDENCIES = ['centralite']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("Top of scene.py")

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up scenes for the Centralite platform."""
    centralite_ = hass.data['centralite_system']
    
    devices = []
    
    # .scenes() simply gets a LIST of scenes that need to be created (manually entered in pycentralite.py)

    _LOGGER.debug('   In scene.py, device "%s"', hass.data[CENTRALITE_DEVICES])

    # Heads up: HA's definition of a scene is a little different than Centralite and HA does not support an OFF for a scene.
    #   In order to make it work, this below creates two HA scenes (one for ON, one for OFF) for each of the scenes to be created.

    scenes_dict = centralite_.scenes()
    for i in scenes_dict:
        # i is the dictionary key
        _LOGGER.debug('      In FOR, i is "%s"', i)
        #name = centralite_.get_scene_name(i)  # not needed with implementation of the dictionary with names
        name = scenes_dict[i]
        #_LOGGER.debug('      In FOR, name is "%s"', name)
        name_on = name + "-ON"
        #_LOGGER.debug('      In FOR, name_on is "%s"', name_on)
        name_off = name + "-OFF"
        #_LOGGER.debug('      In FOR, name_off is "%s"', name_off)
        devices.append(CentraliteScene(centralite_, i, name_on))
        devices.append(CentraliteScene(centralite_, i, name_off))        
        
        #! original code by original programmer
        #devices.append(CentraliteScene(centralite_, i, name))        
        #if not centralite.is_ignored(hass, name):
        #    devices.append(CentraliteScene(centralite_, i, name))
        
    #_LOGGER.debug('   Before add_entities, devices has "%s"', devices) 
    add_entities(devices)


class CentraliteScene(Scene):
    """Representation of a single Centralite scene."""
    _LOGGER.debug('   In CentraliteScene') 
    
    def __init__(self, lj, i, name):
        """Initialize the scene."""
        _LOGGER.debug('   In CentraliteScene init, lj = "%s"', lj) 
        _LOGGER.debug('   In CentraliteScene init, i = "%s"', i) 
        _LOGGER.debug('   In CentraliteScene init, name = "%s"', name) 
        
        self._lj = lj
        self._index = i
        self._name = name        

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes."""
        return {
            ATTR_NUMBER: self._index
        }

    def activate(self):
        """Activate the scene."""
        _LOGGER.debug('   In CentraliteScene activate, name = "%s"', self._name) 
        self._lj.activate_scene(self._index, self._name)

    # unused, HA does not support OFF for a scene, commenting this out causes the scene.py not to run
    #def deactivate(self):
    #    """Deactivate the scene."""
    #    self._lj.deactivate_scene(self._index)
        
    def should_poll(self):
        """Return that does not require polling."""
        return False        