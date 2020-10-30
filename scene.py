"""Support for Centralite scenes."""
import logging

from custom_components import centralite
from homeassistant.components.scene import Scene

DEPENDENCIES = ['centralite']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up scenes for the Centralite platform."""
    centralite_ = hass.data['centralite_system']

    devices = []
    for i in centralite_.scenes():
        name = centralite_.get_scene_name(i)
        if not centralite.is_ignored(hass, name):
            devices.append(CentraliteScene(centralite_, i, name))
    add_entities(devices)


class CentraliteScene(Scene):
    """Representation of a single Centralite scene."""

    def __init__(self, lj, i, name):
        """Initialize the scene."""
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
        self._lj.activate_scene(self._index)
