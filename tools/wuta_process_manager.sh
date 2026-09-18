#!/usr/bin/env bash
# Shared lifecycle helpers for the WUTA simulator and hardware launch scripts.

WUTA_RUNTIME_DIR="${WUTA_RUNTIME_DIR:-${WUTA_PROCESS_ROOT}/logs/runtime}"
WUTA_STACK_PID_FILE="${WUTA_RUNTIME_DIR}/active_stack.pid"

_wuta_is_pid() {
    [[ "${1:-}" =~ ^[1-9][0-9]*$ ]]
}

_wuta_is_managed_launch() {
    local pid="$1" command_line
    _wuta_is_pid "${pid}" || return 1
    [[ -r "/proc/${pid}/cmdline" ]] || return 1
    command_line="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
    case "${command_line}" in
        *"ros2 launch simulator_bringup simulator.launch.py"* | \
        *"ros2 launch simulator_bringup fusion_simulator.launch.py"* | \
        *"ros2 launch detection_fusion fusion_hardware.launch.py"*) return 0 ;;
        *) return 1 ;;
    esac
}

_wuta_managed_launch_pids() {
    local pid command_line
    while read -r pid command_line; do
        case "${command_line}" in
            *"ros2 launch simulator_bringup simulator.launch.py"* | \
            *"ros2 launch simulator_bringup fusion_simulator.launch.py"* | \
            *"ros2 launch detection_fusion fusion_hardware.launch.py"*)
                [[ "${pid}" != "$$" ]] && printf '%s\n' "${pid}"
                ;;
        esac
    done < <(ps -eo pid=,args=)
}

_wuta_descendant_pids() {
    local parent="$1" child
    while read -r child; do
        _wuta_is_pid "${child}" || continue
        printf '%s\n' "${child}"
        _wuta_descendant_pids "${child}"
    done < <(pgrep -P "${parent}" 2>/dev/null || true)
}

_wuta_start_wrapper_pid() {
    local launch_pid="$1" parent_pid command_line
    parent_pid="$(ps -o ppid= -p "${launch_pid}" 2>/dev/null | tr -d ' ' || true)"
    _wuta_is_pid "${parent_pid}" || return 0
    [[ -r "/proc/${parent_pid}/cmdline" ]] || return 0
    command_line="$(tr '\0' ' ' < "/proc/${parent_pid}/cmdline" 2>/dev/null || true)"
    case "${command_line}" in
        *"start_simulator.sh"*) printf '%s\n' "${parent_pid}" ;;
    esac
}

_wuta_wait_for_exit() {
    local pid="$1" attempts="$2" index
    for ((index = 0; index < attempts; ++index)); do
        kill -0 "${pid}" 2>/dev/null || return 0
        sleep 0.1
    done
    return 1
}

_wuta_signal_live_pids() {
    local signal_name="$1"
    shift
    local pid
    for pid in "$@"; do
        _wuta_is_pid "${pid}" || continue
        [[ "${pid}" != "$$" ]] || continue
        kill -s "${signal_name}" "${pid}" 2>/dev/null || true
    done
}

wuta_stop_previous_stack() {
    local -a launch_pids=() wrapper_pids=() tracked_pids=() remaining_pids=()
    local pid wrapper_pid registered_pid registered_mode
    declare -A seen=()

    if [[ -r "${WUTA_STACK_PID_FILE}" ]]; then
        read -r registered_pid registered_mode < "${WUTA_STACK_PID_FILE}" || true
        if _wuta_is_managed_launch "${registered_pid:-}"; then
            launch_pids+=("${registered_pid}")
            seen["${registered_pid}"]=1
        fi
    fi

    while read -r pid; do
        _wuta_is_pid "${pid}" || continue
        [[ -n "${seen[${pid}]:-}" ]] && continue
        launch_pids+=("${pid}")
        seen["${pid}"]=1
    done < <(_wuta_managed_launch_pids)

    if (( ${#launch_pids[@]} == 0 )); then
        rm -f "${WUTA_STACK_PID_FILE}"
        return 0
    fi

    echo "Stopping previous WUTA stack: ${launch_pids[*]}"
    for pid in "${launch_pids[@]}"; do
        tracked_pids+=("${pid}")
        wrapper_pid="$(_wuta_start_wrapper_pid "${pid}")"
        if _wuta_is_pid "${wrapper_pid:-}" && [[ -z "${seen[${wrapper_pid}]:-}" ]]; then
            wrapper_pids+=("${wrapper_pid}")
            seen["${wrapper_pid}"]=1
        fi
        while read -r child; do
            [[ -n "${seen[${child}]:-}" ]] && continue
            tracked_pids+=("${child}")
            seen["${child}"]=1
        done < <(_wuta_descendant_pids "${pid}")
    done

    _wuta_signal_live_pids INT "${launch_pids[@]}"
    for pid in "${launch_pids[@]}"; do
        _wuta_wait_for_exit "${pid}" 50 || remaining_pids+=("${pid}")
    done

    if (( ${#remaining_pids[@]} > 0 )); then
        echo "Previous launch did not exit after SIGINT; sending SIGTERM: ${remaining_pids[*]}"
        _wuta_signal_live_pids TERM "${remaining_pids[@]}"
        for pid in "${remaining_pids[@]}"; do
            _wuta_wait_for_exit "${pid}" 20 || true
        done
    fi

    # start_simulator.sh has its own EXIT cleanup. Wait for that wrapper to
    # finish before a new launch starts, otherwise its fallback pkill could
    # race with the new instance.
    remaining_pids=()
    for pid in "${wrapper_pids[@]}"; do
        _wuta_wait_for_exit "${pid}" 40 || remaining_pids+=("${pid}")
    done
    if (( ${#remaining_pids[@]} > 0 )); then
        _wuta_signal_live_pids TERM "${remaining_pids[@]}"
        sleep 1
        _wuta_signal_live_pids KILL "${remaining_pids[@]}"
    fi

    remaining_pids=()
    for pid in "${tracked_pids[@]}"; do
        kill -0 "${pid}" 2>/dev/null && remaining_pids+=("${pid}")
    done
    if (( ${#remaining_pids[@]} > 0 )); then
        _wuta_signal_live_pids TERM "${remaining_pids[@]}"
        sleep 1
        _wuta_signal_live_pids KILL "${remaining_pids[@]}"
    fi

    rm -f "${WUTA_STACK_PID_FILE}"
    echo "Previous WUTA stack stopped."
}

wuta_register_stack() {
    local pid="$1" mode="$2"
    _wuta_is_pid "${pid}" || {
        echo "Cannot register invalid WUTA stack PID: ${pid}" >&2
        return 1
    }
    mkdir -p "${WUTA_RUNTIME_DIR}"
    printf '%s %s\n' "${pid}" "${mode}" > "${WUTA_STACK_PID_FILE}"
}

wuta_clear_stack_registration() {
    local pid="$1" registered_pid registered_mode
    [[ -r "${WUTA_STACK_PID_FILE}" ]] || return 0
    read -r registered_pid registered_mode < "${WUTA_STACK_PID_FILE}" || true
    if [[ "${registered_pid:-}" == "${pid}" ]]; then
        rm -f "${WUTA_STACK_PID_FILE}"
    fi
}
