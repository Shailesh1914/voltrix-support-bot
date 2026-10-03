---
article_id: KB-002
title: E-02 Overcurrent during deceleration
category: fault
kb_version: v2
---

# E-02 Overcurrent during deceleration

## Meaning

The VX-200 detected an output current above its trip level while the motor was ramping down. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-02`.

## Possible causes

- Deceleration time (`P-06`) is too short for the inertia of the load.
- Motor nameplate data in `P-16` to `P-20` is wrong, so the drive controls the motor poorly.
- An intermittent short circuit or insulation fault in the motor cable or motor.
- A mechanical problem that loads the motor suddenly as the speed falls.

## Recommended actions

1. Increase the deceleration time in `P-06`. The factory default is 10.0 s; try doubling the present value.
2. If the application does not need a controlled stop, set the stop mode `P-08` to 1 (coast to stop).
3. Confirm the motor nameplate values in `P-16` to `P-20`, then repeat the auto-tune with `P-21`.
4. Isolate the drive, wait 5 minutes, then inspect the motor cable and the U, V, W terminals.
5. Press STOP/RESET to clear the fault and test again.

If the display shows `E-05` instead of `E-02` when stopping, see the article on DC bus overvoltage during fast deceleration.

## When to contact support

Contact Voltrix Drives support if `E-02` continues with a long deceleration time and correct motor data. Have the drive rating, frame size, the value of `P-06` and the fault history (`P-55` to `P-59`) ready.
