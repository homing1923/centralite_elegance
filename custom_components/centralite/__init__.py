# custom_components/centralite/__init__.py
import logging
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from serial import serialutil
from .pycentralite import Centralite

_LOGGER = logging.getLogger(__name__)

DOMAIN = "centralite"
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SCENE, Platform.SWITCH]


class CentraliteHub:
    def __init__(self, hass: HomeAssistant, cfg: dict):
        self.hass = hass
        self.url = cfg["port"]
        self.include_switches = cfg.get("include_switches", False)
        # user-customizable (from options)
        self.loads_include: list[int] = cfg.get("loads_include") or []
        self.switches_include: list[int] = cfg.get("switches_include") or []
        self.scenes_map: dict[str, str] = cfg.get("scenes_map") or {}
        self.controller: Centralite | None = None

    async def async_setup(self):
        def _start():
            self.controller = Centralite(self.url)

        try:
            await self.hass.async_add_executor_job(_start)
        except (serialutil.SerialException, OSError) as e:
            raise ConfigEntryNotReady(f"Serial port not ready: {e}") from e

    async def async_close(self):
        if self.controller:
            self.controller.close()


async def async_setup(hass: HomeAssistant, config: dict):
    return True


def _merged(entry: ConfigEntry) -> dict:
    data = dict(entry.data)
    data.update(entry.options or {})
    return data


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hub = CentraliteHub(hass, _merged(entry))
    await hub.async_setup()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hub

    # ⬇️ add this
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Unload entities first, then close the serial hub
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub: CentraliteHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.async_close()
    return unload_ok


async def _reload_on_update(hass: HomeAssistant, entry: ConfigEntry):
    """Called when options are updated: fully reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
