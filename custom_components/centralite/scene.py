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

from . import DOMAIN
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Centralite scenes from a config entry."""
    hub = hass.data[DOMAIN][entry.entry_id]
    ctrl: Centralite = hub.controller

    scenes = ctrl.scenes()  # dict[str, str] e.g. {"4": "Upstairs Path", ...}
    entities: list[CentraliteScene] = []

    # HA has no OFF for scenes; create ON/OFF variants for each Centralite scene.
    for scene_id, base_name in scenes.items():
        entities.append(CentraliteScene(ctrl, str(scene_id), f"{base_name}-ON"))
        entities.append(CentraliteScene(ctrl, str(scene_id), f"{base_name}-OFF"))

    _LOGGER.debug("centralite.scene: creating %d scene entities", len(entities))
    async_add_entities(entities, False)


class CentraliteScene(Scene):
    """Representation of a single Centralite scene (ON or OFF variant)."""

    _attr_should_poll = False

    def __init__(self, controller: Centralite, scene_id: str, name: str) -> None:
        self.controller = controller
        self._index = str(scene_id)  # controller handles casting internally
        self._name = name

        # Stable unique_id including ON/OFF suffix
        suffix_match = re.search(r"(ON|OFF)$", self._name, re.IGNORECASE)
        suffix = suffix_match.group(1).upper() if suffix_match else "NA"
        self._attr_unique_id = f"elegance.scene.{self._index}.{suffix}"

    # ---------- HA properties ----------
    @property
    def name(self) -> str:
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_NUMBER: self._index}

    # ---------- Actions ----------
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene (Centralite ON or OFF based on name)."""
        _ = kwargs
        await self.hass.async_add_executor_job(
            self.controller.activate_scene, self._index, self._name
        )
