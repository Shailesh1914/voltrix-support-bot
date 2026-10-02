---
article_id: KB-020
title: Wiring the control terminals (digital and analog I/O)
category: installation
kb_version: v1
---

# Wiring the control terminals (digital and analog I/O)

Isolate the drive and wait 5 minutes before removing the terminal cover.

## Control terminal list

| Terminal | Function |
|---|---|
| +24V | 24 V DC supply for the digital inputs |
| COM | Common for the digital inputs |
| DI1–DI6 | Six digital inputs |
| +10V | 10 V DC supply for a speed potentiometer |
| AI1 | Analog input, 0–10 V |
| AI2 | Analog input, 4–20 mA |
| AGND | Common for the analog inputs and output |
| AO1 | Analog output, 0–10 V |
| R1A, R1B, R1C | Relay output 1 (changeover contact) |
| R2A, R2C | Relay output 2 (normally open contact) |
| TH1, TH2 | Motor thermistor input |

## Default functions

- DI1: run forward
- DI2: run reverse
- DI3: external fault (normally closed; linked to +24V at the factory)
- DI4: fault reset
- DI5: jog
- DI6: not assigned
- Relay 1: fault
- Relay 2: drive running

A digital input is active when it is connected to +24V. The functions of DI1 to DI6 are set in `P-26` to `P-31`.

## Wiring rules

- Use screened cable for the analog signals and connect the screen at the drive end only.
- Run control cables at least 200 mm away from the mains and motor cables. Where they must cross, cross at a right angle.
- Tighten control terminals to 0.5 Nm.
- Use a 10 kΩ potentiometer between +10V, AI1 and AGND for a manual speed reference.

The digital inputs only control the drive when the control source `P-01` is set to terminals. See the article on choosing the control source.
