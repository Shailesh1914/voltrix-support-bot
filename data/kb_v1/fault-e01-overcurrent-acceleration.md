---
article_id: KB-001
title: E-01 Overcurrent during acceleration
category: fault
kb_version: v1
---

# E-01 Overcurrent during acceleration

## Meaning

The VX-200 detected an output current above its trip level while the motor was ramping up to the set frequency. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-01`.

## Possible causes

- Acceleration time (`P-05`) is too short for the load.
- The motor shaft or driven machine is jammed or stiff.
- Motor nameplate data in `P-16` to `P-20` is wrong.
- A short circuit or insulation fault in the motor cable or motor.
- The drive was started onto a motor that was still spinning.
- The motor is larger than the drive rating.

## Recommended actions

1. Check that the machine turns freely with the drive isolated.
2. Increase the acceleration time in `P-05`. The factory default is 10.0 s; try doubling the present value.
3. Confirm the motor nameplate values in `P-16` to `P-20`, then repeat the auto-tune with `P-21`.
4. Isolate the drive, wait 5 minutes, then inspect the motor cable and the U, V, W terminals for damage or loose connections.
5. Let the motor stop completely before giving a new run command.
6. Press STOP/RESET to clear the fault and try again.

## When to contact support

Contact Voltrix Drives support if `E-01` appears with the motor cable disconnected from the drive, or if the fault remains after the checks above. Have the drive rating, frame size and the fault history (`P-55` to `P-59`) ready.
