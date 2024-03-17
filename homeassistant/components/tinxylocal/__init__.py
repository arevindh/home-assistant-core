"""The Tinxy Local integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_MQTT_PASS, DOMAIN
from .coordinator import TinxyUpdateCoordinator
from .tinxylocal import TinxyLocal, TinxyLocalHostConfiguration

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tinxy from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    web_session = async_get_clientsession(hass)

    host_config = TinxyLocalHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        mqtt_pass=entry.data[CONF_MQTT_PASS],
        host=entry.data[CONF_HOST],
    )

    api = TinxyLocal(host_config=host_config, web_session=web_session)

    coordinator = TinxyUpdateCoordinator(hass, api)

    hass.data[DOMAIN][entry.entry_id] = api, coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
