---
article_id: KB-025
title: Setting acceleration and deceleration ramp times
category: parameters
kb_version: v1
---

# Setting acceleration and deceleration ramp times

## The two ramp parameters

| Parameter | Function | Range | Factory default |
|---|---|---|---|
| `P-05` | Acceleration time | 0.1–600.0 s | 10.0 s |
| `P-06` | Deceleration time | 0.1–600.0 s | 10.0 s |

`P-05` is the time the drive takes to raise the output from 0 Hz to the maximum frequency in `P-04`. `P-06` is the time to go from the maximum frequency down to 0 Hz. A change over part of the range takes a proportional part of the time. For example, with `P-04` at 50.0 Hz and `P-05` at 10.0 s, going from 0 to 25 Hz takes 5 seconds.

## Choosing the values

- Start with the factory defaults.
- Shorten a ramp in small steps only if the process needs it.
- Heavy loads and loads with high inertia, such as fans and flywheels, need longer ramps.

## Signs that a ramp is too short

| Fault | Meaning | Change to make |
|---|---|---|
| `E-01` | Overcurrent during acceleration | Increase `P-05` |
| `E-09` | Drive overload | Increase `P-05` |
| `E-02` | Overcurrent during deceleration | Increase `P-06` |
| `E-05` | DC bus overvoltage during fast deceleration | Increase `P-06` |

## Stop mode

`P-08` sets what happens on a stop command:

- 0 (factory default): ramp to stop, using the time in `P-06`.
- 1: coast to stop. The drive switches off its output and the motor runs down freely.

Coast to stop avoids `E-02` and `E-05`, but the stopping time then depends only on the load.

## Changing the values

Both ramp times can be changed while the motor is running. The new value applies from the next change of speed.
