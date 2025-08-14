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
from homeassistant.helpers.entity import DeviceInfo 
from homeassistant.helpers import entity_registry as er
import re

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

async def _maybe_migrate_light_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Migrate legacy light unique_ids to the stable format:
      old:  "elegance.L001"  or  "elegance.L1"
      new:  "{entry_id}.load.{channel}"
    """
    reg = er.async_get(hass)
    for ent in list(reg.entities.values()):
        if ent.config_entry_id != entry.entry_id or ent.platform != DOMAIN:
            continue

        # Match "elegance.L001" or "elegance.L1"
        m = re.fullmatch(r"elegance\.L(\d+)", ent.unique_id)
        if not m:
            continue
        channel = int(m.group(1))
        new_uid = f"{entry.entry_id}.load.{channel}"
        if ent.unique_id != new_uid:
            reg.async_update_entity(ent.entity_id, new_unique_id=new_uid)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Centralite lights from a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller

    await _maybe_migrate_light_unique_ids(hass, entry)

    # Which loads to expose (user selection from options, or all)
    all_ids = ctrl.loads()
    load_ids = hub.loads_include or all_ids

    # Seed initial on/off state in one call (^G)
    initial_states: dict[int, bool] = await hass.async_add_executor_job(
        ctrl.get_all_load_states
    )

    # PASS entry.entry_id into the entity ctor
    entities = [
        CentraliteLight(
            entry_id=entry.entry_id,
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
        entry_id: str,
        hass: HomeAssistant,
        controller: Centralite,
        load_id: int,
        initially_on: bool | None = None,
    ) -> None:
        self._entry_id = entry_id
        self.hass = hass
        self.controller = controller
        self._id = int(load_id)

        # Friendly name and unique_id
        self._name = controller.get_load_name(self._id)  # e.g. "L001"
        self._attr_unique_id = f"{self._entry_id}.load.{self._id:03d}"  # zero-pad for stability

        # Group under one device card
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Centralite Controller",
            manufacturer="Centralite",
            model="Elegance / Elite",
        )

        # State
        if initially_on is not None:
            self._brightness: int | None = 255 if initially_on else 0
            self._is_on: bool | None = initially_on
        else:
            self._brightness = None
            self._is_on = None

        # Subscribe to push updates (^KxxxYY)
        self._unsub = controller.on_load_change(self._id, self._on_load_changed)

        _LOGGER.debug(
            "CentraliteLight init: id=%s name=%s uid=%s seeded_on=%s",
            self._id,
            self._name,
            self._attr_unique_id,
            initially_on,
        )

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

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from controller events when entity is removed/reloaded."""
        unsub = getattr(self, "_unsub", None)
        if unsub:
            try:
                unsub()
            except Exception:
                pass
