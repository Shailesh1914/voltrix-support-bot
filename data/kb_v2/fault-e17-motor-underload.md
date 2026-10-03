---
article_id: KB-037
title: E-17 Motor underload (loss of load)
category: fault
kb_version: v2
---

# E-17 Motor underload (loss of load)

## Meaning

The VX-200 detected that the motor current stayed below the underload level for longer than the set delay while the motor was running. This usually means the motor has lost its load. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-17`.

This fault can only appear when underload detection is enabled with `P-50` set to 1. The factory default is 0 (disabled).

## Underload parameters

| Parameter | Function | Range | Factory default |
|---|---|---|---|
| `P-50` | Underload detection: 0 = disabled, 1 = enabled | 0–1 | 0 |
| `P-51` | Underload level, in % of the motor rated current `P-17` | 10–80 % | 30 % |
| `P-52` | Underload delay | 1–120 s | 10 s |

Underload is only checked while the output frequency is above 10 Hz, so it does not trip during a normal start.

## Possible causes

- A broken drive belt or coupling between the motor and the machine.
- A pump running dry, with a closed valve or a blocked suction.
- A conveyor or fan running with no material or no air flow.
- `P-51` is set too high for the normal light-load current of the machine.
- Motor rated current in `P-17` is set higher than the motor nameplate value.

## Recommended actions

1. Isolate the drive, wait 5 minutes, then check the belt, coupling and driven machine.
2. For a pump, check that valves are open and that the suction is not blocked or dry.
3. Compare `P-17` with the current on the motor nameplate and correct it if needed.
4. If the machine was working normally, note the motor current at the lightest normal load and set `P-51` below it.
5. If short periods of light load are normal for the process, increase the delay in `P-52`.
6. Press STOP/RESET to clear the fault.

## When to contact support

Contact Voltrix Drives support if `E-17` appears while the machine is loaded normally and `P-17` matches the nameplate. Have the drive rating, the values of `P-17`, `P-50`, `P-51` and `P-52`, and the fault history (`P-55` to `P-59`) ready.
