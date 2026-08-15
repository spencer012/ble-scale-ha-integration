"""Constants for the BLE Scale integration."""

from typing import Final

DOMAIN: Final = "ble_scale"
PLATFORMS: Final = ["sensor"]

CONF_ADAPTER: Final = "adapter"
CONF_AGE: Final = "age"
CONF_ATHLETE: Final = "athlete"
CONF_GENDER: Final = "gender"
CONF_HEIGHT: Final = "height"
CONF_HEIGHT_FEET: Final = "height_feet"
CONF_HEIGHT_INCHES: Final = "height_inches"

DEFAULT_AGE: Final = 30
DEFAULT_ATHLETE: Final = False
DEFAULT_GENDER: Final = "male"
DEFAULT_HEIGHT: Final = 175.0

CONNECT_TIMEOUT: Final = 20.0
MEASUREMENT_TIMEOUT: Final = 30.0
RECONNECT_COOLDOWN: Final = 30.0
