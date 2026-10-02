---
article_id: KB-016
title: E-16 Cooling fan failure
category: fault
kb_version: v1
---

# E-16 Cooling fan failure

## Meaning

The VX-200 monitors its cooling fan. `E-16` means a fan is not turning or is turning too slowly. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-16`.

Frame A drives (0.75–2.2 kW) have one fan. Frame B drives (4–7.5 kW) have two fans, and a failure of either one causes `E-16`.

## Possible causes

- The fan is blocked by dust, fluff or a foreign object.
- The fan bearings are worn. The fan is a wearing part and should be replaced every 3 years.
- The fan connector has come loose.
- The fan has failed electrically.

## Recommended actions

1. Isolate the drive and wait 5 minutes.
2. Look into the fan at the bottom of the drive and remove any obstruction.
3. Turn the fan blades gently by hand. They should spin freely and quietly.
4. Check that the fan connector is fully pushed in.
5. If the fan is stiff, noisy or more than 3 years old, replace it as described in the fan replacement article.
6. Restore power and press STOP/RESET. The fan should start when the drive runs.

Do not run the drive without a working fan. It will overheat and trip on `E-07`.

## When to contact support

Contact Voltrix Drives support if `E-16` remains after a new fan has been fitted. Have the drive rating, frame size and the fault history (`P-55` to `P-59`) ready.
