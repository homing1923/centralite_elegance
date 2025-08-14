# custom_components/centralite/config_flow.py
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from . import DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Required("port"): str,                 # e.g. "socket://1.2.3.4:4001" or "/dev/ttyUSB0"
    vol.Optional("include_switches", default=False): bool,
    vol.Optional("exclude_names", default=[]): [str],
})

class CentraliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            # (optional) validate the port string here by trying a quick open
            return self.async_create_entry(title="Centralite", data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CentraliteOptionsFlow(config_entry)

class CentraliteOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.entry.options or self.entry.data
        schema = vol.Schema({
            vol.Optional("include_switches", default=data.get("include_switches", False)): bool,
            vol.Optional("exclude_names", default=data.get("exclude_names", [])): [str],
        })
        return self.async_show_form(step_id="init", data_schema=schema)
