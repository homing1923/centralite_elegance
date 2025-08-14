# custom_components/centralite/config_flow.py
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from . import DOMAIN

MANUAL_VALUE = "__manual__"


# ------------------------- helpers & parsers ------------------------- #
def _parse_exclude(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _parse_int_list(raw: str) -> list[int]:
    if not raw:
        return []
    items = re.split(r"[,\s]+", raw)
    out: list[int] = []
    for it in items:
        if not it:
            continue
        try:
            v = int(it)
            if v <= 0:
                continue
            if v not in out:
                out.append(v)
        except ValueError:
            raise vol.Invalid(f"Invalid number: {it}")
    return out


def _parse_scenes(raw: str) -> dict[str, str]:
    """
    Lines like:
      10: Landscape Lights
      12 = Goodnight
    """
    result: dict[str, str] = {}
    if not raw:
        return result
    for ln in raw.splitlines():
        if not ln.strip():
            continue
        m = re.match(r"\s*(\d+)\s*[:=]\s*(.+?)\s*$", ln)
        if not m:
            raise vol.Invalid(f"Invalid scene line: {ln!r} (use: ID: Name)")
        sid, name = m.group(1), m.group(2)
        result[sid] = name
    return result


async def _scan_serial_ports(hass) -> list[dict[str, str]]:
    """Return selector options: [{'label': '...', 'value': '...'}, ...]."""
    def _scan():
        from serial.tools import list_ports  # pyserial
        entries = []
        for p in list_ports.comports():
            dev = p.device
            label = dev
            if p.description and p.description not in label:
                label = f"{label}  ({p.description})"
            entries.append({"label": label, "value": dev})
        # de-dupe
        seen, uniq = set(), []
        for e in entries:
            if e["value"] in seen:
                continue
            seen.add(e["value"])
            uniq.append(e)
        return uniq

    options = await hass.async_add_executor_job(_scan)
    options.append({"label": "Enter manually…", "value": MANUAL_VALUE})
    return options


async def _probe_port(hass, port: str) -> str | None:
    """Try opening the port briefly. Return error key or None if OK."""
    def _try():
        import serial
        from serial import serialutil
        try:
            s = serial.serial_for_url(port, baudrate=19200, timeout=1)
            try:
                s.close()
            except Exception:
                pass
            return None
        except serialutil.SerialException as e:
            msg = str(e)
            if "No such file" in msg or "could not open port" in msg:
                return "port_not_found"
            return "cannot_connect"
        except Exception:
            return "cannot_connect"

    return await hass.async_add_executor_job(_try)


# ------------------------------- Config Flow ------------------------------- #
class CentraliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    # Step 1: choose port (live scan) or manual
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            choice = user_input["port_choice"]
            if choice == MANUAL_VALUE:
                return await self.async_step_manual()
            self._chosen_port = choice
            return await self.async_step_options_basic()

        options = await _scan_serial_ports(self.hass)
        schema = vol.Schema({
            vol.Required("port_choice"): selector({"select": {"mode": "dropdown", "options": options}})
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    # Step 1b: enter manual port (and probe)
    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = (user_input.get("port") or "").strip()
            if not raw:
                errors["base"] = "port_required"
            else:
                err = await _probe_port(self.hass, raw)
                if err:
                    errors["base"] = err
                else:
                    self._chosen_port = raw
                    return await self.async_step_options_basic()

        schema = vol.Schema({
            vol.Required("port"): selector({"text": {"type": "text"}}),
        })
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    # Step 2: basic options (include_switches / exclude_names), probe chosen port again
    async def async_step_options_basic(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            chosen = getattr(self, "_chosen_port", "").strip()
            if not chosen:
                errors["base"] = "port_required"
            else:
                err = await _probe_port(self.hass, chosen)
                if err:
                    errors["base"] = err
                else:
                    self._base = {
                        "port": chosen,
                        "include_switches": user_input.get("include_switches", False),
                        "exclude_names": _parse_exclude(user_input.get("exclude_names", "")),
                    }
                    return await self.async_step_devices()

        schema = vol.Schema({
            vol.Required("include_switches", default=False): selector({"boolean": {}}),
            vol.Optional("exclude_names", default=""): selector({"text": {"multiline": True}}),
        })
        return self.async_show_form(
            step_id="options_basic",
            data_schema=schema,
            errors=errors,
            description_placeholders={"port": getattr(self, "_chosen_port", "")},
        )

    # Step 3: choose loads & switches
    async def async_step_devices(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                loads = _parse_int_list(user_input.get("loads_include", ""))
                switches = _parse_int_list(user_input.get("switches_include", ""))
            except vol.Invalid:
                errors["base"] = "invalid_devices"
            else:
                self._devices = {"loads_include": loads, "switches_include": switches}
                return await self.async_step_scenes()

        schema = vol.Schema({
            vol.Optional("loads_include", default=""): selector({"text": {"multiline": True}}),
            vol.Optional("switches_include", default=""): selector({"text": {"multiline": True}}),
        })
        return self.async_show_form(step_id="devices", data_schema=schema, errors=errors)

    # Step 4: scenes map
    async def async_step_scenes(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                scenes = _parse_scenes(user_input.get("scenes_map", ""))
            except vol.Invalid:
                errors["base"] = "invalid_scenes"
            else:
                data = {
                    **getattr(self, "_base", {}),
                    **getattr(self, "_devices", {}),
                    "scenes_map": scenes,
                }
                return self.async_create_entry(title="Centralite", data=data)

        schema = vol.Schema({
            vol.Optional("scenes_map", default=""): selector({"text": {"multiline": True}})
        })
        return self.async_show_form(step_id="scenes", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CentraliteOptionsFlow(config_entry)


# ------------------------------- Options Flow ------------------------------- #
class CentraliteOptionsFlow(config_entries.OptionsFlow):
    """Edit port + options + devices + scenes after setup."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    # Init: choose (or re-choose) port and basic options
    async def async_step_init(self, user_input: dict | None = None):
        base = {**self.entry.data, **(self.entry.options or {})}
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input["port_choice"] == MANUAL_VALUE:
                return await self.async_step_manual()
            chosen = user_input["port_choice"]
            err = await _probe_port(self.hass, chosen)
            if err:
                errors["base"] = err
            else:
                self._base = {
                    "port": chosen,
                    "include_switches": user_input.get("include_switches", base.get("include_switches", False)),
                    "exclude_names": _parse_exclude(user_input.get("exclude_names", ",".join(base.get("exclude_names", [])))),
                }
                return await self.async_step_devices()

        options = await _scan_serial_ports(self.hass)
        current = base.get("port")
        if current and all(o["value"] != current for o in options):
            options.insert(0, {"label": f"{current}  (current)", "value": current})

        schema = vol.Schema({
            vol.Required(
                "port_choice",
                default=current or (options[0]["value"] if options else MANUAL_VALUE),
            ): selector({"select": {"mode": "dropdown", "options": options}}),
            vol.Optional("include_switches", default=base.get("include_switches", False)): selector({"boolean": {}}),
            vol.Optional("exclude_names", default=", ".join(base.get("exclude_names", []))): selector({"text": {"multiline": True}}),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    # Manual port entry in options flow
    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        base = {**self.entry.data, **(self.entry.options or {})}
        errors: dict[str, str] = {}
        if user_input is not None:
            port = (user_input.get("port") or "").strip()
            if not port:
                errors["base"] = "port_required"
            else:
                err = await _probe_port(self.hass, port)
                if err:
                    errors["base"] = err
                else:
                    self._base = {
                        "port": port,
                        "include_switches": base.get("include_switches", False),
                        "exclude_names": base.get("exclude_names", []),
                    }
                    return await self.async_step_devices()

        schema = vol.Schema({
            vol.Required("port", default=base.get("port", "")): selector({"text": {"type": "text"}}),
        })
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    # Devices step in options flow
    async def async_step_devices(self, user_input=None):
        base = {**self.entry.data, **(self.entry.options or {})}
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                loads = _parse_int_list(user_input.get("loads_include", ""))
                switches = _parse_int_list(user_input.get("switches_include", ""))
            except vol.Invalid:
                errors["base"] = "invalid_devices"
            else:
                self._devices = {"loads_include": loads, "switches_include": switches}
                return await self.async_step_scenes()

        schema = vol.Schema({
            vol.Optional("loads_include", default=", ".join(map(str, base.get("loads_include", [])))): selector({"text": {"multiline": True}}),
            vol.Optional("switches_include", default=", ".join(map(str, base.get("switches_include", [])))): selector({"text": {"multiline": True}}),
        })
        return self.async_show_form(step_id="devices", data_schema=schema, errors=errors)

    # Scenes step in options flow
    async def async_step_scenes(self, user_input=None):
        base = {**self.entry.data, **(self.entry.options or {})}
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                scenes = _parse_scenes(user_input.get("scenes_map", ""))
            except vol.Invalid:
                errors["base"] = "invalid_scenes"
            else:
                # Save options; carry forward previously collected _base/_devices
                final = {
                    **(self.entry.options or {}),
                    **getattr(self, "_base", {}),
                    **getattr(self, "_devices", {}),
                    "scenes_map": scenes,
                }
                return self.async_create_entry(title="", data=final)

        scenes_lines = "\n".join(f"{k}: {v}" for k, v in base.get("scenes_map", {}).items())
        schema = vol.Schema({
            vol.Optional("scenes_map", default=scenes_lines): selector({"text": {"multiline": True}})
        })
        return self.async_show_form(step_id="scenes", data_schema=schema, errors=errors)
