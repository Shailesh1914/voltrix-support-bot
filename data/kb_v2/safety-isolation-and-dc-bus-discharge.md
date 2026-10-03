---
article_id: KB-034
title: Safe isolation and DC bus discharge time before working on the drive
category: safety
kb_version: v2
---

# Safe isolation and DC bus discharge time before working on the drive

## The hazard

The VX-200 contains DC bus capacitors that stay charged at a dangerous voltage after the supply is switched off. With a 400 V supply the DC bus is at about 565 V DC. A dark display does not prove the drive is safe.

**Wait 5 minutes after switching off the supply before touching any terminal.**

Pressing STOP/RESET or removing the run command does not make the drive safe. The terminals L1, L2, L3, U, V, W, DC+ and DC− remain live whenever the supply is connected, even when the motor is stopped.

## Safe isolation procedure

1. Stop the motor.
2. Switch off the supply at the isolator upstream of the drive.
3. Lock the isolator in the off position and attach a warning tag.
4. Wait 5 minutes.
5. Remove the terminal cover.
6. With a suitable voltmeter that has been checked on a known source, confirm:
   - no voltage between L1, L2 and L3, and from each to PE;
   - less than 50 V DC between DC+ and DC−.
7. Only then begin work.

## Other sources of voltage

- The relay terminals R1A, R1B, R1C, R2A and R2C may carry voltage from an external circuit even when the drive is isolated. Isolate those circuits separately.
- A motor that is turned by its load can generate voltage at U, V, W. Make sure the motor cannot rotate.

## Who may do the work

Only electrically qualified persons may install, wire or work on the drive, following the site's own safety rules.

## Scope

This article covers isolation of the drive only. For work that is not described in the knowledge base, contact Voltrix Drives support.
