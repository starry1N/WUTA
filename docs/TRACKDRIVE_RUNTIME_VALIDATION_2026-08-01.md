# Trackdrive runtime validation - 2026-08-01

## Scope

All runs used the Ubuntu VM with 2 vCPUs and the normal simulator launch path:

- `use_track_truth_map:=false`
- `use_ground_truth_localization:=false`
- `launch_ins:=true`
- `launch_localization:=true`
- `fuse_kiss_odometry:=false`
- `launch_rviz:=true`
- `lidar_enable_occlusion:=true`
- `lidar_max_range:=20.0`

Unless noted otherwise, `use_simulated_cone_colors:=true`. Planning consumed only
the online ConeMap and localization pose; no track YAML centerline was supplied.

## Regression diagnosis

With the original scalar Python occlusion loop, `/sim/lidar/visible_cones` ran at
about 1.6 Hz with the older FSD revision and 1.2 Hz with the updated FSD revision.
The updated run lost its local centerline, held the last command, and then stopped.
The vectorized static transform and AABB implementation preserved the reference
visibility decisions and restored 10.0 Hz (observed maximum interval 0.163 s).
`/planning/final_waypoints` then remained at 5.0 Hz (maximum interval 0.285 s).

The incoming experimental `kiss_odom_gate_node` caused 12.44 m and 9.27 m EKF
jumps when KISS was re-enabled after a blocked interval. Directly fusing absolute
KISS and INS poses could still finish three laps, but KISS ended about 5.4 m from
the INS origin; 116 s after FINISH the EKF became non-finite and RViz retained the
resulting exploded driven trajectory. Raw differential KISS also produced a
13.93 m increment, while an earlier re-entry sanitizer experiment produced a
1,681 m EKF excursion near lap one.

The final default therefore keeps KISS running for diagnostics and map saving but
sets `fuse_kiss_odometry:=false`. EKF uses the simulated CG-410 INS absolute pose,
longitudinal velocity, and yaw rate. The optional true setting uses a new sanitizer
that derives only velocity/yaw rate from KISS increments and rejects non-finite,
hard-limit, and INS-inconsistent samples; KISS global pose never enters EKF.

## Final map and lap matrix

| Track | Online map | Frozen centerline | Explore lap | Race lap(s) | Result |
| --- | --- | --- | ---: | ---: | --- |
| `track2`, simulated colors disabled | blue 265, yellow 266 | quality PASS | 162.54 s | 76.36 s / 71.78 s | 3/3 FINISH |
| classic `trackdrive`, simulated colors disabled | blue 189, yellow 190 | quality PASS | 87.76 s | 51.94 s / 46.90 s | 3/3 FINISH |
| external track 6 | 149/149 tracks | 85 points, confidence 0.957 | 53.38 s | 31.30 s | 2/2 FINISH |
| external track 7 | 159/159 tracks | 83 points, confidence 0.964 | 43.44 s | 26.84 s | 2/2 FINISH |
| external track 8 | 187/187 tracks | 109 points, confidence 0.976 | 48.59 s | 30.36 s | 2/2 FINISH |
| external track 9 | 196/196 tracks; blue 99, yellow 97 | 101 points, confidence 0.911 | 62.64 s | 38.76 s | 2/2 FINISH |

The final `track2` run remained stationary for another 160 s after FINISH. EKF
remained finite at `(0.389, 0.020)` and logs contained no NaN or localization
jump. The optional `fuse_kiss_odometry:=true` mode was smoke-tested through the
classic trackdrive first lap and transition into RACE; isolated bad KISS increments
were rejected without a localization jump or non-finite output.

## Generalization safeguards

- No code branches on a track name or truth cone position.
- KISS global pose is never injected into EKF. The optional fusion path is based
  only on checked increments, so it does not assume a shared absolute origin.
- Localization and driven-trajectory publishers reject non-finite values and stop
  producing terminal-state history, preventing stale RViz paths from masking faults.
- Pose-jump allowance is based on stamped elapsed time and a configurable
  plausible speed, so delayed callbacks at race speed are not treated as jumps.
- Map closure can remove only a small and clearly separated cluster of weak
  tracks. It does not raise the normal publication hit threshold.
- The frozen map is immutable; race-speed spacing and terminal pose resets do
  not trigger mapping recovery.
- Tracks 10 and 11 remain outside this validation by prior scope because their
  adjacent-section geometry is a separate path-selection problem.
