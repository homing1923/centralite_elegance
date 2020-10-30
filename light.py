"""
Support for Centralite lights.

For more details about this platform, please refer to the documentation at
"""
import logging

"""from homeassistant.components import centralite"""
from custom_components import centralite 
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ENTITY_ID_FORMAT, LightEntity)
from custom_components.centralite import (
    CENTRALITE_CONTROLLER, CENTRALITE_DEVICES, LJDevice)
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['centralite']

ATTR_NUMBER = 'number'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up lights for the Centralite platform."""
    centralite_ = hass.data[CENTRALITE_CONTROLLER]
    _LOGGER.debug("device %s", hass.data[CENTRALITE_DEVICES])
    add_entities(
        [CentraliteLight(device,centralite_) for
         device in hass.data[CENTRALITE_DEVICES]['light']], True)


class CentraliteLight(LJDevice, LightEntity):
    """Representation of a single Centralite light."""
    def __init__(self, lj_device, controller):
        """Initialize a Centralite light."""
        _LOGGER.debug("init of the light for %s", lj_device)
        super().__init__(lj_device, controller)
        self._brightness = None
        self._state = None
#        self.entity_id = ENTITY_ID_FORMAT.format(lj_device)
        LJDevice.__init__(self,lj_device,controller)

        controller.on_load_change(lj_device, self._on_load_changed)
#        controller.on_load_activated(lj_device, self._on_load_changed)
#        controller.on_load_deactivated(lj_device, self._on_load_changed)

    def _on_load_changed(self, _device):
#        lambda level 
        """Handle state changes."""
        _LOGGER.debug("Updating due to notification for %s", self._name)
        self.schedule_update_ha_state(True)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the light's name."""
        return self._name

    @property
    def brightness(self):
        """Return the light's brightness."""
        return self._brightness

    @property
    def is_on(self):
        """Return if the light is on."""
        return self._brightness != 0

    @property
    def should_poll(self):
        """Return that lights do not require polling."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            ATTR_NUMBER: self.lj_device
        }

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 255 * 99)
            self.controller.activate_load_at(self.lj_device, brightness, 1)
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self.controller.activate_load(self.lj_device)
            self._brightness = 255
        self._state = True
        self.schedule_update_ha_state()



    def turn_off(self, **kwargs):
        """Turn off the light."""
        self.controller.deactivate_load(self.lj_device)
        self._state = False
        self._brightness = 0
        self.schedule_update_ha_state()


    def update(self):
        """Retrieve the light's brightness from the Centralite system."""
        _LOGGER.debug("what is self %s", self)
        self._brightness = self.controller.get_load_level(self.lj_device) / 99 * 255
