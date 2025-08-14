"""
Support for Centralite switch.

For more details about this platform, please refer to the documentation at
"""
import logging
import sys

from homeassistant.components.switch import SwitchEntity

from ... import (
    CENTRALITE_CONTROLLER,
    CENTRALITE_DEVICES,
    LJDevice,
)

DEPENDENCIES = ["centralite"]
ATTR_NUMBER = "number"

_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("Top of switch.py")


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Centralite switch platform."""
    controller = hass.data[CENTRALITE_CONTROLLER]
    switch_ids = list(hass.data[CENTRALITE_DEVICES].get("switch", []))

    _LOGGER.debug("centralite.switch: creating %d switch entities", len(switch_ids))

    entities = [CentraliteSwitch(dev_id, controller) for dev_id in switch_ids]
    # update_before_add=True is fine; our update() is noop (push-driven)
    add_entities(entities, True)


class CentraliteSwitch(LJDevice, SwitchEntity):
    """Representation of a single Centralite switch."""

    def __init__(self, sw_device, controller):
        """Initialize a Centralite switch."""
        name = controller.get_switch_name(sw_device)

        self._state: bool | None = False  # pressed = True, released = False
        self._uid = f"elegance.{name}"

        super().__init__(sw_device, controller, name)

        # Subscribe to P/R events
        controller.on_switch_pressed(sw_device, self._on_switch_pressed)
        controller.on_switch_released(sw_device, self._on_switch_released)

        _LOGGER.debug("CentraliteSwitch init: id=%s name=%s uid=%s",
                      sw_device, name, self._uid)

    # ---- HA properties ----
    @property
    def name(self):
        return self._name

    @property
    def is_on(self) -> bool | None:
        # True when physically pressed (momentary), False when released
        return self._state

    @property
    def should_poll(self) -> bool:
        # Push-driven by controller thread
        return False

    @property
    def extra_state_attributes(self):
        return {ATTR_NUMBER: self.lj_device}

    @property
    def unique_id(self):
        # Override LJDevice.unique_id so we keep our explicit uid
        return self._uid

    # ---- Event handlers from controller ----
    def _on_switch_pressed(self, *args):
        _LOGGER.debug("Switch pressed: %s", self._name)
        self._state = True
        self.schedule_update_ha_state()

    def _on_switch_released(self, *args):
        _LOGGER.debug("Updating released for %s", self._name)
        states = self.controller.get_all_switch_states()  # now a dict
        if states:
            self._state = bool(states.get(self.lj_device, False))
        else:
            self._state = False
        self.schedule_update_ha_state()

    # ---- Commands (simulate press/release) ----
    def turn_on(self, **kwargs):
        """Simulate pressing the switch."""
        try:
            self.controller.press_switch(self.lj_device)
        except Exception:
            _LOGGER.debug("press_switch failed: %s", sys.exc_info()[0])
        # Optimistic update; controller should push real state shortly
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Simulate releasing the switch."""
        try:
            self.controller.release_switch(self.lj_device)
        except Exception:
            _LOGGER.debug("release_switch failed: %s", sys.exc_info()[0])
        self._state = False
        self.schedule_update_ha_state()

    # No polling-based update needed (push-driven)
    def update(self):
        # Optional: keep switch LED/logic in sync on HA restarts
        states = self.controller.get_all_switch_states()
        if states:
            self._state = bool(states.get(self.lj_device, False))