---
article_id: KB-011
title: E-11 Output phase loss
category: fault
kb_version: v1
---

# E-11 Output phase loss

## Meaning

The VX-200 detected that current is missing in one of the three motor phases at U, V or W. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-11`. The protection is controlled by `P-49` and is enabled by default.

## Possible causes

- A loose or disconnected conductor at the U, V or W terminals.
- A loose link or connection in the motor terminal box.
- A broken conductor in the motor cable.
- An open motor winding.
- A contactor or isolator between the drive and the motor is open or has a faulty contact.
- The motor is very small compared with the drive rating, so the current is too low to detect.

## Recommended actions

1. Isolate the drive and wait 5 minutes before touching any terminal.
2. Inspect and re-tighten the U, V, W terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
3. Check the connections and links in the motor terminal box.
4. With the motor cable disconnected from the drive, measure the resistance between the three motor conductors. The three readings should be nearly equal.
5. Check any switch or contactor between the drive and the motor.
6. Reconnect, restore power and press STOP/RESET.

## When to contact support

Contact Voltrix Drives support if `E-11` appears with a sound motor, cable and connections. Have the drive rating, motor nameplate data, the measured winding resistances and the fault history (`P-55` to `P-59`) ready.
