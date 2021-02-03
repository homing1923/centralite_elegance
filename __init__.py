"""Allows the Centralite Elegance/Elite/Eligance XL lighting system to be controlled by Home Assistant.

For more details about this component, please refer to the documentation at
"""
import logging
from collections import defaultdict

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.const import CONF_PORT
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    EVENT_HOMEASSISTANT_STOP, CONF_LIGHTS, CONF_EXCLUDE)


_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE_NAMES = 'exclude_names'
CONF_INCLUDE_SWITCHES = 'include_switches'

DOMAIN = 'centralite'

CENTRALITE_CONTROLLER = 'centralite_system'
LJ_ID_FORMAT = '{}_{}'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_EXCLUDE_NAMES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

CENTRALITE_DEVICES = 'centralite_devices'
CENTRALITE_SCENES = 'centralite_scenes'

CENTRALITE_COMPONETS = [
    'light', 'switch', 'scene'
]

def setup(hass, base_config):
    """Set up the Centralite component."""
    from .pycentralite import Centralite

    config = base_config.get(DOMAIN)
    url = config.get(CONF_PORT)
    exclude_ids = config.get(CONF_EXCLUDE)

    hass.data[CENTRALITE_CONTROLLER] = Centralite(url)

    """ Must call for each device type (light, scene, switch) """
    # Causes light.py to run
    discovery.load_platform(hass, 'light', DOMAIN, {}, config)
    
    # Causes scene.py to run (commenting stops it from being run, this is the trigger)
    discovery.load_platform(hass, 'scene', DOMAIN, {}, config)
    
    # Need to edit and uncomment to add functionality for switch (not yet implemented)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)    

    #### LIGHTS
    _LOGGER.debug("In setup about to add LIGHTS to device list")
    
    try:
        # get a list of numbers starting at FIRST_LOAD and endeding at LAST_LOAD+1
        all_devices = hass.data[CENTRALITE_CONTROLLER].loads()
    except RequestException:
        _LOGGER.exception("Error talking to MCP")
        return False

    # create a list data type of devices if the device is in all_devices?  LIGHT/LOAD SPECIFIC!
    #? I'm not sure why this is here and then another for loop below, seems like they could be combined?
    devices = [device for device in all_devices]
    """if device not in exclude_ids]"""

    centralite_devices = defaultdict(list)
    for device in devices:
        device_type = 'light'
        centralite_devices[device_type].append(device)

    #### SCENES
    _LOGGER.debug("In setup about to add SCENES to device list")
    all_scenes = hass.data[CENTRALITE_CONTROLLER].scenes()
    _LOGGER.debug('   SCENES list "%s"', all_scenes)
        
    # build list of scenes and append to devices
    for _a_scene in all_scenes:
        device_type = 'scene'
        _LOGGER.debug('   In loop to add scene "%s"', _a_scene)
        centralite_devices[device_type].append(_a_scene)

        
    #### SWITCHES/centralite style
    _LOGGER.debug("In setup about to add SWITCHES to device list")
    all_switches = hass.data[CENTRALITE_CONTROLLER].button_switches()
    _LOGGER.debug('   SWITCHES list "%s"', all_switches)
        
    # build list of scenes and append to devices
    for _a_switch in all_switches:
        device_type = 'switch'
        _LOGGER.debug('   In loop to add switch "%s"', _a_switch)
        centralite_devices[device_type].append(_a_switch)
        
    hass.data[CENTRALITE_DEVICES] = centralite_devices


    return True

def is_ignored(hass, name):
    """Determine if a load, switch, or scene should be ignored."""
    for prefix in hass.data['centralite_config'].get(CONF_EXCLUDE_NAMES, []):
        if name.startswith(prefix):
            return True
    return False

class LJDevice(Entity):
    """Representation of Centralite device entity"""

    def __init__(self, lj_device, controller, lj_device_name, *args):
        """Initialize the device"""
        _LOGGER.debug("we are in class LJDevice")
        self.lj_device = lj_device
        self.controller = controller        

        # Original get_load_name() was light specific, moved this to light.py to set self._name there to not cause name issues for switches
        _LOGGER.debug("     LJDevice incoming name is %s", lj_device_name)
        #self._name = self.controller.get_load_name(lj_device)      
        self._name = lj_device_name
        _LOGGER.debug("     LJDevice after get load name, self._name is %s", self._name)

        self.lj_id = LJ_ID_FORMAT.format(
            slugify(self._name), lj_device)

        """self.controller.register(lj_device, self._update_callback)"""

    def _update_callback(self, _device):
        """Update state"""
        self.schedule_update_ha_state(True)
    @property
    def name(self):
        return self._name

    @property 
    def should_poll(self):
        return self.lj_device.should_poll


