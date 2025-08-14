"""
Support for Centralite scenes (Config Entry version) with
name-keyed unique_ids so the scene number can be changed in the UI.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.scene import Scene
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import slugify

from . import DOMAIN
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller
    scenes: dict[str, str] = hub.scenes_map or ctrl.scenes()  # { "12": "Goodnight", ... }

    # Build desired entities keyed by scene name (stable) not number
    desired: list[tuple[str, str, str]] = []  # (suffix, key, friendly_name_with_suffix)
    for sid_raw, base_name in scenes.items():
        key = slugify(base_name) or f"scene_{int(sid_raw)}"  # fallback
        desired.append(("ON", key, f"{base_name}-ON"))
        desired.append(("OFF", key, f"{base_name}-OFF"))

    # Migrate old numeric unique_ids -> name-keyed unique_ids (one time)
    await _maybe_migrate_scene_unique_ids(hass, entry, scenes)

    # Helper to lookup current number by key (latest options)
    @callback
    def sid_lookup(scene_key: str) -> str | None:
        # current map from options/controller
        current = (hass.data[DOMAIN][entry.entry_id].scenes_map or ctrl.scenes())
        # invert: name -> sid (normalize names)
        inv = {slugify(v): str(int(k)) for k, v in current.items()}
        return inv.get(scene_key)

    # De-dupe and add
    seen_uids: set[str] = set()
    entities: list[CentraliteScene] = []
    for suffix, key, friendly in desired:
        uid = f"{entry.entry_id}.scene.{key}.{suffix}"
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        entities.append(
            CentraliteScene(
                entry_id=entry.entry_id,
                controller=ctrl,
                scene_key=key,
                friendly_name=friendly,
                sid_lookup=sid_lookup,
            )
        )

    _LOGGER.debug("centralite.scene: creating %d scene entities", len(entities))
    async_add_entities(entities, False)


async def _maybe_migrate_scene_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, scenes_map: dict[str, str]
) -> None:
    """
    One-time migration:
      old:  {entry}.scene.{sid}.(ON|OFF)     or  elegance.scene{sid}(ON|OFF)
      new:  {entry}.scene.{slug(name)}.(ON|OFF)
    """
    reg = er.async_get(hass)
    # Build current sid -> key map from options
    sid_to_key = {str(int(sid)): slugify(name) for sid, name in scenes_map.items()}
    for entity_id in list(reg.entities):
        ent = reg.entities[entity_id]
        if ent.config_entry_id != entry.entry_id or ent.platform != DOMAIN:
            continue

        # Pattern 1: our earlier numeric unique_id
        m = re.fullmatch(rf"{re.escape(entry.entry_id)}\.scene\.(\d+)\.(ON|OFF)", ent.unique_id)
        # Pattern 2: legacy very old "elegance.scene12ON"
        if not m:
            m = re.fullmatch(r"elegance\.scene(\d+)(ON|OFF)", ent.unique_id)

        if not m:
            continue

        sid, suffix = str(int(m.group(1))), m.group(2)
        key = sid_to_key.get(sid)
        if not key:
            # If that sid no longer exists, skip migration (entity will be removed on reload)
            continue
        new_uid = f"{entry.entry_id}.scene.{key}.{suffix}"
        if ent.unique_id != new_uid:
            _LOGGER.debug("Migrating scene unique_id %s -> %s", ent.unique_id, new_uid)
            reg.async_update_entity(ent.entity_id, new_unique_id=new_uid)


class CentraliteScene(Scene):
    """A Centralite scene (ON/OFF) keyed by scene name; number can change in options."""

    _attr_should_poll = False

    def __init__(
        self,
        entry_id: str,
        controller: Centralite,
        scene_key: str,                     # stable key (slug of name)
        friendly_name: str,                 # e.g. "Goodnight-ON"
        sid_lookup: Callable[[str], str | None],
    ) -> None:
        self._entry_id = entry_id
        self.controller = controller
        self._scene_key = scene_key
        self._name = friendly_name
        self._sid_lookup = sid_lookup

        # Suffix for unique_id / action
        m = re.search(r"(ON|OFF)$", self._name, re.IGNORECASE)
        suffix = m.group(1).upper() if m else "NA"

        # UNIQUE ID: NAME-KEYED
        self._attr_unique_id = f"{self._entry_id}.scene.{self._scene_key}.{suffix}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Centralite Controller",
            manufacturer="Centralite",
            model="Elegance / Elite",
        )

    # ---------- HA properties ----------
    @property
    def name(self) -> str:
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sid = self._sid_lookup(self._scene_key)
        return {ATTR_NUMBER: sid} if sid is not None else {}

    # ---------- Scene action ----------
    async def async_activate(self, **_: Any) -> None:
        sid = self._sid_lookup(self._scene_key)
        if not sid:
            _LOGGER.warning("Scene %s has no current id; skipping", self._name)
            return
        await self.hass.async_add_executor_job(
            self.controller.activate_scene, sid, self._name
        )
