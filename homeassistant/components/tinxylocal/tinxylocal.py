"""Tinxy Local."""
import base64
from dataclasses import dataclass
import time

from tinxy import tinxy


class TinxyLocalException(Exception):
    """Tinxy Exception."""

    def __init__(self, message="Failed") -> None:
        """Init."""
        self.message = message
        super().__init__(self.message)


class TinxyAuthenticationException(TinxyLocalException):
    """Tinxy authentication exception."""


@dataclass
class TinxyLocalHostConfiguration:
    """Tinxy host configuration."""

    api_token: str
    mqtt_pass: str
    host: str

    def __post_init__(self):
        """Post init."""
        if self.api_token is None or self.mqtt_password is None:
            raise TinxyAuthenticationException(
                message="No API token / Mattermost password to the was provided."
            )
        if self.api_token is None and self.host is None:
            raise TinxyLocalException(
                message="No  url, api token to the Tinxy server was provided."
            )


class TinxyLocal:
    """Main class for tinxy."""

    DOMAIN = "tinxy"
    CONF_MQTT_PASS = "mqtt_pass"
    CONF_API_TOKEN = "api_token"
    CONF_HOST = "host"

    def __init__(self, host_config: TinxyLocalHostConfiguration, web_session) -> None:
        """Init."""
        self.host_config = host_config
        self.web_session = web_session

    def digit_key_value_pairs(self, text: str) -> dict:
        """Convert a string of digits into a dictionary with key-value pairs for each digit."""
        result = {}
        for i, digit in enumerate(text):
            result[i] = int(digit)  # Convert digit to integer
        return result

    async def get_states(self) -> dict | bool:
        """Get current states of device."""
        result = await self.api_request("", None, "GET")
        if result is not False:
            digits = self.digit_key_value_pairs(result.state)
            return digits
        return False

    async def turn_on(self, realy_number: int, state: dict) -> dict:
        """Turn on device."""

    async def api_request(self, path: str, payload: dict, method="GET") -> dict:
        """Tinxy api requests requests."""

        password = await self.generate_password(self.host_config[self.CONF_MQTT_PASS])

        # Define the request headers.
        headers = {"Content-Type": "application/json"}

        if method == "POST":
            payload["password"] = password

        # Make the POST request to toggle the device state.
        async with self.web_session.request(
            method=method,
            url=f"{self.host_config.host}/{path}",  # Using f-string for clarity
            json=payload,
            headers=headers,
        ) as resp:
            # Check if the request was successful (HTTP status code 200).
            if resp.status == 200:
                # Return the JSON response directly.
                return await resp.json(content_type=None)
            else:
                # Log or handle unsuccessful request appropriately.
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
