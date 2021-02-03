"""
Support for Centralite switch.

For more details about this platform, please refer to the documentation at
"""
import logging

from custom_components import centralite
from homeassistant.components.switch import SwitchEntity

from custom_components.centralite import (
    CENTRALITE_CONTROLLER, CENTRALITE_DEVICES, LJDevice)

DEPENDENCIES = ['centralite']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("Top of switch.py")

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Centralite switch platform."""
    centralite_ = hass.data[CENTRALITE_CONTROLLER]
    
    _LOGGER.debug("In switch.py, device %s", hass.data[CENTRALITE_DEVICES])

    add_entities(
        [CentraliteSwitch(device,centralite_) for
         device in hass.data[CENTRALITE_DEVICES]['switch']], True)
    


class CentraliteSwitch(LJDevice, SwitchEntity):
    """Representation of a single Centralite switch."""

    #def __init__(self, hass, lj, i, name):
    def __init__(self, sw_device, controller):
        """Initialize a Centralite switch."""
        _LOGGER.debug("init of the SWITCH for sw_device %s", sw_device)
                
        self._hass = controller
        self._lj = sw_device
        self._index = sw_device
        self._state = None
        self._name = controller.get_switch_name(sw_device) # self._name required from __init__.py LJDevice init
        super().__init__(sw_device, controller, self._name)
        
        #! this causes problems, I copied this from the light.py thinking it was needed. Seems ok without it.
        #LJDevice.__init__(self, sw_device, controller, self._name)  
        
        controller.on_switch_pressed(sw_device, self._on_switch_pressed)
        controller.on_switch_released(sw_device, self._on_switch_released)
        
        _LOGGER.debug("   END of init of the SWITCH for sw_device %s", sw_device)

    # *args is needed even though calling handler_params is empty
    def _on_switch_pressed(self, *args):
        _LOGGER.debug("Updating pressed for %s", self._name)
        _LOGGER.debug("   current state %s", self._state)
        self._state = True
        _LOGGER.debug("   after set to True, current state %s", self._state)
        try:
            self.schedule_update_ha_state()
        except:
            error_msg = sys.exc_info()[0]
            _LOGGER.debug("   failed schedule update ha state, error_msg: %s", error_msg)

    def _on_switch_released(self, *args):
        _LOGGER.debug("Updating released for %s", self._name)
        self._state = False
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return if the switch is pressed."""
        return self._state

    @property
    def should_poll(self):
        """Return that polling is not necessary."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes."""
        return {
            ATTR_NUMBER: self._index
        }

    def turn_on(self, **kwargs):
        """Press the switch."""
        self.controller.press_switch(self._index)

    def turn_off(self, **kwargs):
        """Release the switch."""
        #self._lj.release_switch(self._index)
        self.controller.release_switch(self._index)
