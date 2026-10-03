---
article_id: KB-027
title: "Choosing the control source: keypad, terminals or analog reference"
category: parameters
kb_version: v2
---

# Choosing the control source: keypad, terminals or analog reference

Two parameters decide where the VX-200 takes its commands from. One sets the source of the start and stop command, the other sets the source of the speed reference.

## Start and stop command: `P-01`

| Value | Source |
|---|---|
| 0 (factory default) | Keypad: RUN and STOP/RESET keys |
| 1 | Terminals: digital inputs DI1 (run forward) and DI2 (run reverse) |

When `P-01` is 1, the REMOTE LED is on and the RUN key has no effect. The STOP/RESET key still stops the motor.

## Speed reference: `P-02`

| Value | Source |
|---|---|
| 0 (factory default) | Keypad: ▲ and ▼ keys |
| 1 | Analog input AI1, 0–10 V |
| 2 | Analog input AI2, 4–20 mA |

The analog reference is scaled between the minimum frequency `P-03` and the maximum frequency `P-04`.

## Common combinations

| Use | `P-01` | `P-02` |
|---|---|---|
| Local control at the drive | 0 | 0 |
| Remote start/stop with a speed potentiometer | 1 | 1 |
| Remote start/stop with a 4–20 mA speed signal | 1 | 2 |
| Remote start/stop at a fixed speed set on the keypad | 1 | 0 |

## Points to note

- Stop the motor before changing `P-01` or `P-02`.
- With `P-01` at 1, the motor starts as soon as DI1 or DI2 is connected to +24V. Make sure the machine is safe before changing the setting.
- If the 4–20 mA signal on AI2 is lost, the reference falls to the minimum frequency.
- See the control terminal wiring article for the terminal connections.
