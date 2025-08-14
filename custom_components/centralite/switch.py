"""
Support for Centralite switches (Config Entry version).
"""
from __future__ import annotations

import logging
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

    if not hub.include_switches:
        _LOGGER.debug("centralite.switch: include_switches is False; skipping")
        return

    all_ids = ctrl.button_switches()
    switch_ids = hub.switches_include or all_ids

    # Seed initial LED/logic state from ^H (not strictly required for momentary behavior)
    initial_states: dict[int, bool] = await hass.async_add_executor_job(
        ctrl.get_all_switch_states
    )

    entities = [
        CentraliteSwitch(
            entry_id=entry.entry_id,
            controller=ctrl,
            switch_id=sid,
            initially_on=bool(initial_states.get(sid, False)),
        )
        for sid in switch_ids
    ]

    _LOGGER.debug("centralite.switch: creating %d switch entities", len(entities))
    async_add_entities(entities, False)


class CentraliteSwitch(SwitchEntity):
    """Representation of a single Centralite switch (momentary: pressed/released)."""

    _attr_should_poll = False  # push-driven via P/R events

    def __init__(
        self,
        entry_id: str,
        controller: Centralite,
        switch_id: int,
        initially_on: bool = False,
    ) -> None:
        self._entry_id = entry_id
        self.controller = controller
        self._id = int(switch_id)
        self._name = controller.get_switch_name(self._id)  # e.g. "SW075"
        self._attr_unique_id = f"{self._entry_id}.switch.{self._name}"

        # pressed=True, released=False
        self._state: bool = bool(initially_on)

        # Subscribe to push events
        controller.on_switch_pressed(self._id, self._on_switch_pressed)
        controller.on_switch_released(self._id, self._on_switch_released)

        _LOGGER.debug(
            "CentraliteSwitch init: id=%s name=%s uid=%s seeded=%s",
            self._id,
            self._name,
            self._attr_unique_id,
            initially_on,
        )

    # ---------- Event handlers ----------
    def _on_switch_pressed(self, *_: Any) -> None:
        self._state = True
        self.schedule_update_ha_state()

    def _on_switch_released(self, *_: Any) -> None:
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
    async def async_turn_on(self, **_: Any) -> None:
        await self.hass.async_add_executor_job(self.controller.press_switch, self._id)
        # Optimistic; physical P event should follow
        self._state = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **_: Any) -> None:
        await self.hass.async_add_executor_job(self.controller.release_switch, self._id)
        self._state = False
        self.schedule_update_ha_state()
