---
article_id: KB-012
title: E-12 Earth (ground) fault
category: fault
kb_version: v1
---

# E-12 Earth (ground) fault

## Meaning

The VX-200 detected current flowing from the motor output to earth. The drive stops its output immediately, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-12`.

Treat this fault seriously. Do not reset it repeatedly without finding the cause.

## Possible causes

- Damaged insulation in the motor cable.
- Insulation failure in the motor windings.
- Moisture or dirt in the motor terminal box.
- A conductor strand touching the cabinet or the cable screen at the U, V, W terminals.
- A very long motor cable. The maximum motor cable length is 50 m.

## Recommended actions

1. Isolate the drive and wait 5 minutes before touching any terminal.
2. Disconnect the motor cable from the U, V, W terminals of the drive.
3. Carry out an insulation resistance test on the motor and motor cable to earth. Never apply an insulation tester to the drive terminals; it can damage the drive.
4. Inspect the motor terminal box for moisture, dirt and loose strands.
5. Inspect the cable along its length for crushing or abrasion.
6. Repair or replace the faulty part, reconnect, restore power and press STOP/RESET.

To find out whether the drive or the motor circuit is at fault, power the drive with the motor cable disconnected and give a run command.

## When to contact support

Contact Voltrix Drives support if `E-12` appears with the motor cable disconnected from the drive. Have the drive rating, frame size, insulation test results and the fault history (`P-55` to `P-59`) ready.
