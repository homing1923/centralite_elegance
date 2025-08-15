# custom_components/centralite/__init__.py
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .hub import CentraliteHub

DOMAIN = "centralite"
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SCENE, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)

def _merged(entry: ConfigEntry) -> dict:
    data = dict(entry.data)
    data.update(entry.options or {})
    return data

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # one-time data → options migration so Options UI shows imported values
    moved, data, opts = False, dict(entry.data), dict(entry.options or {})
    for k in ("loads_include", "switches_include", "scenes_map"):
        if k in data and k not in opts:
            opts[k] = data.pop(k); moved = True
    if moved:
        hass.config_entries.async_update_entry(entry, data=data, options=opts)

    hub = CentraliteHub(hass, {**entry.data, **entry.options})
    await hub.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    async def _update_listener(hass, updated_entry):
        await hass.config_entries.async_reload(updated_entry.entry_id)
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hub: CentraliteHub = hass.data[DOMAIN].pop(entry.entry_id, None)
    if hub:
        await hub.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
