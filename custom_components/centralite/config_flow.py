from __future__ import annotations
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from . import DOMAIN

# 備註：
# 1) exclude_names 用字串，使用者可輸入 "Foo, Bar" 或多行
# 2) 送出時 parse 成 list 存到 entry.data / options

DATA_SCHEMA = vol.Schema({
    vol.Required("port"): str,                  # e.g. "socket://192.168.1.50:4001" 或 "/dev/ttyUSB0"
    vol.Optional("include_switches", default=False): bool,
    vol.Optional("exclude_names", default=""): str,   # <= 這裡改成字串
})

def _parse_exclude(raw: str) -> list[str]:
    if not raw:
        return []
    # 允許逗號或換行分隔
    parts = re.split(r"[,\n]+", raw)
    return [p.strip() for p in parts if p.strip()]

class CentraliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            data = {
                "port": user_input["port"],
                "include_switches": user_input.get("include_switches", False),
                "exclude_names": _parse_exclude(user_input.get("exclude_names", "")),
            }
            return self.async_create_entry(title="Centralite", data=data)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CentraliteOptionsFlow(config_entry)

class CentraliteOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None):
        # 讀目前設定（options 優先，其次 data）
        base = dict(self.entry.data)
        base.update(self.entry.options or {})

        if user_input is not None:
            updated = {
                "include_switches": user_input.get("include_switches", base.get("include_switches", False)),
                "exclude_names": _parse_exclude(user_input.get("exclude_names", "")),
            }
            return self.async_create_entry(title="", data=updated)

        # 將 list 轉回顯示用字串（逗號分隔）
        exclude_str = ", ".join(base.get("exclude_names", []))
        schema = vol.Schema({
            vol.Optional("include_switches", default=base.get("include_switches", False)): bool,
            vol.Optional("exclude_names", default=exclude_str): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
