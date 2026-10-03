---
article_id: KB-024
title: "Quick-start commissioning: entering motor nameplate data"
category: parameters
kb_version: v2
---

# Quick-start commissioning: entering motor nameplate data

The VX-200 needs the data from the motor nameplate to control and protect the motor correctly. Enter it before the motor is run for the first time, and again whenever the motor is changed.

## Before you start

- Complete the pre-power-up checklist.
- Make sure the motor is stopped. Motor data can only be changed while the motor is stopped.
- Read the values from the nameplate for the connection (star or delta) actually used.

## Step 1: enter the motor data

| Parameter | Value to enter |
|---|---|
| `P-16` | Motor rated voltage (V) |
| `P-17` | Motor rated current (A) |
| `P-18` | Motor rated frequency (Hz) |
| `P-19` | Motor rated speed (rpm) |
| `P-20` | Motor rated power (kW) |

## Step 2: choose the control mode

Set `P-07` to 0 for V/f control (the factory default) or 1 for sensorless vector control. V/f suits simple loads such as fans and pumps. Sensorless vector gives better torque at low speed.

## Step 3: run the auto-tune

1. Set `P-21` to 1 and press ENTER.
2. Press RUN. The display shows `tUnE`.
3. The auto-tune takes about 30 seconds. The motor does not rotate, but it is energised.
4. When the display returns to the flashing frequency, the auto-tune is complete.

## Step 4: set the basic application values

- Acceleration and deceleration times: `P-05` and `P-06`.
- Minimum and maximum frequency: `P-03` and `P-04`.
- Control source: `P-01` and `P-02`.

## Step 5: test

Start the motor at a low frequency and check the direction of rotation before running at full speed.
