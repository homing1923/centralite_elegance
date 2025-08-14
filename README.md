# centralite_elegance

Modified for HACS


# Centralite Integration (Custom Config Entry Version)

## Overview
This is a refactored version of the Centralite integration for Home Assistant, migrated from static YAML configuration to a **full Config Entry** (UI-based) setup via HACS.  
It supports:
- Real-time USB port selection
- User-customizable loads, switches, and scenes
- Duplicate prevention when adding new scenes

## ✨ Key Changes

### 1. Migration to Config Entries
- Removed legacy YAML `setup()` and replaced with `__init__.py` using Home Assistant’s Config Entry API.
- Now fully configurable from the Home Assistant UI.
- Single `CentraliteHub` instance per config entry, reused across all platforms (`light`, `scene`, `switch`).

### 2. USB Port Selection in UI
- Config flow dynamically lists available serial/USB ports.
- Users can pick the port from a dropdown instead of editing YAML.

### 3. User-Customizable Device Lists
- Added `loads_include`, `switches_include`, and `scenes_map` stored in config entry options.
- Editable via the **Options** flow after setup.
- Lights and switches are filtered based on user selection.

### 4. Scene Management Enhancements
- Scenes editable in UI: `scene_id: Scene Name` format.
- Duplicate scene detection:
  - Warns if a number is already assigned.
  - Suggests next available free number.
- Stable `unique_id` for entities to prevent duplication.

### 5. Updated Platform Implementations
- **`light.py`**
  - Brightness scaling between Centralite’s 0–99 and HA’s 0–255.
  - Real-time push updates from controller.
  - Stable unique IDs using config entry `entry_id`.
- **`scene.py`**
  - ON/OFF entities per scene.
  - Migrates old unique IDs automatically.
- **`switch.py`**
  - Optional switch entities.
  - Push updates for button press/release events.
  - Stable unique IDs using config entry `entry_id`.

### 6. Persistent Controller Instance
- Prevents multiple `Centralite` instances from being created when reloading or adding devices.
- Shared controller reference via `hass.data[DOMAIN][entry_id]`.

---

## 📦 Installation
1. Copy this repository into your HACS `custom_components/centralite` folder.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and select **Centralite**.
4. Follow the UI prompts to select USB port, loads, switches, and scenes.

---

## 🛠 Notes
- Edit scenes in the integration’s **Options** menu.
- Scene IDs must be unique; the UI warns and suggests replacements.
- Adding/removing devices will not create duplicate entities thanks to stable IDs.
