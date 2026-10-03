---
article_id: KB-006
title: E-06 DC bus undervoltage
category: fault
kb_version: v2
---

# E-06 DC bus undervoltage

## Meaning

The DC bus voltage inside the VX-200 fell below the trip level of 320 V DC while the drive was running. The trip level was lowered from 350 V DC so that the drive rides through more short supply dips without tripping. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-06`.

## Possible causes

- The mains supply voltage is too low. The permitted supply is 380–480 V AC ±10 %, so the lowest permitted value is 342 V AC.
- A short dip or interruption of the supply.
- A loose connection at the L1, L2 or L3 terminals, or in the upstream fuses, circuit breaker or isolator.
- A weak supply whose voltage drops when the motor accelerates or when other large loads start.
- The supply was switched off while the drive was running.

## Recommended actions

1. Measure the supply voltage on L1, L2 and L3 with a suitable meter, both with the motor stopped and while it runs.
2. Check upstream fuses, the circuit breaker and the isolator.
3. Isolate the drive, wait 5 minutes, then re-tighten the L1, L2, L3 terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
4. If the voltage drops during acceleration, increase the acceleration time in `P-05`.
5. Press STOP/RESET to clear the fault once the supply is healthy.
6. If short supply dips are frequent and the machine is safe to restart on its own, consider enabling automatic restart with `P-09`. See the automatic restart article. By default the drive does not restart by itself after `E-06`.

`E-06` recorded at the moment the supply is switched off is normal and needs no action.

## When to contact support

Contact Voltrix Drives support if `E-06` appears while the measured supply voltage stays inside the permitted range. Have the measured voltages, the drive rating and the fault history (`P-55` to `P-59`) ready.
