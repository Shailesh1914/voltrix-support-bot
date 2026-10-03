---
article_id: KB-039
title: Flying start (starting onto a spinning motor)
category: parameters
kb_version: v2
---

# Flying start (starting onto a spinning motor)

## What it does

Normally the VX-200 starts the motor from 0 Hz. If the motor is already turning, for example a fan being turned by air flow or a machine still running down after a coast stop, starting from 0 Hz can cause a high current and trip the drive on `E-01`.

With flying start enabled, the drive first measures the speed and direction of the spinning motor, then takes it over at that speed and ramps to the set frequency.

## Flying start parameter

| Parameter | Function | Range | Factory default |
|---|---|---|---|
| `P-11` | Flying start: 0 = disabled, 1 = enabled | 0–1 | 0 |

## When to use it

- Fans that can be turned by air flow or by another fan while stopped.
- Machines with high inertia that are restarted before they have stopped, especially when the stop mode `P-08` is 1 (coast to stop).
- Together with automatic restart (`P-09`), where the motor may still be turning when the drive restarts.

## Points to note

- Each start takes up to 2 seconds longer while the drive measures the motor speed.
- Enter the correct motor data in `P-16` to `P-20` and run the auto-tune with `P-21` first. Flying start relies on this data.
- If the motor is turning in the reverse direction, the drive slows it to 0 Hz first and then accelerates it in the commanded direction.
- Flying start does not shorten the stopping time and does not prevent `E-05` during deceleration.

## Setting it up

1. Stop the motor.
2. Set `P-11` to 1 and press ENTER.
3. Test by giving a run command while the motor is coasting, and confirm the drive picks it up without a fault.

If `E-01` still appears with flying start enabled, see the article on `E-01` overcurrent during acceleration.
