"""
Support for Centralite lights.

For more details about this platform, please refer to the documentation at

Checklist for creating a platform: https://developers.home-assistant.io/docs/creating_platform_code_review/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)

from . import (
    CENTRALITE_CONTROLLER,
    CENTRALITE_DEVICES,
    LJDevice,
)

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


def _lvl_99_to_255(level_0_99: int | None) -> int | None:
    if level_0_99 is None:
        return None
    # Clamp and scale to 0–255
    if level_0_99 < 0:
        level_0_99 = 0
    if level_0_99 > 99:
        level_0_99 = 99
    # Round so 99 -> 255, 1 -> ~3
    return int(round(level_0_99 * 255 / 99))


def _lvl_255_to_99(level_0_255: int) -> int:
    # Clamp and scale to 0–99
    if level_0_255 < 0:
        level_0_255 = 0
    if level_0_255 > 255:
        level_0_255 = 255
    return int(round(level_0_255 * 99 / 255))


# setup is called when HA is loading this platform
def setup_platform(hass, config, add_entities, discovery_info=None):
    controller = hass.data[CENTRALITE_CONTROLLER]
    light_ids = list(hass.data[CENTRALITE_DEVICES].get("light", []))

    # Seed initial ON/OFF from a single ^G call:
    initial = controller.get_all_load_states()  # {id: bool}

    entities = [
        CentraliteLight(dev_id, controller, initially_on=bool(initial.get(dev_id, False)))
        for dev_id in light_ids
    ]
    add_entities(entities, False)  # no need to force update if you seed



class CentraliteLight(LJDevice, LightEntity):
    """Representation of a single Centralite light."""

    def __init__(self, lj_device, controller, initially_on: bool | None = None):
        """Initialize a Centralite light."""
        if initially_on is not None:
            self._brightness = 255 if initially_on else 0
            self._state = initially_on
        else:
            self._brightness = None
            self._state = None
        
        name = controller.get_load_name(lj_device)

        # LJDevice will set name, ids, etc.
        super().__init__(lj_device, controller, name)

        # Unique ID for registry
        self._attr_unique_id = f"elegance.{name}"

        # Subscribe to push notifications from controller (^KxxxYY events)
        controller.on_load_change(lj_device, self._on_load_changed)

        _LOGGER.debug("CentraliteLight init: id=%s name=%s uid=%s",
                      lj_device, name, self._attr_unique_id)

    # ---------- Push update path ----------
    def _on_load_changed(self, new_level_str: str | None):
        """Handle level change from controller (^KxxxYY)."""
        _LOGGER.debug("Push update for %s: raw level=%s", self._name, new_level_str)
        if not new_level_str:
            return

        try:
            lvl_0_99 = int(new_level_str)
        except (TypeError, ValueError):
            _LOGGER.debug("Invalid level payload for %s: %r", self._name, new_level_str)
            return

        self._brightness = _lvl_99_to_255(lvl_0_99)
        self._state = (self._brightness or 0) > 0
        self.schedule_update_ha_state()

    # ---------- HA-required properties ----------
    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS

    @property
    def name(self):
        return self._name

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        if self._brightness is None:
            return None  # unknown at startup until we learn a value
        return self._brightness > 0

    @property
    def should_poll(self) -> bool:
        # We get pushes from the controller thread.
        return False

    @property
    def extra_state_attributes(self):
        return {ATTR_NUMBER: self.lj_device}

    # ---------- Commands ----------
    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            b_255 = int(kwargs[ATTR_BRIGHTNESS])
            b_99 = _lvl_255_to_99(b_255)
            self.controller.activate_load_at(self.lj_device, b_99, 1)
            self._brightness = b_255
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

    # ---------- Sync update on add / restore ----------
    def update(self):
        """Retrieve the light's brightness from the Centralite system."""
        try:
            lvl_0_99 = self.controller.get_load_level(self.lj_device)
        except Exception as e:
            _LOGGER.debug("get_load_level failed for %s: %s", self._name, e)
            return

        self._brightness = _lvl_99_to_255(lvl_0_99)
        self._state = (self._brightness or 0) > 0
