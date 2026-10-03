---
article_id: KB-015
title: E-15 Parameter memory error
category: fault
kb_version: v2
---

# E-15 Parameter memory error

## Meaning

The VX-200 checks its stored parameter values each time it powers up and each time a parameter is saved. `E-15` means the stored values could not be read or written correctly. The drive will not run the motor, the FAULT LED lights and the display flashes `E-15`.

## Possible causes

- The supply was switched off at the moment a parameter was being saved.
- Strong electrical interference, often due to poor earthing or cable screening.
- An internal memory fault in the drive.

## Recommended actions

1. Switch the supply off, wait 5 minutes, then switch it on again.
2. If `E-15` returns, restore the factory defaults by setting `P-15` to 1 and pressing ENTER.
3. After the restore, re-enter the motor nameplate data in `P-16` to `P-20`, repeat the auto-tune with `P-21`, and re-enter any other settings for the application. A restore sets parameters `P-01` to `P-54` back to their defaults and keeps the fault history.
4. Check the earthing and cable screening as described in the earthing article.
5. Do not switch off the supply while the display is still showing a value being saved.

Keep a written record of the parameter settings for each drive so they can be re-entered after a restore.

## When to contact support

Contact Voltrix Drives support if `E-15` returns after restoring the factory defaults, or if it appears more than once. Have the drive rating, frame size and a note of what was happening when the fault appeared.
