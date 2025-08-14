"""
Support for Centralite switches (Config Entry version).
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Centralite switches from a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller

    # Respect the UI option to include/exclude switches
    if not getattr(hub, "include_switches", False):
        _LOGGER.debug("centralite.switch: include_switches is False; skipping")
        return

    switch_ids = ctrl.button_switches()  # list[int]
    # Optional: seed state with one ^H snapshot so UI isn't 'unknown'
    initial = await hass.async_add_executor_job(ctrl.get_all_switch_states)  # {id: bool}

    entities = [
        CentraliteSwitch(
            controller=ctrl,
            switch_id=sid,
            initially_on=bool(initial.get(sid, False)),
        )
        for sid in switch_ids
    ]
    _LOGGER.debug("centralite.switch: creating %d switch entities", len(entities))
    async_add_entities(entities, False)


class CentraliteSwitch(SwitchEntity):
    """Representation of a single Centralite switch."""

    _attr_should_poll = False  # push-driven via P/R events

    def __init__(self, controller: Centralite, switch_id: int, initially_on: bool = False) -> None:
        self.controller = controller
        self._id = int(switch_id)
        self._name = controller.get_switch_name(self._id)  # e.g. "SW075"
        self._attr_unique_id = f"elegance.{self._name}"

        # State: True when physically pressed, False when released
        self._state: bool = bool(initially_on)

        # Subscribe to P/R events (push updates)
        controller.on_switch_pressed(self._id, self._on_switch_pressed)
        controller.on_switch_released(self._id, self._on_switch_released)

        _LOGGER.debug("CentraliteSwitch init: id=%s name=%s uid=%s seeded=%s",
                      self._id, self._name, self._attr_unique_id, initially_on)

    # ---------- Event handlers from controller ----------
    def _on_switch_pressed(self, *args) -> None:
        _LOGGER.debug("Switch pressed: %s", self._name)
        self._state = True
        self.schedule_update_ha_state()

    def _on_switch_released(self, *args) -> None:
        _LOGGER.debug("Switch released: %s", self._name)
        self._state = False
        self.schedule_update_ha_state()

    # ---------- HA properties ----------
    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_NUMBER: self._id}

    # ---------- Commands (simulate press/release) ----------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Simulate pressing the switch."""
        try:
            await self.hass.async_add_executor_job(self.controller.press_switch, self._id)
            # optimistic; actual state will be confirmed by P event
            self._state = True
        except Exception:
            _LOGGER.debug("press_switch failed for %s: %s", self._name, sys.exc_info()[0])
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Simulate releasing the switch."""
        try:
            await self.hass.async_add_executor_job(self.controller.release_switch, self._id)
            self._state = False
        except Exception:
            _LOGGER.debug("release_switch failed for %s: %s", self._name, sys.exc_info()[0])
        self.schedule_update_ha_state()

    # No polling update; if you want to resync from ^H occasionally, you could add:
    # async def async_update(self) -> None:
    #     states = await self.hass.async_add_executor_job(self.controller.get_all_switch_states)
    #     if states and self._id in states:
    #         self._state = bool(states[self._id])
