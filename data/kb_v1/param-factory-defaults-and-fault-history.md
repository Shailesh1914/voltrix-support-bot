---
article_id: KB-028
title: Restoring factory defaults and viewing the fault history
category: parameters
kb_version: v1
---

# Restoring factory defaults and viewing the fault history

## Viewing the fault history

The VX-200 stores the last 5 faults. They are kept when the supply is switched off.

| Parameter | Content |
|---|---|
| `P-55` | Most recent fault |
| `P-56` | Second most recent fault |
| `P-57` | Third most recent fault |
| `P-58` | Fourth most recent fault |
| `P-59` | Oldest stored fault |

To read the history, press MENU, go to `P-55` with ▲ or ▼ and press ENTER. The display shows a code from `E-01` to `E-16`, or `----` if nothing is stored. When a sixth fault occurs, the oldest entry is dropped.

To clear the history, set `P-60` to 1 and press ENTER.

Write down the fault history before contacting Voltrix Drives support and before restoring factory defaults.

## Restoring factory defaults

A restore sets every parameter from `P-01` to `P-54` back to its factory value. The fault history in `P-55` to `P-59` is kept.

1. Stop the motor.
2. Write down the present settings if they may be needed again.
3. Press MENU and go to `P-15`.
4. Press ENTER, set the value to 1 and press ENTER again.
5. The display shows `dEF` for a few seconds and then returns to the flashing frequency. `P-15` returns to 0 by itself.

## After a restore

- The control source returns to the keypad (`P-01` = 0, `P-02` = 0).
- Ramp times return to 10.0 s and the maximum frequency to 50.0 Hz.
- The motor data is lost. Re-enter `P-16` to `P-20` and repeat the auto-tune with `P-21`, as described in the quick-start commissioning article.

## When to restore

Restore the defaults when the settings are unknown, or as part of clearing fault `E-15`.
