---
article_id: KB-026
title: Setting minimum and maximum frequency limits
category: parameters
kb_version: v2
---

# Setting minimum and maximum frequency limits

## The two limit parameters

| Parameter | Function | Range | Factory default |
|---|---|---|---|
| `P-03` | Minimum frequency | 0.0 Hz up to the value of `P-04` | 0.0 Hz |
| `P-04` | Maximum frequency | value of `P-03` up to 400.0 Hz | 50.0 Hz |

The drive keeps the output frequency between these two limits whenever the motor is running, whatever the reference from the keypad or the analog input asks for.

## Minimum frequency

Use `P-03` when the machine must not run below a certain speed. Common reasons are a pump that needs a minimum flow, or a motor that cools poorly at very low speed. With `P-03` at 20.0 Hz, a reference of 0 gives 20.0 Hz as long as a run command is present.

## Maximum frequency

Use `P-04` to stop the machine being driven too fast. Although the VX-200 can produce up to 400 Hz, most standard induction motors are designed for 50 or 60 Hz. Before setting `P-04` above the motor rated frequency in `P-18`, confirm with the motor and machine documentation that both are suitable for the higher speed.

## Effect on the analog reference

The analog inputs are scaled between the two limits:

- AI1: 0 V gives `P-03`, 10 V gives `P-04`.
- AI2: 4 mA gives `P-03`, 20 mA gives `P-04`.

## Effect on ramp times

The ramp times `P-05` and `P-06` are measured between 0 Hz and `P-04`. If you raise `P-04`, the motor accelerates at a faster rate unless you also lengthen the ramp times.

## Changing the values

Stop the motor before changing `P-03` or `P-04`.
