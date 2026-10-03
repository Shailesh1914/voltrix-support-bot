---
article_id: KB-014
title: E-14 External fault input active
category: fault
kb_version: v2
---

# E-14 External fault input active

## Meaning

The external fault input of the VX-200 was activated. By default this is digital input DI3. The input expects a normally closed contact: the circuit between DI3 and +24V must stay closed while everything is healthy. When the circuit opens, the drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-14`.

`E-14` is not a fault of the drive itself. It reports that a device outside the drive asked it to stop.

## Possible causes

- An external protective device has operated, for example a pressure switch, a guard switch or a thermal relay.
- An emergency stop wired to the external fault input was pressed.
- A broken wire or loose connection in the DI3 circuit.
- Nothing is wired to DI3 and the factory link between DI3 and +24V has been removed.
- The function of DI3 was changed in `P-28`.

## Recommended actions

1. Find out which external device is wired to DI3 and why it operated.
2. Correct the cause and reset the external device.
3. Isolate the drive, wait 5 minutes, then check the wiring at DI3 and +24V (tightening torque 0.5 Nm).
4. If no external device is used, refit the link between DI3 and +24V.
5. Press STOP/RESET to clear the fault.

## When to contact support

Contact Voltrix Drives support if `E-14` appears while the circuit between DI3 and +24V is confirmed closed. Have the drive rating, the value of `P-28` and the fault history (`P-55` to `P-59`) ready.
