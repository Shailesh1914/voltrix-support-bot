# Part B: full-flow run 3 (whole-articles)

Spec 05, Part B. Every ticket through QueryFlow with the real model at
threshold -1.0, so the retrieval check never escalates; the
unknown-fault-code check stays active. Handoffs went to the
evaluation-only file below, never to handoffs/.

- Run: **VALID**
- Tickets run: 70/70
- Date: 2026-10-17
- Git commit: 211c5aef7d8ee931caaff1773a5486337fe1439c (with uncommitted changes)
- Ticket file SHA-256: `c07524bc9a4f251340ed5ee4f9730c3f57307d978df875d389a43d1022fdb80a`
- Code trees at HEAD: query `8b48ca796e94`, ingestion `16f1e659e66d`, evals/*.py `e9ed6b85bf52`
- Model: claude-haiku-4-5-20251001, temperature 0, max output tokens 2048
- System prompt SHA-256: `57a9ae57e9648952a933b60d9785122fb3e5d356b2445ce97bca4da1b09f2ac8`
- KB version: v1; threshold -1.0 (evaluation only, passed to the flow)
- Label: whole-articles
- Handoffs: `2026-10-17-part-b-whole-articles-run3-handoffs.jsonl` (29 records)
- Top score and retrieved chunks: step d of spec 02, from the free planning pass (checked against this run); the model read the whole selected articles (step 3e)
- Model calls: 66
- Tokens: 312,746 input, 13,209 output
- Cost: $0.3788 ($1.00 / $5.00 per million input / output tokens)
- Malformed model outputs: 0. Malformed model outputs have no token counts (the generator raises before returning usage). They are still billed, so the cost is slightly underestimated for them.

## Results at threshold -1.0 (this run only)

The threshold itself is simulated by the sweep (Part C).

| Set | AC1 (target 85%) | AC2 (target 95%) | Wrong escalation | Both articles cited |
|---|---|---|---|---|
| calibration | 19/24 (79.2%) | 11/11 (100.0%) | 4/24 (16.7%) | 2/3 (66.7%) |
| holdout | 21/24 (87.5%) | 11/11 (100.0%) | 3/24 (12.5%) | 3/6 (50.0%) |
| full | 40/48 (83.3%) | 22/22 (100.0%) | 7/48 (14.6%) | 5/9 (55.6%) |

- failed_check counts (full set): grounding 3
- Escalation reasons (full set): insufficient_context 19, out_of_scope 10
- T-101 (article_match "any"): AC1 **no**

## All tickets

| Ticket | Set | Expected | Top score | Status | Reason | failed_check | Cited | Pass | Tokens in/out |
|---|---|---|---|---|---|---|---|---|---|
| T-001 | calibration | answer | 0.8205 | answered | – | – | KB-001 | yes | 4536/287 |
| T-002 | holdout | answer | 0.8379 | answered | – | – | KB-002, KB-025 | yes | 4610/201 |
| T-003 | calibration | answer | 0.8094 | answered | – | – | KB-003 | yes | 4407/347 |
| T-004 | holdout | answer | 0.8745 | answered | – | – | KB-004 | yes | 4617/278 |
| T-005 | calibration | answer | 0.8853 | escalated | insufficient_context | grounding | – | **no** | 4698/317 |
| T-006 | holdout | answer | 0.8341 | answered | – | – | KB-006 | yes | 4469/409 |
| T-007 | calibration | answer | 0.8087 | answered | – | – | KB-007, KB-030 | yes | 4658/536 |
| T-008 | holdout | answer | 0.8260 | answered | – | – | KB-008, KB-009 | yes | 4431/304 |
| T-009 | calibration | answer | 0.8234 | escalated | insufficient_context | grounding | – | **no** | 4562/275 |
| T-010 | holdout | answer | 0.7945 | answered | – | – | KB-010 | yes | 4426/334 |
| T-011 | calibration | answer | 0.8713 | answered | – | – | KB-011 | yes | 4531/129 |
| T-012 | holdout | answer | 0.8267 | answered | – | – | KB-012 | yes | 4338/203 |
| T-013 | calibration | answer | 0.8719 | answered | – | – | KB-013 | yes | 4577/161 |
| T-014 | holdout | answer | 0.8594 | answered | – | – | KB-014, KB-036 | yes | 4775/291 |
| T-015 | calibration | answer | 0.8242 | answered | – | – | KB-015, KB-028 | yes | 4550/451 |
| T-016 | holdout | answer | 0.8523 | escalated | insufficient_context | – | – | **no** | 4628/71 |
| T-017 | calibration | answer | 0.8159 | answered | – | – | KB-017 | yes | 4964/150 |
| T-018 | holdout | answer | 0.7636 | answered | – | – | KB-018 | yes | 4844/198 |
| T-019 | calibration | answer | 0.8021 | answered | – | – | KB-018 | yes | 4846/201 |
| T-020 | holdout | answer | 0.6985 | answered | – | – | KB-019, KB-034 | yes | 5105/197 |
| T-021 | calibration | answer | 0.6694 | escalated | insufficient_context | grounding | – | **no** | 5202/153 |
| T-022 | holdout | answer | 0.7044 | answered | – | – | KB-027, KB-020 | yes | 4820/323 |
| T-023 | calibration | answer | 0.8526 | answered | – | – | KB-021 | yes | 4696/162 |
| T-024 | holdout | answer | 0.7054 | answered | – | – | KB-022 | yes | 4715/413 |
| T-025 | calibration | answer | 0.7266 | answered | – | – | KB-023 | yes | 4780/191 |
| T-026 | holdout | answer | 0.7176 | answered | – | – | KB-027, KB-023 | yes | 4987/281 |
| T-027 | calibration | answer | 0.7312 | answered | – | – | KB-024, KB-022 | yes | 4810/342 |
| T-028 | holdout | answer | 0.7308 | answered | – | – | KB-025 | yes | 4997/200 |
| T-029 | calibration | answer | 0.7828 | answered | – | – | KB-026 | yes | 4972/153 |
| T-030 | holdout | answer | 0.8205 | escalated | insufficient_context | – | – | **no** | 4547/71 |
| T-031 | calibration | answer | 0.6435 | answered | – | – | KB-028 | yes | 4895/261 |
| T-032 | holdout | answer | 0.7304 | answered | – | – | KB-028 | yes | 4429/353 |
| T-033 | calibration | answer | 0.7056 | answered | – | – | KB-029 | yes | 4838/360 |
| T-034 | holdout | answer | 0.6627 | answered | – | – | KB-030 | yes | 4554/213 |
| T-035 | calibration | answer | 0.7655 | answered | – | – | KB-031 | yes | 4737/98 |
| T-036 | holdout | answer | 0.7939 | answered | – | – | KB-032 | yes | 4878/351 |
| T-037 | calibration | answer | 0.7062 | answered | – | – | KB-033 | yes | 4973/242 |
| T-038 | holdout | answer | 0.7163 | answered | – | – | KB-034 | yes | 4975/243 |
| T-039 | calibration | answer | 0.7861 | answered | – | – | KB-036, KB-032 | **no** | 4603/186 |
| T-040 | holdout | answer | 0.6642 | answered | – | – | KB-035 | yes | 4843/150 |
| T-041 | calibration | answer | 0.6806 | answered | – | – | KB-035 | yes | 4560/134 |
| T-042 | holdout | answer | 0.8844 | answered | – | – | KB-036 | yes | 4622/262 |
| T-043 | calibration | escalate | 0.6729 | escalated | insufficient_context | – | – | yes | 4639/71 |
| T-044 | holdout | escalate | 0.7659 | escalated | insufficient_context | – | – | yes | 4938/71 |
| T-045 | calibration | escalate | 0.6755 | escalated | insufficient_context | – | – | yes | 4941/71 |
| T-046 | holdout | escalate | 0.6980 | escalated | insufficient_context | – | – | yes | 4830/71 |
| T-047 | calibration | escalate | 0.6336 | escalated | insufficient_context | – | – | yes | 4604/71 |
| T-048 | holdout | escalate | 0.7177 | escalated | insufficient_context | – | – | yes | 4905/71 |
| T-049 | calibration | escalate | 0.8853 | escalated | insufficient_context | – | – | yes | 4686/71 |
| T-050 | holdout | escalate | 0.6627 | escalated | insufficient_context | – | – | yes | 4812/71 |
| T-051 | calibration | escalate | 0.7053 | escalated | out_of_scope | – | – | yes | 4677/73 |
| T-052 | holdout | escalate | 0.7112 | escalated | out_of_scope | – | – | yes | 4626/73 |
| T-053 | calibration | escalate | 0.6635 | escalated | insufficient_context | – | – | yes | – |
| T-054 | holdout | escalate | 0.6630 | escalated | insufficient_context | – | – | yes | – |
| T-055 | calibration | escalate | 0.7221 | escalated | insufficient_context | – | – | yes | – |
| T-056 | holdout | escalate | 0.7011 | escalated | out_of_scope | – | – | yes | 5075/73 |
| T-057 | calibration | escalate | 0.6828 | escalated | out_of_scope | – | – | yes | 4612/73 |
| T-058 | holdout | escalate | 0.7893 | escalated | out_of_scope | – | – | yes | 4739/73 |
| T-059 | calibration | escalate | 0.6344 | escalated | out_of_scope | – | – | yes | 4973/73 |
| T-060 | holdout | escalate | 0.6890 | escalated | out_of_scope | – | – | yes | 4361/73 |
| T-101 | calibration | answer | 0.6975 | escalated | insufficient_context | – | – | **no** | 4798/71 |
| T-102 | holdout | answer | 0.6246 | escalated | insufficient_context | – | – | **no** | 4661/71 |
| T-103 | calibration | answer | 0.7619 | answered | – | – | KB-034, KB-032 | yes | 4835/168 |
| T-104 | holdout | answer | 0.7376 | answered | – | – | KB-028 | yes | 4890/288 |
| T-105 | calibration | answer | 0.7282 | answered | – | – | KB-006 | yes | 4318/337 |
| T-106 | holdout | answer | 0.7825 | answered | – | – | KB-030, KB-007 | yes | 5103/494 |
| T-107 | calibration | escalate | 0.7314 | escalated | insufficient_context | – | – | yes | – |
| T-108 | holdout | escalate | 0.6792 | escalated | out_of_scope | – | – | yes | 4870/73 |
| T-109 | calibration | escalate | 0.7741 | escalated | out_of_scope | – | – | yes | 4849/73 |
| T-110 | holdout | escalate | 0.7369 | escalated | out_of_scope | – | – | yes | 4999/73 |

## Answers (for the Step 10 review)

Not scored automatically beyond criterion 7 (spec 05, Scoring).

### T-001 (answer; answered)

Question: vx200 on the infeed conveyor trips evry time it ramps up, E-01 flashing. wht to check first

Model decision: answer; used_article_ids: KB-001

Answer shown to the user:

> E-01 means overcurrent during acceleration. Check these in order:
>
> 1. Check that the machine turns freely with the drive isolated.
>
> 2. Increase the acceleration time in P-05. The factory default is 10.0 s; try doubling the present value.
>
> 3. Confirm the motor nameplate values in P-16 to P-20, then repeat the auto-tune with P-21.
>
> 4. Isolate the drive, wait 5 minutes, then inspect the motor cable and the U, V, W terminals for damage or loose connections.
>
> 5. Let the motor stop completely before giving a new run command.
>
> 6. Press STOP/RESET to clear the fault and try again.
>
> If E-01 appears with the motor cable disconnected from the drive, or if the fault remains after these checks, contact Voltrix Drives support. Have the drive rating, frame size and the fault history (P-55 to P-59) ready.

### T-002 (answer; answered)

Question: Getting E-02 when we stop the mixer. Ramp down is set to 3 sec. We don't really need a controlled stop on this machine, is there a way round it?

Model decision: answer; used_article_ids: KB-002, KB-025

Answer shown to the user:

> Yes. Since you don't need a controlled stop, you can set the stop mode `P-08` to 1 (coast to stop). This will make the drive switch off its output and let the motor run down freely, which avoids the E-02 fault.
>
> Alternatively, you could increase the deceleration time in `P-06` from 3 seconds to a longer value. The factory default is 10.0 s; try doubling your present value.
>
> If you choose coast to stop, the stopping time will then depend only on the load.

### T-003 (answer; answered)

Question: Drive cut out while running at steady speed, red fault light on and E-03 on the display. One of the operators had flicked the local isolator next to the motor while it was running. Could that be the cause or is the drive damaged?

Model decision: answer; used_article_ids: KB-003

Answer shown to the user:

> Yes, that could be the cause. E-03 Overcurrent at constant speed is triggered when the VX-200 detects an output current above its trip level while the motor is running at a steady frequency.
>
> One of the possible causes of E-03 is: A contactor or isolator between the drive and the motor was switched while the drive was running.
>
> This matches what happened. The drive is not necessarily damaged.
>
> To clear the fault and check:
>
> 1. Do not open or close any switch between the drive and the motor while the drive is running.
> 2. Isolate the drive, wait 5 minutes, then check the motor cable and re-tighten the U, V, W terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
> 3. Confirm the motor nameplate values in P-16 to P-20.
> 4. Press STOP/RESET to clear the fault and restart.
>
> If E-03 appears repeatedly with a free-running machine and a sound motor cable, contact Voltrix Drives support. Have the drive rating, frame size, the output frequency at the time of the trip and the fault history (P-55 to P-59) ready.

### T-004 (answer; answered)

Question: E-04 keeps coming up overnight when the drive is just sat there not running anything. Measured the incoming supply at 535 V between phases. Is that the problem?

Model decision: answer; used_article_ids: KB-004

Answer shown to the user:

> Yes, that is the problem. The permitted supply is 380–480 V AC ±10 %, so the highest permitted value is 528 V AC. Your measured supply of 535 V is above the permitted range and is causing the E-04 fault.
>
> The DC bus voltage inside the VX-200 rose above the trip level of 800 V DC while the drive was stopped. This happens because the mains supply voltage is too high.
>
> You need to:
>
> 1. Contact your site's electrical supply provider or maintenance team to bring the supply voltage down to within the permitted range of 380–480 V AC ±10 %.
> 2. Once the supply voltage is back in range, press STOP/RESET to clear the fault.
>
> If you cannot reduce the supply voltage, contact Voltrix Drives support with the measured supply voltage, the drive rating and the fault history (P-55 to P-59).

### T-005 (answer; escalated, insufficient_context)

Question: big extract fan, drive throws an overvoltage code every time we stop it (E-05). decel is at 5s. what do i change and can i change it while the fan is still running or do i have to stop it first

Model decision: answer; used_article_ids: KB-005, KB-025

Rejected draft (failed_check grounding, never shown):

> You are seeing E-05 because the deceleration time is too short for the fan's inertia. Energy from the slowing load flows back into the drive and raises the DC bus voltage above 800 V DC.
>
> Change P-06 (deceleration time). The factory default is 10.0 s; increase it in steps until the fault no longer appears. Since your decel is at 5 s, try increasing it to 15 s or 20 s and test.
>
> You can change P-06 while the motor is running. The new value applies from the next change of speed.
>
> If the application does not need a controlled stop, you can also set the stop mode P-08 to 1 (coast to stop). This avoids E-05, but the stopping time then depends only on the load.
>
> If you still get E-05 with a long deceleration time, contact Voltrix Drives support with the drive rating, the value of P-06, a description of the load and the fault history (P-55 to P-59).

### T-006 (answer; answered)

Question: Our drive drops out whenever the big compressor on the same board kicks in. Display says E-06. Motor just coasts down. Anything we can do on the drive side?

Model decision: answer; used_article_ids: KB-006

Answer shown to the user:

> E-06 is DC bus undervoltage. When the compressor starts, it draws large current and causes the supply voltage to dip below the trip level of 350 V DC.
>
> On the drive side, you can try these actions:
>
> 1. Measure the supply voltage on L1, L2 and L3 with a suitable meter, both with the motor stopped and while it runs. Note the voltage when the compressor kicks in.
>
> 2. Check upstream fuses, the circuit breaker and the isolator for any issues.
>
> 3. Isolate the drive, wait 5 minutes, then re-tighten the L1, L2, L3 terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
>
> 4. If the voltage drops during the compressor start, increase the acceleration time in P-05. This reduces the current drawn by the motor during acceleration and may help the supply voltage stay higher.
>
> 5. Press STOP/RESET to clear the fault once the supply is healthy.
>
> However, the root cause is likely that your supply is weak and cannot handle both the drive and compressor starting together. The permitted supply is 380–480 V AC ±10 %, so the lowest permitted value is 342 V AC. If the voltage drops below this when the compressor starts, you may need to contact your electrical supplier or consider upgrading the supply infrastructure. Contact Voltrix Drives support if E-06 appears while the measured supply voltage stays inside the permitted range.

### T-007 (answer; answered)

Question: Drive in a warm panel keeps tripping mid afternoon on the heatsink overtemp fault and it wont reset straight away. Fins look pretty clogged with dust. Why wont it reset and whats the proper way to clean it out?

Model decision: answer; used_article_ids: KB-007, KB-030

Answer shown to the user:

> Why it won't reset:
>
> The heatsink temperature of the VX-200 reached the trip level of 90 °C. The fault cannot be reset until the heatsink has cooled.
>
> Proper way to clean the heatsink and vents:
>
> Preparation:
> 1. Stop the motor.
> 2. Isolate the supply and lock it off.
> 3. Wait 5 minutes for the DC bus to discharge.
> 4. Let the heatsink cool. It can reach 90 °C in operation.
>
> Cleaning:
> 1. Vacuum loose dust from the top vents and from the fan inlet at the bottom of the drive.
> 2. Brush the heatsink fins and vacuum the dust away as it loosens.
> 3. If compressed air is used, blow from the top of the drive downward, against the normal air flow, so the dust leaves through the fan inlet. Hold the fan blades still while blowing, so the fan is not spun too fast.
> 4. Clean or replace the cabinet filters.
> 5. Check that the fan spins freely by hand.
>
> Things to avoid:
> - Do not use water, solvents or cleaning sprays.
> - Do not push dust into the drive.
> - Do not use a metal nozzle or tool near the terminals or circuit boards.
> - Do not remove any cover other than the terminal cover.
>
> After cleaning:
> Restore the supply and confirm the fan runs when the drive runs. Check that the 100 mm clearance above and below the drive and 50 mm on each side are still free.
>
> What you need:
> - A soft, dry brush.
> - A vacuum cleaner with a plastic nozzle.
> - Dry, oil-free compressed air at low pressure, if available.
>
> The warm panel is likely contributing to the overtemperature fault. The drive gives its full rating from −10 °C to +40 °C and must be derated between 40 °C and 50 °C. After cleaning, check the mounting clearances and the cabinet ventilation.

### T-008 (answer; answered)

Question: whats the actual difference between E-08 and E-09?? we get both on different days and nobody here knows which one means what

Model decision: answer; used_article_ids: KB-008, KB-009

Answer shown to the user:

> E-08 and E-09 are two different overload faults that protect different parts of the drive system.
>
> E-08 Motor overload protects the motor. The VX-200 calculates how hot the motor is from the output current and the motor rated current in P-17. E-08 means this calculation shows the motor has been drawing more than its permitted current for too long.
>
> E-09 Drive overload protects the drive. The VX-200 can deliver 150 % of its rated output current for 60 seconds. E-09 means the output current stayed above the rated current for longer than the drive allows.
>
> In short: E-08 protects the motor, E-09 protects the drive.
>
> When you get E-08, the motor is too hot. When you get E-09, the drive itself is overloaded.
>
> Do not confuse E-08 with E-09: E-08 protects the motor, E-09 protects the drive.

### T-009 (answer; escalated, insufficient_context)

Question: E-08 on a pump motor after about 20 min running. Motor plate says 8.4 A but I see P-17 is set to 6.0. Machine turns freely by hand. Is that setting wrong?

Model decision: answer; used_article_ids: KB-008

Rejected draft (failed_check grounding, never shown):

> Yes, that setting is wrong. P-17 should match the motor nameplate current. Your motor nameplate says 8.4 A but P-17 is set to 6.0 A, which is lower than the actual motor rating.
>
> This is a known cause of E-08. When P-17 is set lower than the motor nameplate value, the drive calculates that the motor is overheating sooner than it actually is, and triggers the fault.
>
> To fix this:
>
> 1. Let the motor cool before restarting.
> 2. Change P-17 from 6.0 to 8.4 A to match the motor nameplate.
> 3. Press STOP/RESET to clear the fault.
> 4. Restart and monitor the motor.
>
> Since the machine turns freely by hand and the issue is the incorrect P-17 setting, this should resolve the E-08 fault.

### T-010 (answer; answered)

Question: one of the three supply fuses had blown, replaced it but still getting input phase loss. production wants it running tonight - can i just switch that protection off to get through the shift?

Model decision: answer; used_article_ids: KB-010

Answer shown to the user:

> No. Do not disable P-48 to keep the drive running. Running with a missing phase overstresses the drive.
>
> After replacing the fuse, follow these steps to find the real problem:
>
> 1. Measure the voltage between L1–L2, L2–L3 and L1–L3 with a suitable meter. All three readings should be within 380–480 V AC ±10 % and close to each other.
> 2. Check the upstream fuses, circuit breaker, isolator and any contactor.
> 3. Isolate the drive, wait 5 minutes, then inspect and re-tighten the L1, L2, L3 terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
> 4. Inspect the supply cable for damage.
> 5. Restore all three phases, then press STOP/RESET to clear the fault.
>
> The E-10 fault is still appearing because one of these issues remains: a loose or burnt connection at the terminals, a faulty contact in an upstream isolator or contactor, a broken conductor in the supply cable, or a badly unbalanced supply.

### T-011 (answer; answered)

Question: E-11 output phase loss. Terminals at the drive look tight. What should I be measuring on the motor leads to see if a winding has gone?

Model decision: answer; used_article_ids: KB-011

Answer shown to the user:

> With the motor cable disconnected from the drive, measure the resistance between the three motor conductors. The three readings should be nearly equal.
>
> If one reading is very different from the others, or if any reading is infinite (open circuit), a motor winding has failed.

### T-012 (answer; answered)

Question: earth fault E-12 after washdown. ok to put the insulation tester straight on the U V W terminals of the drive to check the motor?

Model decision: answer; used_article_ids: KB-012

Answer shown to the user:

> No. Never apply an insulation tester to the drive terminals; it can damage the drive.
>
> To check the motor after an earth fault E-12, follow these steps:
>
> 1. Isolate the drive and wait 5 minutes before touching any terminal.
> 2. Disconnect the motor cable from the U, V, W terminals of the drive.
> 3. Carry out an insulation resistance test on the motor and motor cable to earth.
>
> After washdown, also inspect the motor terminal box for moisture, dirt and loose strands, and inspect the cable along its length for crushing or abrasion.

### T-013 (answer; answered)

Question: Drive shows E-13 as soon as we try to run. This motor has no thermistor in it at all, nothing wired to TH1/TH2. How do we get rid of it?

Model decision: answer; used_article_ids: KB-013

Answer shown to the user:

> The motor has no thermistor connected, so you need to disable the thermistor input.
>
> Set P-47 to 0. This disables the thermistor monitoring. The factory default is 0 (disabled), so P-47 must have been changed to 1 at some point.
>
> After setting P-47 to 0, press STOP/RESET to clear the fault.

### T-014 (answer; answered)

Question: brand new drive, only power and motor connected, nothing on the control terminals. powers up with E-14. the little wire link that came on the terminals got taken off during wiring. related?

Model decision: answer; used_article_ids: KB-014, KB-036

Answer shown to the user:

> Yes, that is related. The E-14 fault means the external fault input is active.
>
> By default, digital input DI3 expects a normally closed circuit between DI3 and +24V. The factory link you removed was connecting DI3 to +24V. Without it, the circuit is open and the drive reports E-14.
>
> To fix this:
>
> 1. Isolate the drive, wait 5 minutes, then check the wiring at DI3 and +24V (tightening torque 0.5 Nm).
> 2. Refit the link between DI3 and +24V.
> 3. Press STOP/RESET to clear the fault.
>
> If you plan to wire an external device to DI3 later, you would remove the link and wire the normally closed contact of that device between DI3 and +24V instead. But for now with nothing on the control terminals, the link must be fitted.

### T-015 (answer; answered)

Question: Power went off on site while I was halfway through saving a parameter. Now it comes up with E-15 and won't run. How do I get it back, and what exactly will I lose if I do the reset to defaults?

Model decision: answer; used_article_ids: KB-015, KB-028

Answer shown to the user:

> E-15 means the stored parameter values could not be read or written correctly. This can happen when the supply is switched off while a parameter is being saved.
>
> To get the drive back:
>
> 1. Switch the supply off, wait 5 minutes, then switch it on again.
> 2. If E-15 returns, restore the factory defaults by setting P-15 to 1 and pressing ENTER.
> 3. The display shows dEF for a few seconds and then returns to the flashing frequency. P-15 returns to 0 by itself.
>
> What you will lose and what you keep:
>
> A restore sets parameters P-01 to P-54 back to their factory values. The fault history in P-55 to P-59 is kept.
>
> After the restore:
> - The control source returns to the keypad (P-01 = 0, P-02 = 0).
> - Ramp times return to 10.0 s and the maximum frequency to 50.0 Hz.
> - The motor data is lost. You must re-enter P-16 to P-20 and repeat the auto-tune with P-21.
> - Any other settings for your application will be lost and must be re-entered.
>
> To avoid this in future, keep a written record of the parameter settings for each drive so they can be re-entered after a restore. Do not switch off the supply while the display is still showing a value being saved.
>
> If E-15 returns after restoring the factory defaults, or if it appears more than once, contact Voltrix Drives support. Have the drive rating, frame size and a note of what was happening when the fault appeared.

### T-016 (answer; escalated, insufficient_context)

Question: E-16 on a 5.5 kW unit. how many fans has this size got and whats the procedure to swap them, do i need to do both

Model decision: insufficient_context; used_article_ids: –

### T-017 (answer; answered)

Question: Just unpacked a new VX-200. There's a short wire fitted between two of the control terminals from the factory - is that meant to be there? What else should have been in the box?

Model decision: answer; used_article_ids: KB-017

Answer shown to the user:

> Yes, the factory-fitted wire link is meant to be there. It connects terminals DI3 and +24V.
>
> What should be in the box:
>
> - One VX-200 drive with its terminal cover fitted.
> - A printed quick-start guide.
> - A factory-fitted wire link between terminals DI3 and +24V.

### T-018 (answer; answered)

Question: short of space in the panel. how much gap does the drive need round it and can i mount it on its side to fit

Model decision: answer; used_article_ids: KB-018

Answer shown to the user:

> The VX-200 needs the following clearances around it:
>
> - Above the drive: 100 mm
> - Below the drive: 100 mm
> - Each side: 50 mm
>
> Do not mount the drive on its side, flat on its back or upside down. The drive must be mounted vertically on a flat, solid metal back plate, with the keypad facing forward and the fan at the bottom. Cooling air is drawn in at the bottom and leaves at the top.
>
> Mounting it on its side will prevent proper cooling and lead to fault E-07.

### T-019 (answer; answered)

Question: What is the highest air temperature the drive is allowed to run in? Our cabinets get pretty hot in summer. And is that the room temperature or the temperature inside the cabinet?

Model decision: answer; used_article_ids: KB-018

Answer shown to the user:

> The highest air temperature the drive is allowed to run in is 50 °C. Above 50 °C, do not operate the drive.
>
> This is the temperature inside the cabinet, not the room temperature. Measure the temperature inside the cabinet, not in the room. Fit cabinet ventilation if needed.
>
> The drive gives its full rating when the air at its inlet is between −10 °C and +40 °C. Between 40 °C and 50 °C the output current must be reduced by 2.5 % for each degree above 40 °C.

### T-020 (answer; answered)

Question: there are two terminals marked DC+ and DC- next to the power terminals. what are they for, can i connect anything to them?

Model decision: answer; used_article_ids: KB-019, KB-034

Answer shown to the user:

> DC+ and DC− are DC bus measuring points. Do not connect anything to them.
>
> These terminals stay charged at a dangerous voltage after the supply is switched off. With a 400 V supply the DC bus is at about 565 V DC. You can use them only to measure the voltage with a voltmeter to confirm the drive is safe before working on it. After isolating the supply, wait 5 minutes and then confirm with a suitable voltmeter that the voltage between DC+ and DC− is below 50 V DC before touching any terminal.

### T-021 (answer; escalated, insufficient_context)

Question: Want to add a speed pot on the panel door. Which terminals does it go on and what value pot do I need?

Model decision: answer; used_article_ids: KB-020

Rejected draft (failed_check grounding, never shown):

> The speed potentiometer connects to three terminals: +10V, AI1 and AGND.
>
> Use a 10 kΩ potentiometer.
>
> You also need to set P-02 to 1 so the drive takes its speed reference from analog input AI1.
>
> Tighten the control terminals to 0.5 Nm.

### T-022 (answer; answered)

Question: we have a 4-20mA speed signal coming from the control room. where does it land on the drive and what do i need to set so the drive actually follows it and starts from a remote contact

Model decision: answer; used_article_ids: KB-027, KB-020

Answer shown to the user:

> The 4–20 mA speed signal connects to analog input AI2 on the drive.
>
> To make the drive follow the signal and start from a remote contact, set these parameters:
>
> 1. Set P-01 to 1. This makes the drive take the start and stop command from the digital inputs DI1 (run forward) and DI2 (run reverse) instead of the keypad.
>
> 2. Set P-02 to 2. This makes the drive take the speed reference from AI2 (4–20 mA).
>
> The speed reference is scaled between the minimum frequency P-03 and the maximum frequency P-04.
>
> When P-01 is 1, the motor starts as soon as DI1 or DI2 is connected to +24V. Make sure the machine is safe before changing the setting.
>
> For the wiring: connect the 4–20 mA signal to AI2 and connect the common to AGND. Use screened cable and connect the screen at the drive end only. Tighten the control terminals to 0.5 Nm.

### T-023 (answer; answered)

Question: Screened cables - do I earth the screen at one end or both? Asking for the motor cable and also the analog signal cable, heard different things from different people.

Model decision: answer; used_article_ids: KB-021

Answer shown to the user:

> Motor cable screen: Connect the screen to earth at both ends - at the drive and at the motor terminal box. Clamp the screen all the way round with a metal clamp. Do not twist the screen into a long tail.
>
> Analog signal cable screen: Connect the control cable screen to earth at the drive end only.
>
> This applies to the analog inputs AI1, AI2 and the analog output AO1.

### T-024 (answer; answered)

Question: about to switch on a newly installed drive for the first time. is there a list of things to check before i do, and what should the display look like if all is ok?

Model decision: answer; used_article_ids: KB-022

Answer shown to the user:

> Yes, work through the pre-power-up checklist before applying the supply to a newly installed VX-200.
>
> Checks with the supply isolated:
>
> 1. The drive rating label matches the motor nameplate and the supply (3-phase 380–480 V AC, 50/60 Hz).
> 2. The drive is mounted vertically with 100 mm clear above and below and 50 mm on each side.
> 3. The mains supply is connected to L1, L2, L3 and the motor to U, V, W. The mains must never be connected to U, V, W.
> 4. Both PE terminals are connected and earth continuity has been measured.
> 5. Power terminals are tightened to 1.2 Nm (frame A) or 2.5 Nm (frame B); control terminals to 0.5 Nm.
> 6. The link between DI3 and +24V is fitted, or an external fault device is wired there.
> 7. No tools, wire strands or swarf are left in the drive or cabinet.
> 8. The terminal cover is fitted.
> 9. The motor and machine are safe to turn, and people are clear of the machine.
>
> First power-up:
>
> 1. Make sure no run command is present.
> 2. Switch on the supply.
> 3. The display lights and shows `0.0` flashing. The FAULT LED is off.
> 4. If a fault code appears, note it and look up the matching fault article.

### T-025 (answer; answered)

Question: how do i change a setting on this thing. pressed MENU, got P-01 on the screen, now stuck

Model decision: answer; used_article_ids: KB-023

Answer shown to the user:

> You are in the parameter menu. Here is how to change a setting:
>
> 1. Press ▲ or ▼ to reach the parameter you want. Parameters run from P-01 to P-60.
> 2. Press ENTER. The display shows the present value.
> 3. Press ▲ or ▼ to change the value. Hold the key to change it quickly.
> 4. Press ENTER to save, or MENU to leave without saving.
> 5. Press MENU again to return to the frequency display.

### T-026 (answer; answered)

Question: The green RUN button on the front does nothing at all, but the stop button still works. There's a light lit up labelled REMOTE. Is the keypad broken?

Model decision: answer; used_article_ids: KB-027, KB-023

Answer shown to the user:

> The keypad is not broken. The REMOTE LED being on means the drive is controlled from the terminals, not the keypad. When P-01 is set to 1, the RUN key has no effect and the REMOTE LED is on. The STOP/RESET key still stops the motor.
>
> To use the RUN button again, change P-01 back to 0 (keypad control):
>
> 1. Press MENU. The display shows a parameter number.
> 2. Press ▲ or ▼ to reach P-01.
> 3. Press ENTER. The display shows the present value (1).
> 4. Press ▲ or ▼ to change the value to 0.
> 5. Press ENTER to save.
> 6. Press MENU again to return to the frequency display.
>
> After this change, the REMOTE LED will turn off and the RUN button will work again.

### T-027 (answer; answered)

Question: Swapped the motor for a new one today. What do I have to put into the drive for the new motor, and does the shaft turn during the tuning? Need to know if the guards have to be back on.

Model decision: answer; used_article_ids: KB-024, KB-022

Answer shown to the user:

> You need to enter the motor nameplate data into these parameters:
>
> - P-16: Motor rated voltage (V)
> - P-17: Motor rated current (A)
> - P-18: Motor rated frequency (Hz)
> - P-19: Motor rated speed (rpm)
> - P-20: Motor rated power (kW)
>
> Read the values from the nameplate for the connection (star or delta) actually used.
>
> After entering the motor data, run the auto-tune by setting P-21 to 1 and pressing ENTER, then press RUN. The display shows `tUnE`.
>
> The motor does not rotate during auto-tune, but it is energised. The auto-tune takes about 30 seconds. When the display returns to the flashing frequency, the auto-tune is complete.
>
> Since the motor does not rotate during tuning, the guards do not need to be removed for the auto-tune itself. However, after tuning is complete, you must start the motor at a low frequency (for example 5 Hz) and check the direction of rotation before running at full speed. For this test run, make sure the motor and machine are safe to turn and people are clear of the machine.

### T-028 (answer; answered)

Question: accel time question. if i set P-05 to 10 is that 10 seconds to whatever speed i ask for, or 10 seconds to top speed?

Model decision: answer; used_article_ids: KB-025

Answer shown to the user:

> P-05 is the time the drive takes to raise the output from 0 Hz to the maximum frequency in P-04. So if you set P-05 to 10 seconds, that is 10 seconds to reach the top speed (P-04), not to whatever speed you ask for.
>
> A change over part of the range takes a proportional part of the time. For example, with P-04 at 50.0 Hz and P-05 at 10.0 s, going from 0 to 25 Hz takes 5 seconds.

### T-029 (answer; answered)

Question: Our pump must never run slower than about 20 Hz even if the speed signal drops to zero. Which parameter does that?

Model decision: answer; used_article_ids: KB-026

Answer shown to the user:

> Use parameter P-03 (Minimum frequency) to set the lowest speed the pump can run at. Set P-03 to 20.0 Hz. With this setting, even if the speed signal drops to zero, the pump will not run slower than 20.0 Hz as long as a run command is present.
>
> Stop the motor before changing P-03.

### T-030 (answer; escalated, insufficient_context)

Question: i put the max frequency up from 50 to 70 last week and since then the drive trips with E-01 on start. didnt touch anything else. why would that do it?

Model decision: insufficient_context; used_article_ids: –

### T-031 (answer; answered)

Question: how do i see what the last few trips were? and can the list be wiped afterwards

Model decision: answer; used_article_ids: KB-028

Answer shown to the user:

> To see the last few trips (faults):
>
> 1. Press MENU.
> 2. Go to P-55 with ▲ or ▼.
> 3. Press ENTER. The display shows a code from E-01 to E-16, or ---- if nothing is stored.
>
> The VX-200 stores the last 5 faults. They are kept when the supply is switched off.
>
> P-55 shows the most recent fault.
> P-56 shows the second most recent fault.
> P-57 shows the third most recent fault.
> P-58 shows the fourth most recent fault.
> P-59 shows the oldest stored fault.
>
> To clear the fault history:
>
> 1. Set P-60 to 1 and press ENTER.
>
> When a sixth fault occurs, the oldest entry is automatically dropped.

### T-032 (answer; answered)

Question: Inherited a drive off another machine, no idea what the previous settings are. How do I wipe it back to how it left the factory, and what do I then need to set up again before running our motor?

Model decision: answer; used_article_ids: KB-028

Answer shown to the user:

> To restore the drive to factory defaults:
>
> 1. Stop the motor.
> 2. Write down the present settings if they may be needed again.
> 3. Press MENU and go to P-15.
> 4. Press ENTER, set the value to 1 and press ENTER again.
> 5. The display shows dEF for a few seconds and then returns to the flashing frequency. P-15 returns to 0 by itself.
>
> After the restore, you need to set up the following before running your motor:
>
> 1. Re-enter the motor nameplate data in P-16 to P-20.
> 2. Repeat the auto-tune with P-21, as described in the quick-start commissioning article.
> 3. Re-enter any other settings for your application.
>
> The restore sets parameters P-01 to P-54 back to their factory values. The control source returns to the keypad (P-01 = 0, P-02 = 0), ramp times return to 10.0 s and the maximum frequency to 50.0 Hz. The fault history in P-55 to P-59 is kept.
>
> Keep a written record of the parameter settings for each drive so they can be re-entered after a restore.

### T-033 (answer; answered)

Question: Putting together our PM plan. What routine maintenance do these drives need and how often?

Model decision: answer; used_article_ids: KB-029

Answer shown to the user:

> The VX-200 needs little maintenance, but regular checks prevent most overheating and connection faults. Shorten the intervals below in dusty, hot or humid locations.
>
> Monthly:
> - Visual check: display normal, no fault codes, fan running, no unusual noise or smell (supply on)
> - Check the cabinet temperature and the cabinet filters (supply on)
>
> Every 6 months:
> - Clean the heatsink and air vents (supply isolated)
>
> Every 12 months:
> - Inspect and re-tighten the power and control terminals (supply isolated)
> - Inspect cables for damage and discolouration (supply isolated)
> - Read and record the fault history in P-55 to P-59 (supply on)
>
> Every 3 years:
> - Replace the cooling fan (supply isolated)
>
> Before any task with the supply isolated:
> 1. Stop the motor.
> 2. Isolate the supply and lock it off.
> 3. Wait 5 minutes for the DC bus to discharge.
> 4. Confirm there is no voltage before touching any terminal.
>
> Keep a log for each drive with the date, the task carried out, the fault history and a record of the parameter settings. A record of the settings makes it quick to re-enter them after a restore of factory defaults.

### T-034 (answer; answered)

Question: ok to blow the drive out with the workshop airline? and can i use contact cleaner spray on the fins, theyre greasy

Model decision: answer; used_article_ids: KB-030

Answer shown to the user:

> Do not use the workshop airline or contact cleaner spray on the drive.
>
> For compressed air: Use only dry, oil-free compressed air at low pressure, if available. If you use compressed air, blow from the top of the drive downward, against the normal air flow, so the dust leaves through the fan inlet. Hold the fan blades still while blowing, so the fan is not spun too fast.
>
> For cleaning: Do not use water, solvents or cleaning sprays. Use a soft, dry brush and a vacuum cleaner with a plastic nozzle instead. Brush the heatsink fins and vacuum the dust away as it loosens.

### T-035 (answer; answered)

Question: fitting a replacement fan. theres an arrow moulded on it - which way should that face? dont want to put it in backwards

Model decision: answer; used_article_ids: KB-031

Answer shown to the user:

> The arrow on the new fan must point up into the drive, so that air is blown from the bottom to the top.

### T-036 (answer; answered)

Question: During the yearly check I found one of the incoming supply terminals has gone brown and the insulation next to it looks a bit melted. Screw wasn't very tight. Can I just nip it up and carry on?

Model decision: answer; used_article_ids: KB-032

Answer shown to the user:

> No. A discoloured terminal has been running hot and the insulation damage shows overheating. You must cut the conductor back to clean copper and reconnect it.
>
> Follow these steps:
>
> 1. Stop the motor.
> 2. Isolate the supply and lock it off.
> 3. Wait 5 minutes for the DC bus to discharge.
> 4. Remove the terminal cover.
> 5. Confirm with a suitable voltmeter that there is no voltage on L1, L2, L3 and less than 50 V DC between DC+ and DC−.
> 6. Cut the conductor back to clean copper and reconnect it.
> 7. Re-tighten using a torque screwdriver. For incoming supply terminals (L1, L2, L3): use 1.2 Nm on frame A (0.75–2.2 kW) or 2.5 Nm on frame B (4–7.5 kW). Do not exceed these values. Overtightening damages the terminal.
> 8. Refit the terminal cover, restore the supply and confirm the drive powers up without a fault.
> 9. Record the inspection in the maintenance log.
>
> If the terminal block itself is damaged, contact Voltrix Drives support.

### T-037 (answer; answered)

Question: got a spare vx200 thats been sat on the stores shelf about 18 months, never powered. can i just fit it and run?

Model decision: answer; used_article_ids: KB-033

Answer shown to the user:

> No. The drive has been in storage for 18 months without power, so you must re-form the DC bus capacitors before running it.
>
> Re-forming procedure:
>
> 1. Install and wire the drive as normal, or connect only the supply to L1, L2, L3 and PE.
> 2. Make sure no run command is present.
> 3. Switch on the supply.
> 4. Leave the drive powered for at least 1 hour without starting the motor.
> 5. The drive is then ready for normal commissioning.
>
> The DC bus capacitors slowly lose their internal insulating layer when left without voltage. If full load is applied straight after long storage, the capacitors can be damaged. Re-forming restores the layer by applying voltage with no load for a period.

### T-038 (answer; answered)

Question: How long do I have to wait after turning the supply off before I can touch the terminals? Display goes dark almost straight away so I assume its dead by then.

Model decision: answer; used_article_ids: KB-034

Answer shown to the user:

> Wait 5 minutes after switching off the supply before touching any terminal.
>
> A dark display does not prove the drive is safe. The VX-200 contains DC bus capacitors that stay charged at a dangerous voltage after the supply is switched off. With a 400 V supply the DC bus is at about 565 V DC. The terminals L1, L2, L3, U, V, W, DC+ and DC− remain live whenever the supply is connected, even when the motor is stopped.
>
> After waiting 5 minutes, remove the terminal cover and use a suitable voltmeter to confirm there is no voltage between L1, L2 and L3, and from each to PE, and less than 50 V DC between DC+ and DC−. Only then begin work.

### T-039 (answer; answered)

Question: motor is stopped, i pressed the stop button on the drive. is it safe to re-make the connections on the output terminals now or do i need to do more than that

Model decision: answer; used_article_ids: KB-036, KB-032

Answer shown to the user:

> Do not touch the output terminals yet. You must isolate the drive and wait 5 minutes before touching any terminal. The STOP button stops the motor but does not isolate the drive. The power terminals stay live.
>
> After you have isolated the drive and waited 5 minutes, confirm with a suitable voltmeter that there is no voltage on L1, L2, L3 and less than 50 V DC between DC+ and DC−. Then it is safe to work on the output terminals.

### T-040 (answer; answered)

Question: what does the sticker with the lightning bolt and '5 min' on the front cover mean

Model decision: answer; used_article_ids: KB-035

Answer shown to the user:

> The sticker with the lightning flash and "5 min" is on the front of the terminal cover. It means the DC bus capacitors stay charged after the supply is switched off. Wait 5 minutes after isolating the supply before touching any terminal, then confirm with a voltmeter that the voltage between DC+ and DC− is below 50 V DC.

### T-041 (answer; answered)

Question: There is a triangle symbol with wavy lines on the side of the unit. One of the apprentices asked what it means and I wasn't sure.

Model decision: answer; used_article_ids: KB-035

Answer shown to the user:

> The wavy lines in a triangle is a warning symbol for a hot surface. It is located on the side of the drive, near the heatsink. The heatsink becomes hot in operation and can reach 90 °C. Let it cool before cleaning the drive or replacing the fan.

### T-042 (answer; answered)

Question: can we just wire the e-stop button into the external fault input and use that as the emergency stop for the machine? would save putting in a safety relay

Model decision: answer; used_article_ids: KB-036

Answer shown to the user:

> No. The external fault input is not a certified safety function and cannot replace the machine's emergency stop circuit.
>
> The documents state: "Do not rely on the drive's STOP/RESET key or on the external fault input alone as the emergency stop for a machine."
>
> "An emergency stop button may additionally be wired into the DI3 circuit so that the drive reports `E-14` when the button is pressed. This is for indication and does not replace the machine's emergency stop circuit."
>
> The external fault input also does not isolate the drive—the power terminals stay live. It only makes the motor coast to a stop, which is not a certified safety function.
>
> Your machine's emergency stop must be designed from the machine's risk assessment and must follow your site's safety rules. You need a proper safety relay or safety-rated emergency stop system, not just the drive's external fault input.

### T-043 (escalate; escalated, insufficient_context)

Question: how do i check what firmware version the drive is on

Model decision: insufficient_context; used_article_ids: –

### T-044 (escalate; escalated, insufficient_context)

Question: We have two VX-200s that behave slightly differently and suspect one has older software. Is there an update file and what's the procedure to load it onto the drive?

Model decision: insufficient_context; used_article_ids: –

### T-045 (escalate; escalated, insufficient_context)

Question: need to hook the drive up to our plc over modbus. which terminals and what are the comms settings (baud, address)?

Model decision: insufficient_context; used_article_ids: –

### T-046 (escalate; escalated, insufficient_context)

Question: Does the VX-200 have an Ethernet port or an option card so we can read speed and fault status into the control system over the network?

Model decision: insufficient_context; used_article_ids: –

### T-047 (escalate; escalated, insufficient_context)

Question: want the drive to hold constant pressure on a booster pump using a pressure transducer. how do i set up the pid

Model decision: insufficient_context; used_article_ids: –

### T-048 (escalate; escalated, insufficient_context)

Question: We feed a 4-20 mA flow signal into the drive. Can it regulate the motor speed on its own to keep the flow at a setpoint, and which parameters are the gain settings?

Model decision: insufficient_context; used_article_ids: –

### T-049 (escalate; escalated, insufficient_context)

Question: keep getting E-05 on a high inertia load and we cant make the stop any longer. want to fit a braking resistor - where does it connect and what do i set?

Model decision: insufficient_context; used_article_ids: –

### T-050 (escalate; escalated, insufficient_context)

Question: What ohm value and wattage brake resistor is right for the 7.5 kW drive?

Model decision: insufficient_context; used_article_ids: –

### T-051 (escalate; escalated, out_of_scope)

Question: only got 230v single phase in the workshop. can i run the vx200 off that if i just use L1 and L2?

Model decision: out_of_scope; used_article_ids: –

### T-052 (escalate; escalated, out_of_scope)

Question: Site has no three phase available at the pump house. Is there a way to feed the drive from a single phase supply with reduced output, and how much would it need derating?

Model decision: out_of_scope; used_article_ids: –

### T-056 (escalate; escalated, out_of_scope)

Question: Which size VX-200 do I need for a 3 kW conveyor motor that starts fully loaded about 30 times an hour?

Model decision: out_of_scope; used_article_ids: –

### T-057 (escalate; escalated, out_of_scope)

Question: can you work out what decel time i need to stop a 40 kg flywheel from 1450 rpm without tripping

Model decision: out_of_scope; used_article_ids: –

### T-058 (escalate; escalated, out_of_scope)

Question: how much is a replacement fan for the frame B and whats the price of a complete 4 kW drive

Model decision: out_of_scope; used_article_ids: –

### T-059 (escalate; escalated, out_of_scope)

Question: We ordered two drives over three weeks ago and nothing has arrived. When will they be delivered?

Model decision: out_of_scope; used_article_ids: –

### T-060 (escalate; escalated, out_of_scope)

Question: bit off topic but we also have an old inverter from a different manufacturer on the next line showing OC3. any idea what that means?

Model decision: out_of_scope; used_article_ids: –

### T-101 (answer; escalated, insufficient_context)

Question: commissioned new vx200 today, motor running in reverse direction. what is the correct way to fix, change wiring or parameter??

Model decision: insufficient_context; used_article_ids: –

### T-102 (answer; escalated, insufficient_context)

Question: Conveyor fully loaded with material, drive trips immediately on start. Empty conveyor starts fine.

Model decision: insufficient_context; used_article_ids: –

### T-103 (answer; answered)

Question: how many minutes to wait after switching off before i open the front cover to check terminals

Model decision: answer; used_article_ids: KB-034, KB-032

Answer shown to the user:

> Wait 5 minutes after switching off the supply before removing the terminal cover.
>
> The VX-200 contains DC bus capacitors that stay charged at a dangerous voltage after the supply is switched off. With a 400 V supply the DC bus is at about 565 V DC. A dark display does not prove the drive is safe.
>
> **Wait 5 minutes after switching off the supply before touching any terminal.**

### T-104 (answer; answered)

Question: Someone changed many settings and now nobody knows what was set. How to go back to factory settings from keypad?

Model decision: answer; used_article_ids: KB-028

Answer shown to the user:

> To restore factory settings from the keypad:
>
> 1. Stop the motor.
> 2. Write down the present settings if they may be needed again.
> 3. Press MENU and go to P-15.
> 4. Press ENTER, set the value to 1 and press ENTER again.
> 5. The display shows dEF for a few seconds and then returns to the flashing frequency. P-15 returns to 0 by itself.
>
> After a restore:
> - The control source returns to the keypad (P-01 = 0, P-02 = 0).
> - Ramp times return to 10.0 s and the maximum frequency to 50.0 Hz.
> - The motor data is lost. Re-enter P-16 to P-20 and repeat the auto-tune with P-21, as described in the quick-start commissioning article.
>
> The fault history in P-55 to P-59 is kept.

### T-105 (answer; answered)

Question: during rainy season our supply voltage dips sometimes and drive stops with fault. after supply ok it doesnt start again by itself

Model decision: answer; used_article_ids: KB-006

Answer shown to the user:

> When the supply voltage dips, the drive stops and shows a fault. This is likely E-06 (DC bus undervoltage). The drive will not restart automatically after the supply recovers.
>
> To restart the drive after the supply is healthy again:
>
> 1. Press STOP/RESET to clear the fault.
>
> To prevent voltage dips from stopping the drive:
>
> 1. Measure the supply voltage on L1, L2 and L3 with a suitable meter, both with the motor stopped and while it runs.
> 2. Check upstream fuses, the circuit breaker and the isolator.
> 3. Isolate the drive, wait 5 minutes, then re-tighten the L1, L2, L3 terminals (1.2 Nm on frame A, 2.5 Nm on frame B).
> 4. If the voltage drops during acceleration, increase the acceleration time in P-05.
>
> If E-06 appears while the measured supply voltage stays inside the permitted range (380–480 V AC ±10 %), contact Voltrix Drives support. Have the measured voltages, the drive rating and the fault history (P-55 to P-59) ready.

### T-106 (answer; answered)

Question: Drive in cement plant panel trips on high temperature every afternoon. Heatsink looks very dusty. How often should we clean it and what is the fault telling us

Model decision: answer; used_article_ids: KB-030, KB-007

Answer shown to the user:

> Clean the VX-200 every 6 months, or more often in dusty locations. In a cement plant with dust, you should clean it more frequently than 6 months.
>
> The fault E-07 means the heatsink temperature reached the trip level of 90 °C. The drive stops its output, the motor coasts to a stop, the FAULT LED lights and the display flashes E-07. The fault cannot be reset until the heatsink has cooled.
>
> Dust on the heatsink fins and in the air vents reduces cooling and leads to fault E-07. A dusty heatsink is a likely cause of the afternoon trips. Clean the heatsink and vents as follows:
>
> 1. Stop the motor.
> 2. Isolate the supply and lock it off.
> 3. Wait 5 minutes for the DC bus to discharge.
> 4. Let the heatsink cool. It can reach 90 °C in operation.
> 5. Vacuum loose dust from the top vents and from the fan inlet at the bottom of the drive.
> 6. Brush the heatsink fins and vacuum the dust away as it loosens.
> 7. If compressed air is used, blow from the top of the drive downward, against the normal air flow, so the dust leaves through the fan inlet. Hold the fan blades still while blowing, so the fan is not spun too fast.
> 8. Clean or replace the cabinet filters.
> 9. Check that the fan spins freely by hand.
>
> Do not use water, solvents or cleaning sprays. Do not push dust into the drive. Do not use a metal nozzle or tool near the terminals or circuit boards.
>
> After cleaning, restore the supply and confirm the fan runs when the drive runs. Check that the 100 mm clearance above and below the drive and 50 mm on each side are still free.

### T-108 (escalate; escalated, out_of_scope)

Question: We want to run a 15 kW crusher motor. Which VX-200 size should we order and will it handle the starting torque?

Model decision: out_of_scope; used_article_ids: –

### T-109 (escalate; escalated, out_of_scope)

Question: what is the price and delivery time for a spare cooling fan for vx200

Model decision: out_of_scope; used_article_ids: –

### T-110 (escalate; escalated, out_of_scope)

Question: Replacing an old drive of another brand with VX-200. Can you give the matching parameter numbers so we can copy the old settings

Model decision: out_of_scope; used_article_ids: –
