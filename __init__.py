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

    discovery.load_platform(hass, 'light', DOMAIN, {}, config)

    try:
        all_devices = hass.data[CENTRALITE_CONTROLLER].loads()
    except RequestException:
        _LOGGER.exception("Error talking to MCP")
        return False

    
    devices = [device for device in all_devices]
    """if device not in exclude_ids]"""

    centralite_devices = defaultdict(list)
    for device in devices:
        device_type = 'light'
        centralite_devices[device_type].append(device)
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

    def __init__(self, lj_device, controller):
        """Initialize the device"""
        _LOGGER.debug("we are in class LJDevice")
        self.lj_device = lj_device
        self.controller = controller

        self._name = self.controller.get_load_name(lj_device)

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


