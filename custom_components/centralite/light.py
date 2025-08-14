"""
Support for Centralite lights (Config Entry version).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)

from . import DOMAIN
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


def _lvl_99_to_255(level_0_99: int | None) -> int | None:
    if level_0_99 is None:
        return None
    if level_0_99 < 0:
        level_0_99 = 0
    if level_0_99 > 99:
        level_0_99 = 99
    return int(round(level_0_99 * 255 / 99))


def _lvl_255_to_99(level_0_255: int) -> int:
    if level_0_255 < 0:
        level_0_255 = 0
    if level_0_255 > 255:
        level_0_255 = 255
    return int(round(level_0_255 * 99 / 255))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Centralite lights from a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller

    # Which loads to expose (user selection from options, or all)
    all_ids = ctrl.loads()
    load_ids = hub.loads_include or all_ids

    # Seed initial on/off state in one call (^G)
    initial_states: dict[int, bool] = await hass.async_add_executor_job(
        ctrl.get_all_load_states
    )

    entities = [
        CentraliteLight(
            hass=hass,
            controller=ctrl,
            load_id=lid,
            initially_on=bool(initial_states.get(lid, False)),
        )
        for lid in load_ids
    ]

    _LOGGER.debug("centralite.light: creating %d light entities", len(entities))
    async_add_entities(entities, False)  # already seeded


class CentraliteLight(LightEntity):
    """Representation of a single Centralite light."""

    _attr_supported_features = SUPPORT_BRIGHTNESS
    _attr_should_poll = False  # push-driven via ^K events

    def __init__(
        self,
        hass: HomeAssistant,
        controller: Centralite,
        load_id: int,
        initially_on: bool | None = None,
    ) -> None:
        self.hass = hass
        self.controller = controller
        self._id = int(load_id)

        # Friendly name and unique_id
        self._name = controller.get_load_name(self._id)  # e.g. "L001"
        self._attr_unique_id = f"elegance.{self._name}"

        # State
        if initially_on is not None:
            self._brightness: int | None = 255 if initially_on else 0
            self._is_on: bool | None = initially_on
        else:
            self._brightness = None
            self._is_on = None

        # Subscribe to push updates (^KxxxYY)
        controller.on_load_change(self._id, self._on_load_changed)

        _LOGGER.debug(
            "CentraliteLight init: id=%s name=%s uid=%s seeded_on=%s",
            self._id,
            self._name,
            self._attr_unique_id,
            initially_on,
        )

    # ---------- Push updates from controller ----------
    def _on_load_changed(self, new_level_str: str | None) -> None:
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
        self._is_on = (self._brightness or 0) > 0
        self.schedule_update_ha_state()

    # ---------- HA properties ----------
    @property
    def name(self) -> str:
        return self._name

    @property
    def brightness(self) -> int | None:
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_NUMBER: self._id}

    # ---------- Commands ----------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            b_255 = int(kwargs[ATTR_BRIGHTNESS])
            b_99 = _lvl_255_to_99(b_255)
            await self.hass.async_add_executor_job(
                self.controller.activate_load_at, self._id, b_99, 1
            )
            self._brightness = b_255
        else:
            await self.hass.async_add_executor_job(
                self.controller.activate_load, self._id
            )
            self._brightness = 255
        self._is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.hass.async_add_executor_job(
            self.controller.deactivate_load, self._id
        )
        self._is_on = False
        self._brightness = 0
        self.schedule_update_ha_state()

    async def async_update(self) -> None:
        """Fallback single-light refresh (rarely needed)."""
        try:
            lvl_0_99 = await self.hass.async_add_executor_job(
                self.controller.get_load_level, self._id
            )
        except Exception as e:
            _LOGGER.debug("get_load_level failed for %s: %s", self._name, e)
            return
        self._brightness = _lvl_99_to_255(lvl_0_99)
        self._is_on = (self._brightness or 0) > 0
