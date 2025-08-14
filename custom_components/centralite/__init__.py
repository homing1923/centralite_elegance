"""Allows the Centralite Elegance/Elite/Eligance XL lighting system to be controlled by Home Assistant.

For more details about this component, please refer to the documentation at
"""
import logging
from collections import defaultdict

import voluptuous as vol

from requests.exceptions import RequestException

import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
from homeassistant.helpers import discovery
from homeassistant.const import CONF_PORT

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Config keys
CONF_EXCLUDE_NAMES = "exclude_names"          # List[str], prefix-based ignore
CONF_INCLUDE_SWITCHES = "include_switches"    # bool

# Domain / keys used in hass.data
DOMAIN = "centralite"
CENTRALITE_CONTROLLER = "centralite_system"
CENTRALITE_DEVICES = "centralite_devices"
CENTRALITE_CONFIG = "centralite_config"

# Platforms
PLAT_LIGHT = "light"
PLAT_SCENE = "scene"
PLAT_SWITCH = "switch"

# Entity ID format helper
LJ_ID_FORMAT = "{}_{}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PORT): cv.string,
                vol.Optional(CONF_EXCLUDE_NAMES, default=[]): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, base_config):
    """Set up the Centralite component."""
    from .pycentralite import Centralite

    config = base_config.get(DOMAIN)
    if not config:
        _LOGGER.error("Missing %s config", DOMAIN)
        return False

    url = config.get(CONF_PORT)
    include_switches = config.get(CONF_INCLUDE_SWITCHES, False)

    # Save config so is_ignored() can access it later
    hass.data[CENTRALITE_CONFIG] = {
        CONF_EXCLUDE_NAMES: config.get(CONF_EXCLUDE_NAMES, []),
        CONF_INCLUDE_SWITCHES: include_switches,
    }

    # Create controller
    try:
        hass.data[CENTRALITE_CONTROLLER] = Centralite(url)
    except Exception as e:
        _LOGGER.exception("Failed to initialize Centralite on port %s: %s", url, e)
        return False

    # Kick off platforms
    discovery.load_platform(hass, PLAT_LIGHT, DOMAIN, {}, config)
    discovery.load_platform(hass, PLAT_SCENE, DOMAIN, {}, config)
    if include_switches:
        discovery.load_platform(hass, PLAT_SWITCH, DOMAIN, {}, config)

    # Build the shared device registry for platforms to consume
    centralite_devices = defaultdict(list)

    # LIGHTS
    _LOGGER.debug("Building LIGHT device list")
    try:
        all_load_ids = hass.data[CENTRALITE_CONTROLLER].loads()  # list[int]
    except RequestException:
        _LOGGER.exception("Error talking to Centralite while getting loads()")
        return False
    except Exception:
        _LOGGER.exception("Unexpected error while getting loads()")
        return False

    for load_id in all_load_ids:
        centralite_devices[PLAT_LIGHT].append(load_id)

    # SCENES (dict: id -> name)
    _LOGGER.debug("Building SCENE device list")
    try:
        scenes_dict = hass.data[CENTRALITE_CONTROLLER].scenes()  # dict[str, str]
    except Exception:
        _LOGGER.exception("Unexpected error while getting scenes()")
        return False

    # Store just the scene IDs here; platform can map to names
    for scene_id in scenes_dict.keys():
        centralite_devices[PLAT_SCENE].append(scene_id)

    # SWITCHES (optional)
    if include_switches:
        _LOGGER.debug("Building SWITCH device list")
        try:
            all_switch_ids = hass.data[CENTRALITE_CONTROLLER].button_switches()  # list[int]
        except Exception:
            _LOGGER.exception("Unexpected error while getting button_switches()")
            return False

        for sw_id in all_switch_ids:
            centralite_devices[PLAT_SWITCH].append(sw_id)

    hass.data[CENTRALITE_DEVICES] = centralite_devices

    _LOGGER.debug(
        "Centralite devices ready: lights=%s, scenes=%s, switches=%s",
        len(centralite_devices[PLAT_LIGHT]),
        len(centralite_devices[PLAT_SCENE]),
        len(centralite_devices[PLAT_SWITCH]),
    )

    return True


def is_ignored(hass, name: str) -> bool:
    """Determine if a load, switch, or scene should be ignored based on name prefix."""
    cfg = hass.data.get(CENTRALITE_CONFIG, {})
    for prefix in cfg.get(CONF_EXCLUDE_NAMES, []):
        if name.startswith(prefix):
            return True
    return False


class LJDevice(Entity):
    """Base representation of a Centralite device entity."""

    def __init__(self, lj_device, controller, lj_device_name: str, *args):
        """Initialize the device."""
        _LOGGER.debug("Initializing LJDevice: id=%s name=%s", lj_device, lj_device_name)
        self.lj_device = lj_device          # Usually an int ID or scene ID str
        self.controller = controller
        self._name = lj_device_name
        self.lj_id = LJ_ID_FORMAT.format(slugify(self._name), lj_device)

    def _update_callback(self, _device):
        """Update state (called by controller)."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self) -> bool:
        # Controller pushes events; we don’t poll by default.
        return False

    @property
    def unique_id(self):
        # Helpful for registry
        return self.lj_id
