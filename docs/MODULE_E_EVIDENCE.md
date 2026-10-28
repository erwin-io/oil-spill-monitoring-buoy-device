# Module E (IDs 53–68) — implementation and evidence register

Read against the live Development Checklist (2026-10-28); official status is **Not Started** for 53–68 at time of read. This register documents software implementation only, not checklist completion or scientific validation.

| ID | Requirement | Current evidence | Acceptance still missing |
|---|---|---|---|
| 53 | 365nm UV LED Driver | OpticalCycle enforces OFF before/after measurement, including failures | Verified current-limited LED driver, safe reset/boot bias, optical power/timing tests |
| 54 | ZWB2 excitation filter | Design constraint documented | Installed physical filter and visible leakage measurement |
| 55 | Optical cuvette | Sampling interface present | Actual correctly positioned cleanable cuvette |
| 56 | 90-degree geometry | Fixed geometry ID required for calibration | Built dark chamber/90 degree alignment, stray-light test |
| 57 | L39/UV390 detector filter | Design constraint documented | Installed long-pass filter and excitation rejection test |
| 58 | AS7341 integration | drivers/as7341.py SMUX, 6 channels, controlled gain/integration, onboard white LED off; desktop fake I2C test | Hardware ID, bus compatibility, saturation/noise test |
| 59 | UV-OFF background | services/optics.py measures repeat-median UV-OFF spectrum | Physical ambient/dark proof |
| 60 | UV-ON fluorescence | Repeated settled UV-ON median, UV finally OFF | Physical UV timing, stable fluorescence repeat test |
| 61 | Spectral features | Clamped ON-OFF channels, optional clean-water baseline, ratios, slope and total | Validated physical meaningfulness / traceability |
| 62 | Clean-water calibration | baseline_from_runs validates minimum physical runs and geometry ID | Actual repeated distilled + clean seawater scans |
| 63 | Repeatability | Per-channel CV fail-closed bound | Actual repeated fills/washes/drift report |
| 64 | Labeled dataset | CSV schema/training guard and split by run ID | Real independently labeled clean, oil and interference experiments |
| 65 | Random Forest training | tools/train_edge_model.py 32-tree group-split trainer and versioned model export | Real training on final dataset, saved model and accepted evaluation |
| 66 | Evaluation & threshold | Confusion matrices, per-class reports, petroleum false-alert counts, abstention threshold | Hold-out evaluation on physically independent runs and signed threshold |
| 67 | ESP32 inference | services/edge_model.py compact Python interpreter for serialized trees, unit-tested | Real ESP32 deployed model, memory/timing and parity vs scikit-learn predictions |
| 68 | Final classification | NORMAL/PETROLEUM/INTERFERENCE/INCONCLUSIVE with threshold-based abstention | Scientifically validated model deployed and end-to-end physical acceptance |

## Scientific safeguards

Do not train on synthetic/random samples then claim sensor accuracy. No oil label is inferred without a vetted physical model. Dataset should include separate experiment IDs and test batches; train/validation/test must share zero experiment IDs. Record UV driver current, exact cuvette geometry, ZWB2/L39 parts, AS7341 gain/integration, temperature, seawater composition, oil type, experimental concentration and wash/blank controls. Recalibrate after changing optics and version the model+geometry+calibration together. Do not falsely claim ppm quantification or filter-removal performance.

## Operational gate

Until hardware tests and dataset acceptance exist, leave GPIO21 and AS7341 disabled in config.py. Runtime should report SENSOR_NOT_INSTALLED or CALIBRATION_REQUIRED rather than spoofed petroleum/normal data. This is **software built, physical acceptance pending**, not 16/16 Complete.
