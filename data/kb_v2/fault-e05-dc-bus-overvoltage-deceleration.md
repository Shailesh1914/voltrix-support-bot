---
article_id: KB-005
title: E-05 DC bus overvoltage during fast deceleration
category: fault
kb_version: v2
---

# E-05 DC bus overvoltage during fast deceleration

## Meaning

The DC bus voltage inside the VX-200 rose above the trip level of 800 V DC while the motor was ramping down. When a motor is slowed faster than it would stop naturally, energy flows from the load back into the drive and raises the DC bus voltage. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-05`.

## Possible causes

- Deceleration time (`P-06`) is too short for the inertia of the load.
- The load has high inertia, such as a fan, flywheel or centrifuge.
- The supply voltage is already near the top of the permitted range (528 V AC), leaving little margin.
- A large, sudden reduction of the frequency reference.

## Recommended actions

1. Increase the deceleration time in `P-06`. The factory default is 10.0 s; increase it in steps until the fault no longer appears.
2. If the application does not need a controlled stop, set the stop mode `P-08` to 1 (coast to stop).
3. Avoid large step changes in the frequency reference.
4. Measure the supply voltage on L1, L2 and L3 and confirm it is within 380–480 V AC ±10 %.
5. Press STOP/RESET to clear the fault.

See the article on setting acceleration and deceleration ramp times for more detail.

## When to contact support

Contact Voltrix Drives support if the application needs a stopping time shorter than the drive can achieve without `E-05`. Have the drive rating, the value of `P-06`, a description of the load and the fault history (`P-55` to `P-59`) ready.
