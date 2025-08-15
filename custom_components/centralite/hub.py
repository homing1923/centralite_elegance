# custom_components/centralite/hub.py
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryNotReady
from serial import serialutil
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

class CentraliteHub:
    """Small wrapper that owns the Centralite controller and user-selected config."""

    def __init__(self, hass: HomeAssistant, cfg: dict):
        self.hass = hass
        self.url = cfg["port"]
        self.include_switches: bool = cfg.get("include_switches", False)

        # Editable via Options UI
        self.loads_include: list[int] = cfg.get("loads_include") or []
        self.switches_include: list[int] = cfg.get("switches_include") or []
        self.scenes_map: dict[str, str] = cfg.get("scenes_map") or {}

        self.controller: Centralite | None = None

    async def async_setup(self) -> None:
        def _start():
            return Centralite(self.url)
        try:
            self.controller = await self.hass.async_add_executor_job(_start)
        except (serialutil.SerialException, OSError) as e:
            raise ConfigEntryNotReady(f"Serial port not ready: {e}") from e

    async def async_close(self) -> None:
        try:
            if self.controller:
                self.controller.close()
        except Exception:
            pass
