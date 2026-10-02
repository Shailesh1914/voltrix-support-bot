---
article_id: KB-010
title: E-10 Input phase loss
category: fault
kb_version: v1
---

# E-10 Input phase loss

## Meaning

The VX-200 detected that one of the three mains supply phases at L1, L2 or L3 is missing or much lower than the others. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes `E-10`. The protection is controlled by `P-48` and is enabled by default.

## Possible causes

- A blown fuse or a tripped pole in the upstream protection.
- A loose or burnt connection at the L1, L2 or L3 terminals.
- A faulty contact in an upstream isolator or contactor.
- A broken conductor in the supply cable.
- A badly unbalanced supply.

## Recommended actions

1. Measure the voltage between L1–L2, L2–L3 and L1–L3 with a suitable meter. All three readings should be within 380–480 V AC ±10 % and close to each other.
2. Check the upstream fuses, circuit breaker, isolator and any contactor.
3. Isolate the drive, wait 5 minutes, then inspect and re-tighten the L1, L2, L3 terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
4. Inspect the supply cable for damage.
5. Restore all three phases, then press STOP/RESET to clear the fault.

Do not disable `P-48` to keep the drive running. Running with a missing phase overstresses the drive.

## When to contact support

Contact Voltrix Drives support if `E-10` appears while all three measured voltages are present and balanced. Have the three measured voltages, the drive rating and the fault history (`P-55` to `P-59`) ready.
