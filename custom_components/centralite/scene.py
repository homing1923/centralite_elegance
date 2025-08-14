"""
Support for Centralite scenes (Config Entry version).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.scene import Scene
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller

    scenes: dict[str, str] = hub.scenes_map or ctrl.scenes()

    # Normalize & build desired list
    desired: list[tuple[str, str, str]] = []
    for sid_raw, base_name in scenes.items():
        sid = str(int(sid_raw))  # "007" -> "7"
        desired.append(("ON", sid, f"{base_name}-ON"))
        desired.append(("OFF", sid, f"{base_name}-OFF"))

    # Migrate any legacy unique_ids once
    await _maybe_migrate_scene_unique_ids(hass, entry)

    # De-dupe by unique_id before adding
    seen_uids: set[str] = set()
    entities: list[CentraliteScene] = []
    for suffix, sid, name in desired:
        uid = f"{entry.entry_id}.scene.{sid}.{suffix}"
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        entities.append(CentraliteScene(entry.entry_id, ctrl, sid, name))

    _LOGGER.debug("centralite.scene: creating %d scene entities", len(entities))
    async_add_entities(entities, False)


async def _maybe_migrate_scene_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """One-time migration: 'elegance.scene{sid}{suffix}' -> '{entry}.scene.{sid}.{suffix}'."""
    reg = er.async_get(hass)
    # Only look at entities belonging to this entry + this integration
    for entity_id in list(reg.entities):
        ent = reg.entities[entity_id]
        if ent.config_entry_id != entry.entry_id or ent.platform != DOMAIN:
            continue
        m = re.fullmatch(r"elegance\.scene(\d+)(ON|OFF)", ent.unique_id)
        if not m:
            continue
        sid, suffix = m.group(1), m.group(2)
        new_uid = f"{entry.entry_id}.scene.{int(sid)}.{suffix}"
        if ent.unique_id != new_uid:
            reg.async_update_entity(ent.entity_id, new_unique_id=new_uid)


class CentraliteScene(Scene):
    """Representation of a single Centralite scene (ON or OFF)."""

    _attr_should_poll = False

    def __init__(
        self,
        entry_id: str,
        controller: Centralite,
        scene_id: str,
        name: str,
    ) -> None:
        self._entry_id = entry_id
        self.controller = controller
        self._index = str(int(scene_id))  # normalize "007" -> "7"
        self._name = name

        # Stable unique_id including config entry
        m = re.search(r"(ON|OFF)$", self._name, re.IGNORECASE)
        suffix = m.group(1).upper() if m else "NA"
        self._attr_unique_id = f"{self._entry_id}.scene.{self._index}.{suffix}"

        # Group entities under one device in HA UI
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Centralite Controller",
            manufacturer="Centralite",
            model="Elegance / Elite",
        )

        _LOGGER.debug(
            "CentraliteScene init: id=%s name=%s uid=%s",
            self._index,
            self._name,
            self._attr_unique_id,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_NUMBER: self._index}

    async def async_activate(self, **_: Any) -> None:
        await self.hass.async_add_executor_job(
            self.controller.activate_scene, self._index, self._name
        )
