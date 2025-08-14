"""Support for Centralite scenes."""
import logging
import re

from homeassistant.components.scene import Scene
from homeassistant.util import slugify

from ... import (
    CENTRALITE_CONTROLLER,
    CENTRALITE_DEVICES,
    LJDevice,
)

DEPENDENCIES = ["centralite"]
ATTR_NUMBER = "number"
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up scenes for the Centralite platform."""
    controller = hass.data[CENTRALITE_CONTROLLER]

    devices = []
    scenes_dict = controller.scenes()  # dict[str, str] like {"4": "Upstairs Path", ...}

    _LOGGER.debug("centralite.scene: building entities from %d scenes", len(scenes_dict))

    # HA doesn't support OFF for scenes; create ON/OFF variants.
    for scene_id, base_name in scenes_dict.items():
        devices.append(CentraliteScene(controller, scene_id, f"{base_name}-ON"))
        devices.append(CentraliteScene(controller, scene_id, f"{base_name}-OFF"))

    add_entities(devices, False)


class CentraliteScene(LJDevice, Scene):
    """Representation of a single Centralite scene."""

    def __init__(self, controller, scene_id, name):
        """Initialize the scene."""
        self._controller = controller
        self._index = str(scene_id)  # keep as str; controller handles casting
        self._name = name

        # Build a stable unique_id that includes ON/OFF suffix
        suffix_match = re.search(r"(ON|OFF)$", self._name, re.IGNORECASE)
        suffix = suffix_match.group(1).upper() if suffix_match else ""
        self._uid = f"elegance.scene.{self._index}.{suffix or 'NA'}"

        super().__init__(self._index, controller, self._name)

        _LOGGER.debug(
            "CentraliteScene init: id=%s name=%s uid=%s",
            self._index, self._name, self._uid
        )

    # ----- HA properties -----
    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        # Override LJDevice.unique_id so we include the ON/OFF variant
        return self._uid

    @property
    def extra_state_attributes(self):
        return {ATTR_NUMBER: self._index}

    @property
    def should_poll(self):
        return False

    # ----- Actions -----
    def activate(self, **kwargs):
        """Activate the scene (Centralite ON or OFF based on name)."""
        _LOGGER.debug('Activating scene "%s" (%s)', self._name, self._index)
        self._controller.activate_scene(self._index, self._name)
