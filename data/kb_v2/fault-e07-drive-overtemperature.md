---
article_id: KB-007
title: E-07 Drive overtemperature (heatsink)
category: fault
kb_version: v2
---

# E-07 Drive overtemperature (heatsink)

## Meaning

The heatsink temperature of the VX-200 reached the trip level of 90 °C. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-07`. The fault cannot be reset until the heatsink has cooled.

## Possible causes

- The air temperature around the drive is too high. The drive gives its full rating from −10 °C to +40 °C and must be derated between 40 °C and 50 °C.
- The heatsink fins or air vents are blocked with dust.
- The cooling fan is not running or is turning slowly.
- Mounting clearances are too small: the drive needs 100 mm of free space above and below and 50 mm on each side.
- The cabinet ventilation or filter is blocked.
- The drive is running continuously close to its rated current in a warm cabinet.

## Recommended actions

1. Leave the drive powered with the motor stopped so the fan can cool the heatsink.
2. Measure the air temperature inside the cabinet near the drive's air inlet.
3. Check that the fan is turning and that air leaves the top of the drive.
4. Clean the heatsink and vents as described in the cleaning article.
5. Check the mounting clearances and the cabinet filters.
6. Press STOP/RESET once the drive has cooled.

## When to contact support

Contact Voltrix Drives support if `E-07` appears with a clean heatsink, a working fan and a cabinet temperature below 40 °C. Have the cabinet temperature, the drive rating, frame size and the fault history (`P-55` to `P-59`) ready.
