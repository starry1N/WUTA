# Trackdrive Lap Timing

`simulation_bridge` measures Trackdrive laps from `/sim/ground_truth`.

The installed `trackdrive.yaml` uses the same physical line for start and
finish: the orange cones define a finite `x=0` line. During a normal clockwise
run, the vehicle may return through that line from positive X toward negative X.
The timer therefore arms when the mission becomes active, waits until the
vehicle has left the timing line region, and then counts either-direction
crossing of the shared line. This prevents the launch/standing-start departure
from being counted as a completed lap.

For courses with separate start and finish lines, such as acceleration, timing
still uses the positive-X crossing direction for both lines.

Validation command:

```bash
cd /path/to/WUTA
./start_simulator.sh --skip-build \
  track_file:=trackdrive mission_mode:=trackdrive \
  use_ground_truth_localization:=false launch_ins:=true \
  launch_localization:=true launch_rviz:=false
```

Expected log evidence after a clean run:

```text
Lap timer armed at shared x=0.000 m line
Shared timing line ready for next crossing at x=0.000 m
Lap complete: ... laps=1/3
Lap complete: ... laps=2/3
Lap complete: ... laps=3/3
Trackdrive complete after 3 laps; publishing /system/mission_complete
```
