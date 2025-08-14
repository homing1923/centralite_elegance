import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .pycentralite import Centralite  # adjust if your controller lives elsewhere

_LOGGER = logging.getLogger(__name__)

DOMAIN = "centralite"
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SCENE, Platform.SWITCH]

class CentraliteHub:
    def __init__(self, hass: HomeAssistant, url: str, include_switches: bool, exclude_names: list[str]):
        self.hass = hass
        self.url = url
        self.include_switches = include_switches
        self.exclude_names = exclude_names
        self.controller: Centralite | None = None

    async def async_setup(self):
        def _start():
            self.controller = Centralite(self.url)
        await self.hass.async_add_executor_job(_start)

    async def async_close(self):
        pass

async def async_setup(hass: HomeAssistant, config: dict):
    # Optional: allow YAML import if you want
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    data = entry.data
    hub = CentraliteHub(
        hass=hass,
        url=data["port"],
        include_switches=data.get("include_switches", False),
        exclude_names=data.get("exclude_names", []),
    )
    await hub.async_setup()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hub: CentraliteHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
