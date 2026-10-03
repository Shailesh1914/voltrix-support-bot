---
article_id: KB-004
title: E-04 DC bus overvoltage at standstill or constant speed
category: fault
kb_version: v2
---

# E-04 DC bus overvoltage at standstill or constant speed

## Meaning

The DC bus voltage inside the VX-200 rose above the trip level of 800 V DC while the drive was stopped or running at a steady frequency. The drive stops its output, the FAULT LED lights and the display flashes `E-04`.

If the overvoltage happens while the motor is slowing down, the drive shows `E-05` instead.

## Possible causes

- The mains supply voltage is too high. The permitted supply is 380–480 V AC ±10 %, so the highest permitted value is 528 V AC.
- Short voltage surges on the supply, for example when large equipment on the same supply is switched.
- The load is driving the motor faster than the set frequency, such as a descending load.
- A poor earth connection.

## Recommended actions

1. Measure the supply voltage on L1, L2 and L3 with a suitable meter and compare it with the permitted range.
2. Note whether the fault coincides with other equipment switching on or off.
3. Check whether the load can drive the motor. If it can, the application needs to be reviewed.
4. Check the earth connection at the PE terminal.
5. Press STOP/RESET to clear the fault once the voltage is back in range.

## When to contact support

Contact Voltrix Drives support if `E-04` appears while the measured supply voltage is inside the permitted range, or if the load regularly drives the motor. Have the measured supply voltage, the drive rating and the fault history (`P-55` to `P-59`) ready.
