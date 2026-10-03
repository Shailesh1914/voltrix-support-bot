---
article_id: KB-038
title: Automatic restart after a supply dip
category: parameters
kb_version: v2
---

# Automatic restart after a supply dip

## What it does

By default, the VX-200 stays stopped after a fault until it is reset by the STOP/RESET key or the fault reset input DI4. Automatic restart lets the drive reset itself and start the motor again after a short supply problem, without anyone attending the machine.

Automatic restart only applies to these faults:

- `E-06` DC bus undervoltage
- `E-04` DC bus overvoltage at standstill or constant speed

All other faults must be reset by hand after the cause has been found.

## Restart parameters

| Parameter | Function | Range | Factory default |
|---|---|---|---|
| `P-09` | Number of restart attempts: 0 = automatic restart disabled | 0–5 | 0 |
| `P-10` | Delay before each restart attempt | 1–60 s | 5 s |

The drive only restarts when all of these are true:

- The control source is the terminals (`P-01` = 1).
- A run command on DI1 or DI2 is still present.
- The supply voltage has returned to the permitted range.

If the fault is still present after the last attempt, the drive stays tripped and must be reset by hand. The attempt counter is set back to zero after 10 minutes of running without a fault.

## Safety

**With automatic restart enabled, the motor can start without warning.**

- Enable it only where the machine's risk assessment allows an unattended restart.
- Fit a warning sign on the machine stating that it may start automatically.
- Make sure a person working on the machine cannot be put at risk by a restart. Removing the run command or pressing STOP/RESET is not safe isolation; follow the safe isolation article before working on the machine.

## Using it with flying start

If the motor may still be turning when the drive restarts, also enable flying start (`P-11` = 1). Otherwise a restart onto a spinning motor can cause `E-01`.

## Setting it up

1. Stop the motor.
2. Confirm `P-01` is 1.
3. Set `P-10` to the delay needed, for example to let the supply settle.
4. Set `P-09` to the number of attempts, usually 1 to 3.
5. Test by switching off the supply briefly with the run command present, and confirm the drive restarts after the delay.
