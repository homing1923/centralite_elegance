from __future__ import annotations
import re
import voluptuous as vol
from typing import Any
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
from . import DOMAIN

MANUAL_VALUE = "__manual__"

def _parse_exclude(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,\n]+", raw)
    return [p.strip() for p in parts if p.strip()]

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
        # dedupe
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

class CentraliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Step 1: pick a port from live scan, or choose manual."""
        if user_input is not None:
            choice = user_input["port_choice"]
            if choice == MANUAL_VALUE:
                return await self.async_step_manual()
            self._chosen_port = choice
            return await self.async_step_options()

        options = await _scan_serial_ports(self.hass)
        schema = vol.Schema({
            vol.Required("port_choice"): selector({"select": {"mode": "dropdown", "options": options}})
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        """Manual entry for serial path or socket:// URL, with probe."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = (user_input.get("port") or "").strip()
            if not raw:
                errors["base"] = "port_required"
            else:
                # probe immediately
                err = await _probe_port(self.hass, raw)
                if err:
                    errors["base"] = err
                else:
                    self._chosen_port = raw
                    return await self.async_step_options()

        schema = vol.Schema({
            vol.Required("port"): selector({"text": {"type": "text"}}),
        })
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_options(self, user_input: dict[str, Any] | None = None):
        """Step 2: remaining settings; probe selected port before creating entry."""
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
                    data = {
                        "port": chosen,
                        "include_switches": user_input.get("include_switches", False),
                        "exclude_names": _parse_exclude(user_input.get("exclude_names", "")),
                    }
                    return self.async_create_entry(title="Centralite", data=data)

        schema = vol.Schema({
            vol.Required("include_switches", default=False): selector({"boolean": {}}),
            vol.Optional("exclude_names", default=""): selector({"text": {"multiline": True}}),
        })
        description = f"**Selected port:** `{getattr(self, '_chosen_port', '')}`"
        return self.async_show_form(step_id="options", data_schema=schema, errors=errors, description=description)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CentraliteOptionsFlow(config_entry)

class CentraliteOptionsFlow(config_entries.OptionsFlow):
    """Options flow: can rescan and reselect a port; probe before saving."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None):
        base = dict(self.entry.data)
        base.update(self.entry.options or {})

        if user_input is not None:
            if user_input["port_choice"] == MANUAL_VALUE:
                return await self.async_step_manual()
            chosen = user_input["port_choice"]
            err = await _probe_port(self.hass, chosen)
            if err:
                return self.async_show_form(
                    step_id="init",
                    data_schema=await self._schema(base),
                    errors={"base": err},
                )
            return self.async_create_entry(
                title="",
                data={
                    "port": chosen,
                    "include_switches": user_input.get("include_switches", base.get("include_switches", False)),
                    "exclude_names": _parse_exclude(user_input.get("exclude_names", "")),
                },
            )

        return self.async_show_form(step_id="init", data_schema=await self._schema(base))

    async def _schema(self, base):
        options = await _scan_serial_ports(self.hass)
        current = base.get("port")
        if current and all(o["value"] != current for o in options):
            options.insert(0, {"label": f"{current}  (current)", "value": current})
        return vol.Schema({
            vol.Required(
                "port_choice",
                default=current or (options[0]["value"] if options else MANUAL_VALUE),
            ): selector({"select": {"mode": "dropdown", "options": options}}),
            vol.Optional("include_switches", default=base.get("include_switches", False)): selector({"boolean": {}}),
            vol.Optional("exclude_names", default=", ".join(base.get("exclude_names", []))): selector({"text": {"multiline": True}}),
        })

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        base = dict(self.entry.data)
        base.update(self.entry.options or {})
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
                    return self.async_create_entry(
                        title="",
                        data={
                            "port": port,
                            "include_switches": base.get("include_switches", False),
                            "exclude_names": base.get("exclude_names", []),
                        },
                    )
        schema = vol.Schema({
            vol.Required("port", default=base.get("port", "")): selector({"text": {"type": "text"}}),
        })
        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)
