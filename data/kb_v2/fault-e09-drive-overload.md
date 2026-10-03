---
article_id: KB-009
title: E-09 Drive overload
category: fault
kb_version: v2
---

# E-09 Drive overload

## Meaning

The VX-200 can deliver 150 % of its rated output current for 60 seconds. `E-09` means the output current stayed above the rated current for longer than the drive allows. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-09`.

## Possible causes

- The load needs more current than the drive is rated for.
- The motor is larger than the drive rating.
- Acceleration time (`P-05`) is very short, so the drive stays in overload for much of each start.
- Frequent starts and stops with a heavy load.
- The driven machine is stiff or partly jammed.
- Motor nameplate data in `P-16` to `P-20` is wrong.

## Recommended actions

1. Wait a few minutes before restarting so the drive can recover.
2. Compare the drive rating label with the motor nameplate power and current.
3. Check the machine for mechanical overload.
4. Increase the acceleration time in `P-05`.
5. Reduce the number of starts per hour if the process allows.
6. Confirm the motor data in `P-16` to `P-20` and repeat the auto-tune with `P-21`.
7. Press STOP/RESET to clear the fault.

Do not confuse `E-09` with `E-08`: `E-09` protects the drive, `E-08` protects the motor.

## When to contact support

Contact Voltrix Drives support if `E-09` appears with a correctly matched motor and a free-running machine. Have the drive rating, frame size, motor nameplate data and the fault history (`P-55` to `P-59`) ready.
