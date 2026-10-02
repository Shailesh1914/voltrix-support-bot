---
article_id: KB-023
title: Using the keypad and navigating the parameter menu
category: parameters
kb_version: v1
---

# Using the keypad and navigating the parameter menu

## Display and LEDs

The VX-200 has a 4-digit LED display and three status LEDs.

| Item | Meaning |
|---|---|
| Display, steady number | Output frequency in Hz while the motor runs |
| Display, flashing number | Set frequency in Hz while the motor is stopped |
| Display, flashing `E-xx` | A fault code |
| RUN LED | The drive is driving the motor |
| FAULT LED | The drive has tripped on a fault |
| REMOTE LED | The drive is controlled from the terminals, not the keypad |

## Keys

| Key | Function |
|---|---|
| RUN | Starts the motor when the control source is the keypad |
| STOP/RESET | Stops the motor; clears a fault once its cause is removed |
| MENU | Enters the parameter list; steps back without saving |
| ENTER | Opens a parameter; saves a changed value |
| ▲ / ▼ | Changes the set frequency, the parameter number or a value |

## Changing a parameter

1. Press MENU. The display shows a parameter number such as `P-01`.
2. Press ▲ or ▼ to reach the parameter you want. Parameters run from `P-01` to `P-60`.
3. Press ENTER. The display shows the present value.
4. Press ▲ or ▼ to change the value. Hold the key to change it quickly.
5. Press ENTER to save, or MENU to leave without saving.
6. Press MENU again to return to the frequency display.

## Parameter groups

| Range | Group |
|---|---|
| `P-01` to `P-15` | Basic settings |
| `P-16` to `P-25` | Motor data |
| `P-26` to `P-45` | Inputs and outputs |
| `P-46` to `P-60` | Protection and fault history |

Motor data parameters can only be changed while the motor is stopped.
