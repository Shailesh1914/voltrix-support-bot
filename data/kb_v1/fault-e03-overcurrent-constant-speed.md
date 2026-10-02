---
article_id: KB-003
title: E-03 Overcurrent at constant speed
category: fault
kb_version: v1
---

# E-03 Overcurrent at constant speed

## Meaning

The VX-200 detected an output current above its trip level while the motor was running at a steady frequency, not ramping up or down. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-03`.

## Possible causes

- A sudden change in load, such as a jam, a blockage or a shock load.
- A short circuit or insulation fault in the motor cable or motor.
- A loose connection at the U, V, W terminals or in the motor terminal box.
- A contactor or isolator between the drive and the motor was switched while the drive was running.
- Motor nameplate data in `P-16` to `P-20` is wrong.

## Recommended actions

1. Check the driven machine for jams, blockages or damaged bearings.
2. Do not open or close any switch between the drive and the motor while the drive is running.
3. Isolate the drive, wait 5 minutes, then check the motor cable and re-tighten the U, V, W terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
4. Confirm the motor nameplate values in `P-16` to `P-20`.
5. Press STOP/RESET to clear the fault and restart.

## When to contact support

Contact Voltrix Drives support if `E-03` appears repeatedly with a free-running machine and a sound motor cable. Have the drive rating, frame size, the output frequency at the time of the trip and the fault history (`P-55` to `P-59`) ready.
