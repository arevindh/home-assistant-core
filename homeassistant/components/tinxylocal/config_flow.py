"""Config flow for Tinxy Local integration."""
from __future__ import annotations

import base64
import logging
import time
from typing import Any

from tinxy import tinxy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACTION,
    CONF_ADD_DEVICE,
    CONF_DEVICE_ID,
    CONF_EDIT_DEVICE,
    CONF_MQTT_PASS,
    CONF_SETUP_CLOUD,
    DOMAIN,
    TINXY_BACKEND,
)
from .tinxycloud import TinxyCloud, TinxyHostConfiguration

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

STEP_DEVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MQTT_PASS): str,
        vol.Required(CONF_DEVICE_ID): str,
    }
)

CONF_ACTIONS = {
    CONF_ADD_DEVICE: "Add a new device",
    CONF_EDIT_DEVICE: "Edit a device",
    CONF_SETUP_CLOUD: "Reconfigure Cloud API account",
}


class TinxyLocalHub:
    """Placeholder class to make tests pass."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = f"http://{host}"

    async def authenticate(self, api_key: str, web_session) -> bool:
        """Test if we can authenticate with the host."""
        host_config = TinxyHostConfiguration(api_token=api_key, api_url=TINXY_BACKEND)
        api = TinxyCloud(host_config=host_config, web_session=web_session)
        await api.sync_devices()
        return True

    async def tinxy_toggle(
        self, mqttpass: str, relay_number: int, action: int, web_session
    ) -> bool:
        """Toggle Tinxy device state.

        Args:
            mqttpass (str): API key for authentication.
            relay_number (int): The relay number to toggle.
            action (int): The action to perform (0 for off, 1 for on).
            web_session: The web session for making HTTP requests.

        Returns:
            bool: True if the operation was successful, False otherwise.

        """
        try:
            # Generate a password using the provided API key.
            password = await self.generate_password(mqttpass)

            # Define the request headers.
            headers = {"Content-Type": "application/json"}

            # Ensure action is either 1 or 0, and convert to string for the payload.
            if action not in [0, 1]:
                _LOGGER.error("Action must be 0 (off) or 1 (on) ", exc_info=action)
                return False
            action_str = str(action)

            # Construct the payload with dynamic values.
            payload = {
                "password": password,
                "relayNumber": relay_number,
                "action": action_str,  # Ensuring action is passed as a string
            }

            _LOGGER.error(payload)

            # Make the POST request to toggle the device state.
            async with web_session.request(
                method="POST",
                url=f"{self.host}/toggle",  # Using f-string for clarity
                json=payload,
                headers=headers,
            ) as resp:
                # Check if the request was successful (HTTP status code 200).
                if resp.status == 200:
                    # Return the JSON response directly.
                    return await resp.json(content_type=None)
                else:
                    # Log or handle unsuccessful request appropriately.
                    _LOGGER.error(
                        "Failed to toggle device: HTTP ", exc_info=resp.status
                    )
                    _LOGGER.error(resp.status)
                    return False
        except Exception as e:
            # Log or handle any exceptions raised during the request.
            _LOGGER.error(e)
            return False

    async def generate_password(self, mqttpass: str) -> str:
        """Generate Tinxy Password."""
        time_string = str(int(time.time()))
        en_arg1 = tinxy.strToLongs(time_string.encode("utf-8").decode())
        en_mqttpass = tinxy.strToLongs(mqttpass.encode("utf-8").decode())
        ed = tinxy.encodes(en_arg1, en_mqttpass)
        ciphertext = tinxy.longsToStr(ed)
        cipherutf2 = ciphertext.encode("latin-1")
        cipherbase64 = base64.b64encode(cipherutf2)
        return base64.b64decode(cipherbase64).hex()


async def read_devices(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Read Device List."""
    web_session = async_get_clientsession(hass)
    _LOGGER.info(data)

    host_config = TinxyHostConfiguration(
        api_token=data[CONF_API_KEY], api_url=TINXY_BACKEND
    )
    api = TinxyCloud(host_config=host_config, web_session=web_session)

    device_list = await api.get_device_list()

    # _LOGGER.info(device_list)

    return device_list


async def toggle_device(
    hass: HomeAssistant, host: str, mqttpass: str, relay_number: int, action: int
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    web_session = async_get_clientsession(hass)
    hub = TinxyLocalHub(host)

    data = await hub.tinxy_toggle(
        mqttpass=mqttpass,
        relay_number=relay_number,
        action=action,
        web_session=web_session,
    )

    return data


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    web_session = async_get_clientsession(hass)
    hub = TinxyLocalHub(TINXY_BACKEND)

    if not await hub.authenticate(data[CONF_API_KEY], web_session):
        raise InvalidAuth

    return {"title": "Tinxy.in"}


def find_device_by_id(devicelist, target_id):
    """Find."""
    for device in devicelist:
        if device["_id"] == target_id:
            return device
    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tinxy Local."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize local tinxy options flow."""
        # self.config_entry = config_entry
        self.selected_device = None
        self.mqtt_pass = None
        self.cloud_devices = {}
        self.host = None
        self.api_token = None
        self.device_uuid = None

        self.discovered_devices = {}
        self.editing_device = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # After Picking device
        if user_input is not None and CONF_DEVICE_ID in user_input:
            try:
                _LOGGER.error(user_input[CONF_DEVICE_ID])

                device = None

                device = find_device_by_id(
                    self.cloud_devices, user_input[CONF_DEVICE_ID]
                )

                # _LOGGER.error(device, exc_info=device)

                self.mqtt_pass = device["mqttPassword"]
                self.device_uuid = device["uuidRef"]["uuid"]
                self.host = user_input[CONF_HOST]

                _LOGGER.error(
                    {self.mqtt_pass, self.device_uuid, self.host}, exc_info=device
                )

                data = await toggle_device(self.hass, self.host, self.mqtt_pass, 1, 0)

                return self.async_create_entry(
                    title=self.device_uuid,
                    data={
                        CONF_HOST: self.host,
                        CONF_MQTT_PASS: self.mqtt_pass,
                        CONF_DEVICE_ID: self.device_uuid,
                        CONF_API_KEY: self.api_token,
                    },
                )

                _LOGGER.error(data)

                # await validate_input(self.hass, self.api_token)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # After submitting api key
        elif user_input is not None and CONF_API_KEY in user_input:
            try:
                await validate_input(self.hass, user_input)

                # Save after validated
                self.api_token = user_input[CONF_API_KEY]

                self.cloud_devices = await read_devices(self.hass, user_input)

                device_schema_data = {
                    item["_id"]: "{} ({})".format(item["name"], item["uuidRef"]["uuid"])
                    for item in self.cloud_devices
                    if "mqttPassword" in item
                    and "uuidRef" in item
                    and "uuid" in item["uuidRef"]
                }

                device_schema = vol.Schema(
                    {
                        vol.Required("device_id", default=None): vol.In(
                            device_schema_data
                        ),
                        vol.Required(CONF_HOST): str,
                    }
                )

                return self.async_show_form(
                    step_id="user",
                    data_schema=device_schema,
                    description_placeholders=self.cloud_devices,
                    errors=errors,
                )

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
