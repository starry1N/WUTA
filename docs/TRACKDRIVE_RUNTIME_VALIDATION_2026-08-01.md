# Trackdrive runtime validation - 2026-08-01

## Scope

All runs used the Ubuntu VM with 2 vCPUs and the normal simulator launch path:

- `use_track_truth_map:=false`
- `use_ground_truth_localization:=false`
- `launch_ins:=true`
- `launch_localization:=true`
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
jumps when KISS was re-enabled after a blocked interval. It was removed. The
validated chain directly fuses continuous `/kiss/odometry` with INS and retains
the 3-sigma KISS and 5-sigma INS innovation gates.

## Final map and lap matrix

| Track | Online map | Frozen centerline | Explore lap | Race lap(s) | Result |
| --- | --- | --- | ---: | ---: | --- |
| `track2` | 531/531 tracks; blue 265, yellow 266 | 266 points, confidence 0.927 | 115.30 s | 76.46 s | 2/2 FINISH |
| classic `trackdrive` | 381 confirmed, 383 internal from 384 truth | 191 points, confidence 0.973 | 85.15 s | 52.06 s | 2/2 FINISH |
| external track 6 | 149/149 tracks | 85 points, confidence 0.957 | 53.38 s | 31.30 s | 2/2 FINISH |
| external track 7 | 159/159 tracks | 83 points, confidence 0.964 | 43.44 s | 26.84 s | 2/2 FINISH |
| external track 8 | 187/187 tracks | 109 points, confidence 0.976 | 48.59 s | 30.36 s | 2/2 FINISH |
| external track 9 | 196/196 tracks; blue 99, yellow 97 | 101 points, confidence 0.911 | 62.64 s | 38.76 s | 2/2 FINISH |
| `track2`, simulated colors disabled | 531/531 tracks; blue 265, yellow 266 | 266 points, confidence 0.927 | 163.69 s | 76.50 s | 2/2 FINISH |

An earlier full three-lap `track2` run on the same fix completed in 116.60 s,
76.60 s, and 70.94 s, then published a zero-speed command in `FINISH`. A full
classic `trackdrive` run completed in 87.72 s, 52.20 s, and 47.10 s.

## Generalization safeguards

- No code branches on a track name or truth cone position.
- Pose-jump allowance is based on stamped elapsed time and a configurable
  plausible speed, so delayed callbacks at race speed are not treated as jumps.
- Map closure can remove only a small and clearly separated cluster of weak
  tracks. It does not raise the normal publication hit threshold.
- The frozen map is immutable; race-speed spacing and terminal pose resets do
  not trigger mapping recovery.
- Tracks 10 and 11 remain outside this validation by prior scope because their
  adjacent-section geometry is a separate path-selection problem.
