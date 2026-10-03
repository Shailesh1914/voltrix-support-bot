---
article_id: KB-008
title: E-08 Motor overload
category: fault
kb_version: v2
---

# E-08 Motor overload

## Meaning

The VX-200 calculates how hot the motor is from the output current and the motor rated current in `P-17`. `E-08` means this calculation shows the motor has been drawing more than its permitted current for too long. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-08`.

## Possible causes

- The driven machine is overloaded, stiff or partly jammed.
- Motor rated current in `P-17` is set lower than the motor nameplate value.
- The motor overload protection level `P-46` is set too low. The factory default is 100 % of `P-17`.
- The motor runs for long periods at low speed, where its own cooling is weak.
- A motor fault such as worn bearings.

## Recommended actions

1. Let the motor cool before restarting.
2. Check the machine for mechanical overload and confirm it turns freely.
3. Compare `P-17` with the current on the motor nameplate and correct it if needed.
4. Check `P-46`. Do not raise it above 100 % unless the motor data permits it.
5. Review how long the motor runs at low frequency under load.
6. Press STOP/RESET to clear the fault.

Do not confuse `E-08` with `E-09`: `E-08` protects the motor, `E-09` protects the drive.

## When to contact support

Contact Voltrix Drives support if `E-08` appears while the measured motor current is below the nameplate current. Have the nameplate data, the values of `P-17` and `P-46`, and the fault history (`P-55` to `P-59`) ready.
