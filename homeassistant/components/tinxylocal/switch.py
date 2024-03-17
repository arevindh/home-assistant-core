"""Example integration using DataUpdateCoordinator."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import TinxyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config for tinxy local."""
    # assuming API object stored here by __init__.py
    apidata, coordinator = hass.data[DOMAIN][entry.entry_id]

    # _LOGGER.error(apidata)

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()
    switches = []

    entry.data

    status_list = {}

    all_devices = apidata.list_switches()
    result = await apidata.get_states()

    for device in all_devices:
        if device["id"] in result:
            status_list[device["id"]] = device | result[device["id"]]

    for th_device in status_list:
        switches.append(TinxySwitch(coordinator, apidata, th_device))

    async_add_entities(switches)


class TinxySwitch(CoordinatorEntity, SwitchEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, apidata, idx) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx
        self.coordinator = coordinator
        self.api = apidata
        # _LOGGER.warning(
        #     self.coordinator.data[self.idx]["name"]
        #     + " - "
        #     + self.coordinator.data[self.idx]["state"]
        # )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Unique ID property."""
        return self.coordinator.data[self.idx]["id"]

    @property
    def icon(self) -> str:
        """Icon for entity."""
        return self.coordinator.data[self.idx]["icon"]

    @property
    def name(self) -> str:
        """Name of the entity."""
        return self.coordinator.data[self.idx]["name"]

    @property
    def is_on(self) -> bool:
        """If the switch is currently on or off."""
        # self.read_status()
        return self.coordinator.data[self.idx]["state"]
        # return False

    @property
    def available(self) -> bool:
        """Device available status."""
        return True if self.coordinator.data[self.idx]["status"] == 1 else False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer=self.api.manufacturername,
            model=self.light.productname,
            sw_version=self.light.swversion,
            via_device=(DOMAIN, self.api.bridgeid),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # self._is_on = True
        await self.api.set_device_state(
            self.coordinator.data[self.idx]["device_id"],
            str(self.coordinator.data[self.idx]["relay_no"]),
            1,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # self._is_on = False
        await self.api.set_device_state(
            self.coordinator.data[self.idx]["device_id"],
            str(self.coordinator.data[self.idx]["relay_no"]),
            0,
        )
        await self.coordinator.async_request_refresh()
