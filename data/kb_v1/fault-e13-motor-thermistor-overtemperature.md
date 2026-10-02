---
article_id: KB-013
title: E-13 Motor thermistor overtemperature
category: fault
kb_version: v1
---

# E-13 Motor thermistor overtemperature

## Meaning

A thermistor fitted inside the motor windings and wired to the TH1 and TH2 terminals of the VX-200 reported that the motor is too hot. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-13`.

This fault can only appear when the thermistor input is enabled with `P-47` set to 1. The factory default is 0 (disabled).

## Possible causes

- The motor is overloaded or the machine is stiff.
- The motor runs for long periods at low speed, where its own cooling fan is weak.
- The motor cooling fins or fan cowl are blocked with dirt.
- The air around the motor is too hot.
- A broken wire or loose connection in the thermistor circuit. An open circuit is read as overtemperature.
- `P-47` is set to 1 but no thermistor is connected.

## Recommended actions

1. Let the motor cool. The fault cannot be reset while the thermistor still reports a high temperature.
2. Check the motor for overload and confirm the machine turns freely.
3. Clean the motor cooling fins and fan cowl.
4. Isolate the drive, wait 5 minutes, then check the wiring at TH1 and TH2 and in the motor terminal box.
5. If the motor has no thermistor, set `P-47` to 0.
6. Press STOP/RESET to clear the fault.

## When to contact support

Contact Voltrix Drives support if `E-13` remains with a cool motor and a sound thermistor circuit. Have the drive rating, the value of `P-47` and the fault history (`P-55` to `P-59`) ready.
