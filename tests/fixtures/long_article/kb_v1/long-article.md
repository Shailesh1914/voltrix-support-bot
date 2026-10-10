---
article_id: KB-950
title: Fixture long article for split and overlap
category: maintenance
kb_version: v1
---

# Fixture long article for split and overlap

This synthetic article exists only to test how ingestion splits long sections and repeats overlap between the pieces.

## Short section

This section is short, so it stays as one chunk.

## Step-by-step procedure

1. Isolate the drive at the main switch, lock it off and fit a warning tag to the handle before any work starts.
2. Wait at least 5 minutes after isolation so that the DC bus capacitors can discharge to a safe level.
3. Measure the DC bus voltage between DC+ and DC− and confirm that it is below 50 V DC before touching any terminal.
4. Remove the terminal cover by loosening its two captive screws, and place the cover where it cannot be damaged.
5. Inspect the mains terminals L1, L2 and L3 for discolouration, which shows that a connection has been running hot.
6. Inspect the motor terminals U, V and W in the same way, and check that every cable lug is seated squarely.
7. Check the earth connection to the PE terminal, making sure that the protective conductor is not loose or corroded.
8. Re-tighten every power terminal to the torque given in the wiring article, working from left to right.
9. Check the control terminal block for loose wires, and pull gently on each wire to confirm it is held firmly.
10. Clean any dust from the terminal area with a soft brush, and do not use compressed air near the control board.
11. Refit the terminal cover and tighten its two screws, checking that the cover seal is not twisted or pinched.
12. Remove your lock and warning tag, restore the supply, and confirm that the display shows the normal ready state.
13. Run the motor at low speed for one minute and listen for unusual noise from the motor or the driven machine.
14. Record the date, the checks carried out and any defects found in the maintenance log for this drive.

## Background

The VX-200 converts the fixed mains supply into a variable frequency output for the motor. The rectifier charges a DC bus, and the inverter switches that bus voltage to build the output waveform. The output frequency sets the motor speed. The output voltage rises with the frequency so that the motor flux stays roughly constant.

Heat is produced mainly in the inverter switches and in the rectifier. The heatsink carries that heat to the cooling air. The fan pulls air through the heatsink fins from the bottom of the drive to the top. Blocked vents raise the heatsink temperature and can lead to fault E-07.

The DC bus capacitors smooth the rectified voltage and supply short bursts of current to the inverter. Their life depends strongly on temperature. A drive that runs ten degrees cooler can expect a much longer capacitor life. Good ventilation is therefore the cheapest way to extend the life of the drive.

During deceleration the motor can act as a generator and push energy back into the DC bus. If the bus voltage rises too far, the drive trips with fault E-04 or E-05. A longer deceleration time in P-06 reduces the energy returned per second. A braking resistor can absorb the extra energy where a short stop is needed.

The drive protects the motor with an electronic thermal model based on the motor current and the data in P-16 to P-20. The model cannot see the real winding temperature. Where a motor runs at low speed for long periods, its own fan gives little cooling. A motor thermistor connected to the drive gives the best protection in that case.

## Long sentences

When the drive is installed in a cabinet together with other equipment that produces heat, such as transformers, power supplies or other drives, the air temperature inside the cabinet must be measured at the air inlet of the drive during the hottest part of a normal working day.

If the measured inlet air temperature is higher than the rated ambient temperature given in the mounting article, the cabinet ventilation must be improved with a larger fan, a filter with a lower pressure drop, or a cooling unit, before the drive is put back into continuous service.

Where several drives are mounted above one another in the same cabinet, the hot air leaving the lower drive must not enter the air inlet of the drive above it, so an air deflector plate or a larger vertical spacing between the drives is needed in that arrangement.

Cabinet filters collect dust quickly in places such as sawmills, flour mills, textile plants and cement works, so the filter mats in those places must be checked at least once a month and replaced as soon as they are visibly grey or the air flow through them has clearly dropped.

A drive that has tripped on overtemperature should not be reset again and again without finding the cause, because each restart with a hot heatsink shortens the life of the power components and of the DC bus capacitors, and the cause will usually be found in the ventilation.

Before a drive that has been stored for more than one year is connected to the supply again, the DC bus capacitors must be reformed by following the storage and capacitor reforming article, because capacitors that have been unused for a long time can fail when full voltage is applied suddenly.

When the drive is mounted outdoors in a protective enclosure, the enclosure must be shaded from direct sunlight, because the sun can heat a closed metal enclosure far above the outside air temperature and cause the drive to trip on overtemperature even when the motor load is light.

## Settings table

The table below lists the basic parameters. Change them only with the motor stopped, and note the old value before you change anything.

| Parameter | Name | Range | Default |
|---|---|---|---|
| `P-01` | Control source for start and stop | 0 = keypad, 1 = terminals | 0 |
| `P-02` | Speed reference source | 0 = keypad, 1 = analog input | 0 |
| `P-03` | Maximum output frequency | 10.0 to 120.0 Hz | 50.0 Hz |
| `P-04` | Minimum output frequency | 0.0 Hz to P-03 | 0.0 Hz |
| `P-05` | Acceleration time | 0.1 to 600.0 s | 10.0 s |
| `P-06` | Deceleration time | 0.1 to 600.0 s | 10.0 s |
| `P-11` | Flying start | 0 = off, 1 = on | 0 |

The VX-200 converts the fixed mains supply into a variable frequency output for the motor. The rectifier charges a DC bus, and the inverter switches that bus voltage to build the output waveform. The output frequency sets the motor speed. The output voltage rises with the frequency so that the motor flux stays roughly constant.

Heat is produced mainly in the inverter switches and in the rectifier. The heatsink carries that heat to the cooling air. The fan pulls air through the heatsink fins from the bottom of the drive to the top. Blocked vents raise the heatsink temperature and can lead to fault E-07.

The DC bus capacitors smooth the rectified voltage and supply short bursts of current to the inverter. Their life depends strongly on temperature. A drive that runs ten degrees cooler can expect a much longer capacitor life. Good ventilation is therefore the cheapest way to extend the life of the drive.
