---
article_id: KB-036
title: Using the emergency stop and external fault input correctly
category: safety
kb_version: v1
---

# Using the emergency stop and external fault input correctly

## What the external fault input does

The external fault input lets a device outside the VX-200 stop the drive. By default it is digital input DI3. It uses a normally closed circuit: while DI3 is connected to +24V the drive can run. When the circuit opens, the drive switches off its output, the motor coasts to a stop and the display flashes `E-14`.

Because the circuit is normally closed, a broken wire also stops the drive.

## What it does not do

- It does not isolate the drive. The power terminals stay live.
- It does not hold the motor or the machine still. The motor coasts, and a load with high inertia may take a long time to stop.
- It is a control function of the drive, not a certified safety function.

## Emergency stop

The emergency stop for a machine must be designed from the machine's risk assessment and must follow the site's safety rules. Do not rely on the drive's STOP/RESET key or on the external fault input alone as the emergency stop for a machine.

An emergency stop button may additionally be wired into the DI3 circuit so that the drive reports `E-14` when the button is pressed. This is for indication and does not replace the machine's emergency stop circuit.

## Wiring a device to DI3

1. Isolate the drive and wait 5 minutes.
2. Remove the factory link between DI3 and +24V.
3. Wire the normally closed contact of the external device between DI3 and +24V.
4. Tighten the terminals to 0.5 Nm.

## Restarting after a stop

1. Find and correct the reason for the stop.
2. Reset the external device.
3. Press STOP/RESET.

Remove the run command before resetting, so the motor does not restart unexpectedly.
