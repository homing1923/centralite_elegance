import logging
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .hub import CentraliteHub
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
        self.loads_include: list[int] = cfg.get("loads_include") or []
        self.switches_include: list[int] = cfg.get("switches_include") or []
        self.scenes_map: dict[str, str] = cfg.get("scenes_map") or {}
        self.controller: Centralite | None = None

    async def async_setup(self) -> None:  # <-- NO ARG HERE
        def _start():
            self.controller = Centralite(self.url)
        try:
            await self.hass.async_add_executor_job(_start)
        except (serialutil.SerialException, OSError) as e:
            raise ConfigEntryNotReady(f"Serial port not ready: {e}") from e

    async def async_close(self) -> None:
        if self.controller:
            try:
                self.controller.close()
            except Exception:
                pass

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # (optional) trigger import flow if you still support YAML
    return True

def _merged(entry: ConfigEntry) -> dict:
    data = dict(entry.data)
    data.update(entry.options or {})
    return data

async def async_setup_entry(hass, entry):
    # ---- one-time data → options migration ----
    moved, data, opts = False, dict(entry.data), dict(entry.options or {})
    for k in ("loads_include", "switches_include", "scenes_map"):
        if k in data and k not in opts:
            opts[k] = data.pop(k)
            moved = True
    if moved:
        hass.config_entries.async_update_entry(entry, data=data, options=opts)
    # --------------------------------------------

    hub = CentraliteHub(hass, {**entry.data, **entry.options})
    await hub.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    async def _update_listener(hass, updated_entry):
        await hass.config_entries.async_reload(updated_entry.entry_id)
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub: CentraliteHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
