# BLE Scale for Home Assistant

A small, local-only Home Assistant custom integration for connectable BLE body
scales. It reads a completed measurement and exposes the result as Home
Assistant sensors. No cloud account, MQTT broker, or vendor application is
required.

Supported protocols:

- 1byone / Eufy C1, P1, A1 (`T9146`, `T9147`, `T9120`, `Health Scale`)
- Newer `1byone scale` protocol
- Inlife (`000FatScale01`, `000FatScale02`, `042FatScale01`)
- Hesley / YunChen
- Hoffen BS-8107
- Digoo / Mengii
- Excelvan CF369 / Electronic Scale
- Exingtech Y1 / vscale
- Senssun Fat Scale

## Installation

### HACS

Add this repository as a custom integration repository in HACS, install **BLE
Scale**, and restart Home Assistant.

### Manual

Copy `custom_components/ble_scale` into the `custom_components` directory in
your Home Assistant configuration, then restart Home Assistant.

## Setup

Wake the scale so Home Assistant can see its advertisement, then open
**Settings → Devices & services**. Accept the discovered BLE Scale, or choose
**Add integration → BLE Scale** and select a visible device. Enter the height,
age, sex, and athlete setting for the person who uses that scale.

One config entry represents one physical scale and one user profile. The
profile can be changed later from the integration's **Configure** dialog.

## Bluetooth proxies

ESPHome Bluetooth proxies are supported through Home Assistant's Bluetooth
stack. Because these scales use GATT connections, the proxy must support active
connections:

```yaml
bluetooth_proxy:
  active: true
```

Home Assistant automatically chooses a local adapter or the nearest eligible
proxy. Do not run a separate scanner alongside Home Assistant.

## Sensors

The integration creates weight, BMI, body fat, water, muscle mass, bone mass,
visceral fat, physique rating, BMR, metabolic age, impedance, and last
measurement sensors. The last completed measurement is restored after a Home
Assistant restart.

Body-composition values reported by a scale are preferred. Missing values are
estimated from the configured profile using the formulas ported from
`ble-scale-sync`. Consumer BIA measurements and formula-derived values are
estimates and are not medical measurements.

## License and attribution

Protocol parsing and body-composition calculations are ported and modified from
[`ble-scale-sync`](https://github.com/KristianP26/ble-scale-sync), copyright
Kristián Partl, licensed under GPL-3.0. This integration is released under the
same license.
