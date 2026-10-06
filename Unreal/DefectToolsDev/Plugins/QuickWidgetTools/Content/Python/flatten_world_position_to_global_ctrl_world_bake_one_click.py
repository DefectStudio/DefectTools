"""
One-click orchestrator for the proven global_ctrl flattening workflow.

This module does NOT reimplement any math or phase logic. It is an asynchronous
state machine that drives the existing, verified phases of
flatten_world_position_to_global_ctrl_world_bake (the "core") one editor tick
at a time, with settle waits and live-state guards between stages:

    CAPTURE -> settle -> BAKE -> settle -> VALIDATE BAKE -> REBASE -> settle
    -> VALIDATE REBASE -> KEY TIME VALIDATION -> SAVE -> CLEANUP PREVIEW
    -> CLEANUP -> FINAL REPORT

Why ticks: destructive Sequencer edits and their validation must never share a
single synchronous Python call (Sequencer's compiled evaluation graph is not
rebuilt mid-call - proven earlier in this project by a false-positive
validation). Scheduling: unreal.register_slate_post_tick_callback(fn) /
unreal.unregister_slate_post_tick_callback(handle). Each destructive stage is
followed by a settle phase that waits a minimum tick count AND verifies the
live state (channel-shape check + a stability probe that evaluates the control
world transform on consecutive ticks until two samples agree).

Selection-driven, reusable, zero hard-coded names: at start the artist selects
exactly one Blueprint Actor binding + one child Skeletal Mesh binding (+
optionally the control's channels); everything else resolves from the focused
sequence via the core's generic resolver and is pinned into an operation state
file, then re-verified by GUID before every destructive stage. If the sequence
reverts / is reloaded / loses focus mid-run, the run stops immediately.

State persistence: Saved/QuickWidgetTools/flatten_one_click_state.json - the
machine survives module reloads (cancel() works across reloads via the file).

Entry points: run(), dry_run(), status(), cancel(), resume(), plumbing_test().
"""

import importlib
import json
import os
import time as _time
import traceback
import uuid

import unreal

import flatten_world_position_to_global_ctrl_world_bake as core


LOG_PREFIX = "[FlattenOneClick]"
STATE_FILE_NAME = "flatten_one_click_state.json"
MIN_SETTLE_TICKS = 3          # minimum ticks after ANY stage before the next runs
MAX_SETTLE_TICKS = 120        # give up waiting for stability after this many ticks
STABLE_SAMPLES_REQUIRED = 2   # consecutive equal ctrl-world samples = settled
CANCEL_CHECK_EVERY_TICKS = 15
STALE_RUN_SECONDS = 3600      # an "active" state older than this is considered dead

# In-memory handle for the current interpreter (the state FILE is authoritative
# across module reloads; this dict is only for the live callback).
_ACTIVE = {"handle": None, "machine": None}


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} {message}")


def _reload_core():
    global core
    core = importlib.reload(core)


def _now_text():
    return _time.strftime("%Y-%m-%d %H:%M:%S")


def _state_path():
    return os.path.join(core._sidecar_dir(), STATE_FILE_NAME)


def _read_state():
    path = _state_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _write_state(state):
    state["last_update"] = _now_text()
    with open(_state_path(), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=1)


def _tick_api():
    """Verified UE 5.8 editor tick API (probed, not guessed): slate post-tick."""
    register = getattr(unreal, "register_slate_post_tick_callback", None)
    unregister = getattr(unreal, "unregister_slate_post_tick_callback", None)
    if register is None or unregister is None:
        register = getattr(unreal, "register_slate_pre_tick_callback", None)
        unregister = getattr(unreal, "unregister_slate_pre_tick_callback", None)
    return register, unregister


# ---------------------------------------------------------------------------
# Guards and probes (all read-only)
# ---------------------------------------------------------------------------

def _live_context():
    """(capture, resolved, error) for the focused sequence via the core sidecar."""
    capture, error = core._read_capture()
    if capture is None:
        return None, None, error
    resolved, error = core._resolve_from_capture(capture)
    if error:
        return capture, None, error
    return capture, resolved, ""


def _pre_stage_guard(machine, expected_shape):
    """Before every stage: same focused sequence, GUIDs resolve, same identities,
    live channel state matches the expected previous stage, no silent revert."""
    state = machine["state"]
    focused = core._focused_sequence_path()
    if focused != state["sequence_path"]:
        return False, f"focused sequence changed: {focused!r} != target {state['sequence_path']!r}"
    if expected_shape is None:
        return True, ""
    capture, resolved, error = _live_context()
    if error:
        return False, f"context no longer resolves: {error}"
    if capture.get("actor_binding_guid") != state["actor_binding_guid"]:
        return False, (f"capture sidecar actor guid {capture.get('actor_binding_guid')} != "
                       f"operation actor guid {state['actor_binding_guid']}")
    if capture.get("control_name") != state["control_name"]:
        return False, f"control changed: {capture.get('control_name')!r} != {state['control_name']!r}"
    shape, actor_counts, control_counts = core._state_shape(capture, resolved)
    if shape != expected_shape:
        return False, (f"live channel state is {shape!r} but stage expects {expected_shape!r} "
                       f"(actor={actor_counts} control={control_counts}) - the sequence may have "
                       "been reverted/reloaded externally. Stopping; stale flags will not be trusted.")
    return True, ""


def _sample_ctrl_world(machine):
    """Stability probe: evaluates the control world transform at the start frame.
    Forcing this evaluation each tick both exercises and proves re-evaluation."""
    capture, resolved, error = _live_context()
    if error:
        return None
    transforms, _attempts = core._get_world_transforms(
        resolved["sequence"], resolved["control_rig"], capture["control_name"],
        [resolved["start_frame"]], "DISPLAY_RATE",
    )
    if not transforms:
        return None
    location, _rotation = core.diag._transform_loc_rot(transforms[0])
    if location is None:
        return None
    return (round(float(location.x), 4), round(float(location.y), 4), round(float(location.z), 4))


# ---------------------------------------------------------------------------
# Stage implementations. Each returns (ok, fail_action_or_empty, detail).
# fail_action names a rollback stage to run when ok is False.
# ---------------------------------------------------------------------------

def _stage_capture(machine):
    ok = core.diagnose(global_ctrl_name=machine["params"]["global_ctrl_name"]) == "true"
    if not ok:
        return False, "", "diagnose failed (nothing was modified)"
    ok = core.capture_original(global_ctrl_name=machine["params"]["global_ctrl_name"]) == "true"
    return ok, "", "" if ok else "capture failed (nothing was modified)"


def _stage_bake(machine):
    ok = core.bake_flattened() == "true"
    return ok, "ROLLBACK_BAKE" if not ok else "", "" if ok else "bake phase reported failure"


def _stage_validate_bake(machine):
    ok = core.validate_settled() == "true"
    return ok, "ROLLBACK_BAKE" if not ok else "", "" if ok else "settled bake validation FAILED"


def _stage_rebase(machine):
    ok = core.rebase_origin() == "true"
    return ok, "ROLLBACK_REBASE" if not ok else "", "" if ok else "rebase phase reported failure"


def _stage_validate_rebase(machine):
    ok = core.validate_rebase_settled() == "true"
    return ok, "ROLLBACK_REBASE" if not ok else "", "" if ok else "settled rebase validation FAILED"


def _stage_key_times(machine):
    ok = core.validate_key_times() == "true"
    return ok, "ROLLBACK_REBASE" if not ok else "", "" if ok else (
        "key-time validation FAILED (offending keys are listed above); restoring the validated bake")


def _stage_save(machine):
    ok = core.save_sequence() == "true"
    if ok:
        package = state_package(machine)
        if core._package_is_dirty(package):
            return False, "", "save reported success but the package is still dirty"
        machine["state"]["saved"] = True
    return ok, "", "" if ok else "save FAILED (backups will NOT be cleaned up)"


def _stage_cleanup_preview(machine):
    ok = core.cleanup_preview() == "true"
    return ok, "", "" if ok else "cleanup preview failed"


def _stage_cleanup(machine):
    ok = core.cleanup(delete_sidecars=machine["params"]["delete_sidecars"]) == "true"
    if ok:
        machine["state"]["cleanup_complete"] = True
    return ok, "", "" if ok else "cleanup incomplete - remaining backups were reported above; final sequence untouched"


def _stage_rollback_bake(machine):
    machine["state"]["rolled_back"] = "bake"
    ok = core.rollback() == "true"
    return ok, "", "" if ok else "AUTOMATIC ROLLBACK OF BAKE FAILED - inspect manually (backup assets exist)"


def _stage_rollback_rebase(machine):
    machine["state"]["rolled_back"] = "rebase"
    ok = core.rollback_rebase_origin() == "true"
    return ok, "", "" if ok else "AUTOMATIC ROLLBACK OF REBASE FAILED - inspect manually (backup assets exist)"


_STAGE_FUNCTIONS = {
    "CAPTURE": _stage_capture,
    "BAKE": _stage_bake,
    "VALIDATE BAKE": _stage_validate_bake,
    "REBASE": _stage_rebase,
    "VALIDATE REBASE": _stage_validate_rebase,
    "KEY TIME VALIDATION": _stage_key_times,
    "SAVE": _stage_save,
    "CLEANUP PREVIEW": _stage_cleanup_preview,
    "CLEANUP": _stage_cleanup,
    "ROLLBACK_BAKE": _stage_rollback_bake,
    "ROLLBACK_REBASE": _stage_rollback_rebase,
}

# (name, expected live shape BEFORE the stage, destructive - needs settle after)
def _build_stage_plan(params):
    stages = [
        ("CAPTURE", None, True),
        ("BAKE", "baseline", True),
        ("VALIDATE BAKE", "baked", False),
        ("REBASE", "baked", True),
        ("VALIDATE REBASE", "baked", False),
        ("KEY TIME VALIDATION", "baked", False),
    ]
    if params.get("save_final", True):
        stages.append(("SAVE", "baked", False))
    if params.get("cleanup_backups", True):
        stages.append(("CLEANUP PREVIEW", None, False))
        stages.append(("CLEANUP", None, False))
    return stages

# Verification shape after a rollback stage completes.
_ROLLBACK_EXPECTED_SHAPE = {"ROLLBACK_BAKE": "baseline", "ROLLBACK_REBASE": "baked"}


def state_package(machine):
    return str(machine["state"]["sequence_path"]).split(".")[0]


# ---------------------------------------------------------------------------
# The tick-driven machine
# ---------------------------------------------------------------------------

def _finish(machine, success, reason=""):
    machine["finished"] = True  # no later stage completion may be accepted
    state = machine["state"]
    state["active"] = False
    if success:
        state["phase"] = "COMPLETE"
    elif reason == "canceled by user":
        state["phase"] = "CANCELED"
    else:
        state["phase"] = "FAILED"
    state["failure_reason"] = reason
    _write_state(state)
    _unregister()
    if success:
        _final_report(machine)
        _log("COMPLETE")
    else:
        _log_error(f"RUN {state['phase']}: {reason}")
        _log_error(f"operation {state['operation_id']} stopped. rolled_back={state.get('rolled_back')} "
                   f"completed={state.get('completed_phases')}")


def _unregister():
    _register_fn, unregister_fn = _tick_api()
    handle = _ACTIVE.get("handle")
    if handle is not None and unregister_fn is not None:
        try:
            unregister_fn(handle)
        except Exception:
            pass
    _ACTIVE["handle"] = None
    _ACTIVE["machine"] = None


def _on_tick(_delta_seconds):
    machine = _ACTIVE.get("machine")
    if machine is None:
        _unregister()
        return
    # RE-ENTRANCY GUARD: editor operations inside a stage (duplicate_asset, save,
    # etc.) open progress dialogs that PUMP the Slate loop, which fires this
    # callback again mid-stage. Never allow nested execution.
    if machine.get("busy") or machine.get("finished"):
        return
    machine["busy"] = True
    try:
        machine["tick"] += 1
        state = machine["state"]

        # Cross-reload cancel support: honor the state FILE periodically.
        if machine["tick"] % CANCEL_CHECK_EVERY_TICKS == 0:
            disk_state = _read_state()
            if disk_state is not None and disk_state.get("cancel_requested"):
                machine["cancel"] = True
        if machine.get("cancel"):
            _finish(machine, False, "canceled by user")
            return

        mode = machine["mode"]
        if mode == "settle":
            machine["settle_ticks"] += 1
            if machine["settle_ticks"] < MIN_SETTLE_TICKS:
                return
            # Stability probe: two consecutive equal ctrl-world evaluations.
            if machine.get("probe_settle", True):
                sample = _sample_ctrl_world(machine)
                if sample is not None and sample == machine.get("last_sample"):
                    machine["stable_count"] += 1
                else:
                    machine["stable_count"] = 0
                machine["last_sample"] = sample
                settled = machine["stable_count"] >= (STABLE_SAMPLES_REQUIRED - 1)
                if not settled and machine["settle_ticks"] < MAX_SETTLE_TICKS:
                    return
                if not settled:
                    _log_warning(f"settle probe did not stabilize within {MAX_SETTLE_TICKS} ticks; proceeding "
                                 f"(last sample={machine.get('last_sample')})")
            _log(f"Sequencer settled after {machine['settle_ticks']} tick(s).")
            machine["mode"] = "run"
            return

        # mode == "run": execute exactly one stage this tick.
        plan = machine["plan"]
        index = machine["index"]
        if index >= len(plan):
            if machine.get("fail_reason"):
                _finish(machine, False, machine["fail_reason"] + " - automatic rollback completed and verified.")
            else:
                _finish(machine, True)
            return
        name, expected_shape, destructive = plan[index]
        label = f"{index + 1}/{len(plan)}"

        ok, reason = _pre_stage_guard(machine, expected_shape)
        if not ok:
            _finish(machine, False, f"pre-stage guard for {name} failed: {reason}")
            return

        _log(f"{label} {name} START")
        state["phase"] = name
        _write_state(state)
        stage_ok, fail_action, detail = _STAGE_FUNCTIONS[name](machine)
        if machine.get("finished"):
            # A nested event finished/canceled the run while the stage was
            # executing - discard this stage's result entirely.
            return
        if stage_ok:
            _log(f"{label} {name} PASS")
            state.setdefault("completed_phases", []).append(name)
            state.setdefault("phase_results", {})[name] = "PASS"
            _write_state(state)
            machine["index"] += 1
            machine["mode"] = "settle"
            machine["settle_ticks"] = 0
            machine["stable_count"] = 0
            machine["last_sample"] = None
            machine["probe_settle"] = destructive
            if destructive:
                _log("Waiting for Sequencer evaluation...")
            return

        # Stage failed.
        state.setdefault("phase_results", {})[name] = f"FAIL: {detail}"
        _write_state(state)
        _log_error(f"{label} {name} FAIL: {detail}")
        if fail_action:
            _log_warning(f"scheduling automatic {fail_action}...")
            machine["fail_reason"] = f"{name} failed: {detail}"
            machine["plan"] = [(fail_action, None, True), ("__VERIFY_ROLLBACK__", None, False)]
            machine["rollback_action"] = fail_action
            machine["index"] = 0
            machine["mode"] = "settle"
            machine["settle_ticks"] = 0
            machine["stable_count"] = 0
            machine["last_sample"] = None
            machine["probe_settle"] = False
            return
        _finish(machine, False, f"{name} failed: {detail}")
    except Exception:
        try:
            _finish(machine, False, f"unhandled exception in orchestrator: {traceback.format_exc()}")
        except Exception:
            _unregister()
    finally:
        machine["busy"] = False


def _verify_rollback_stage(machine):
    action = machine.get("rollback_action", "")
    expected = _ROLLBACK_EXPECTED_SHAPE.get(action)
    ok, reason = _pre_stage_guard(machine, expected)
    if ok:
        _log(f"rollback verified: live state is {expected!r} again.")
        return True, "", ""
    return False, "", f"rollback verification failed: {reason}"


_STAGE_FUNCTIONS["__VERIFY_ROLLBACK__"] = _verify_rollback_stage


# ---------------------------------------------------------------------------
# Final report (read-only recompute; does not depend on log scraping)
# ---------------------------------------------------------------------------

def _final_report(machine):
    try:
        state = machine["state"]
        capture, resolved, error = _live_context()
        _log("================ FINAL REPORT ================")
        _log(f"operation: {state['operation_id']}  duration: "
             f"{int(_time.time() - machine['start_seconds'])}s")
        _log(f"sequence: {state['sequence_path']}")
        _log(f"actor: {state['actor_binding_name']} guid={state['actor_binding_guid']} | "
             f"component: {state['component_name']} | rig: {state['rig_class']} | "
             f"control: {state['control_name']}")
        for phase_name, result in (state.get("phase_results") or {}).items():
            _log(f"  {phase_name}: {result}")
        if error:
            _log_warning(f"post-run metric recompute unavailable: {error}")
            return
        start_frame, end_frame = resolved["start_frame"], resolved["end_frame"]
        # World-path errors vs the captured original (integer + half frames).
        records = capture.get("original_ctrl_world") or []
        frames = [record["frame"] for record in records]
        fresh, _a = core._get_world_transforms(
            resolved["sequence"], resolved["control_rig"], capture["control_name"], frames, "DISPLAY_RATE")
        max_loc, max_rot = 0.0, 0.0
        if fresh:
            for record, transform in zip(records, fresh):
                loc, _rot = core.diag._transform_loc_rot(transform)
                loc_error = core._location_error(loc, core._record_loc(record)) or 0.0
                rot_error = core._quat_error_degrees(core._transform_quat(transform), core._record_quat(record)) or 0.0
                max_loc, max_rot = max(max_loc, loc_error), max(max_rot, rot_error)
        _log(f"integer-frame world errors: loc={max_loc:.6f} rot={max_rot:.6f}deg over {len(frames)} frames")
        half_records = capture.get("original_ctrl_world_half") or []
        if half_records:
            ticks_values = [record["tick"] for record in half_records]
            fresh_half, _a = core._get_world_transforms(
                resolved["sequence"], resolved["control_rig"], capture["control_name"],
                ticks_values, "TICK_RESOLUTION")
            h_loc, h_rot = 0.0, 0.0
            if fresh_half:
                for record, transform in zip(half_records, fresh_half):
                    loc, _rot = core.diag._transform_loc_rot(transform)
                    h_loc = max(h_loc, core._location_error(loc, core._record_loc(record)) or 0.0)
                    h_rot = max(h_rot, core._quat_error_degrees(core._transform_quat(transform), core._record_quat(record)) or 0.0)
            _log(f"half-frame world errors:    loc={h_loc:.6f} rot={h_rot:.6f}deg over {len(half_records)} samples "
                 f"(vs pre-rebase reference these may legitimately differ for the BAKE stage)")
        ctrl_values = core._bundle_values_at(resolved["control_bundle"], start_frame)
        actor_values = core._bundle_values_at(resolved["actor_bundle"], start_frame)
        _log(f"actor channels at {start_frame}: {core.base._format_values(actor_values)}")
        _log(f"ctrl local at {start_frame}:    {core.base._format_values(ctrl_values)}")
        key_stats = core._inspect_generated_key_times(resolved, start_frame, end_frame, repair=False)
        _log(f"generated keys: total={key_stats['total']} integer_in_range={key_stats['integer']} "
             f"subframe={key_stats['subframe']} out_of_range={key_stats['out_of_range']}")
        _log(f"saved={state.get('saved')} cleanup_complete={state.get('cleanup_complete')} "
             f"rolled_back={state.get('rolled_back')}")
        _log("==============================================")
    except Exception:
        _log_warning(f"final report recompute failed: {traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def _active_run_check():
    """Returns (active_state or None). A run is active if the file says so and is fresh."""
    state = _read_state()
    if state is None or not state.get("active"):
        return None
    try:
        last = _time.mktime(_time.strptime(state.get("last_update"), "%Y-%m-%d %H:%M:%S"))
        if _time.time() - last > STALE_RUN_SECONDS:
            return None
    except Exception:
        pass
    return state


def run(global_ctrl_name="global_ctrl", save_final=True, cleanup_backups=True, delete_sidecars=False):
    try:
        _reload_core()
        _log("================ one-click run requested ================")
        register_fn, _unregister_fn = _tick_api()
        if register_fn is None:
            _log_error("no supported editor tick API found (register_slate_post_tick_callback missing).")
            return ""
        active = _active_run_check()
        if active is not None or _ACTIVE.get("machine") is not None:
            existing = active or (_ACTIVE["machine"] or {}).get("state", {})
            _log_error(f"REFUSED: another one-click operation is active: "
                       f"id={existing.get('operation_id')} phase={existing.get('phase')}. "
                       "Use status()/cancel() first.")
            return ""

        # Resolve everything from selection + focused sequence (read-only).
        context, error = core._resolve_selection_generic(global_ctrl_name)
        if error:
            _log_error(f"selection resolution failed (nothing was modified): {error}")
            return ""

        # Refuse mid-pipeline starts: a fresh one-click requires the baseline
        # (original) state, or a sequence this tool has never touched.
        existing_capture, _msg = core._read_capture()
        if existing_capture is not None:
            resolved, resolve_error = core._resolve_from_capture(existing_capture)
            if not resolve_error:
                shape, actor_counts, control_counts = core._state_shape(existing_capture, resolved)
                if existing_capture.get("baked") and shape != "baseline":
                    _log_error(
                        f"REFUSED: this sequence is mid-pipeline (sidecar baked=True, live shape={shape!r}). "
                        "Finish or roll back via the step-by-step buttons (phase='next' / 'rollback' / "
                        "'rollback_rebase') before starting a fresh one-click run."
                    )
                    return ""

        package = context["sequence_asset_path"].split(".")[0]
        operation_id = f"oneclick_{_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        params = {
            "global_ctrl_name": context["control_name"],
            "save_final": bool(save_final),
            "cleanup_backups": bool(cleanup_backups),
            "delete_sidecars": bool(delete_sidecars),
        }
        plan = _build_stage_plan(params)
        state = {
            "operation_id": operation_id,
            "active": True,
            "cancel_requested": False,
            "phase": "STARTING",
            "completed_phases": [],
            "phase_results": {},
            "sequence_path": context["sequence_asset_path"],
            "playback_range": [context["start_frame"], context["end_frame"]],
            "display_rate": core._rate_text(core._safe_call(context["sequence"], "get_display_rate")),
            "tick_resolution": core._rate_text(core._safe_call(context["sequence"], "get_tick_resolution")),
            "actor_binding_guid": context["actor_binding_guid"],
            "actor_binding_name": core.attach_base._binding_name(context["actor_binding"]),
            "component_name": context["component_name"],
            "rig_class": context["rig_class"],
            "control_name": context["control_name"],
            "control_name_source": context["control_name_source"],
            "initial_package_dirty": core._package_is_dirty(package),
            "params": params,
            "start_time": _now_text(),
            "failure_reason": "",
            "rolled_back": "",
            "saved": False,
            "cleanup_complete": False,
        }
        _write_state(state)
        machine = {
            "state": state, "params": params, "plan": plan, "index": 0,
            "mode": "run", "tick": 0, "settle_ticks": 0, "stable_count": 0,
            "last_sample": None, "probe_settle": False, "cancel": False,
            "start_seconds": _time.time(),
        }
        _log(f"operation {operation_id} starting: {len(plan)} stages on {state['sequence_path']}")
        _log(f"identities: actor={state['actor_binding_name']!r} component={state['component_name']!r} "
             f"rig={state['rig_class']} control={state['control_name']!r} ({state['control_name_source']})")
        _ACTIVE["machine"] = machine
        _ACTIVE["handle"] = register_fn(_on_tick)
        _log("tick callback registered; stages will run across editor ticks. Use status()/cancel().")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def dry_run(global_ctrl_name="global_ctrl", save_final=True, cleanup_backups=True, delete_sidecars=False):
    """Read-only: resolve everything, verify the tick API, and print the exact
    plan run() would execute. Modifies nothing."""
    try:
        _reload_core()
        _log("================ DRY RUN (read-only) ================")
        register_fn, unregister_fn = _tick_api()
        _log(f"tick API: register={getattr(register_fn, '__name__', None)} "
             f"unregister={getattr(unregister_fn, '__name__', None)} available={register_fn is not None}")
        active = _active_run_check()
        if active is not None:
            _log_warning(f"an operation is currently active: id={active.get('operation_id')} "
                         f"phase={active.get('phase')} - run() would REFUSE.")
        context, error = core._resolve_selection_generic(global_ctrl_name)
        if error:
            _log_error(f"selection resolution failed: {error}")
            _log("run() would refuse to start with this selection. Nothing was modified.")
            return ""
        _log(f"sequence: {context['sequence_asset_path']}")
        _log(f"playback range: [{context['start_frame']},{context['end_frame']}) "
             f"display_rate={core._rate_text(core._safe_call(context['sequence'], 'get_display_rate'))} "
             f"tick_resolution={core._rate_text(core._safe_call(context['sequence'], 'get_tick_resolution'))}")
        _log(f"actor binding: {core.attach_base._binding_name(context['actor_binding'])!r} "
             f"guid={context['actor_binding_guid']}")
        _log(f"skeletal component: {context['component_name']!r}")
        _log(f"control rig: {context['rig_class']} | control: {context['control_name']!r} "
             f"({context['control_name_source']})")
        package = context["sequence_asset_path"].split(".")[0]
        _log(f"initial package dirty: {core._package_is_dirty(package)}")
        params = {"global_ctrl_name": context["control_name"], "save_final": bool(save_final),
                  "cleanup_backups": bool(cleanup_backups), "delete_sidecars": bool(delete_sidecars)}
        plan = _build_stage_plan(params)
        _log(f"planned stages ({len(plan)}):")
        for index, (name, expected_shape, destructive) in enumerate(plan):
            _log(f"  {index + 1}/{len(plan)} {name}"
                 f"{' (destructive, settle-wait after)' if destructive else ''}"
                 f"{f' [requires live state {expected_shape!r}]' if expected_shape else ''}")
        _log(f"settle policy: min {MIN_SETTLE_TICKS} ticks after every stage; destructive stages additionally "
             f"require {STABLE_SAMPLES_REQUIRED} consecutive identical ctrl-world evaluations "
             f"(max {MAX_SETTLE_TICKS} ticks).")
        existing_capture, _msg = core._read_capture()
        if existing_capture is not None:
            resolved, resolve_error = core._resolve_from_capture(existing_capture)
            if not resolve_error:
                shape, _ac, _cc = core._state_shape(existing_capture, resolved)
                _log(f"existing sidecar found: baked={existing_capture.get('baked')} live shape={shape!r}")
                if existing_capture.get("baked") and shape != "baseline":
                    _log_warning("run() would REFUSE: sequence is mid-pipeline. Finish/rollback via the "
                                 "step-by-step buttons first.")
                else:
                    _log("run() would START from stage 1 (CAPTURE).")
        else:
            _log("no existing sidecar - run() would START from stage 1 (CAPTURE).")
        _log("DRY RUN complete. Nothing was modified.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def status():
    try:
        _reload_core()
        state = _read_state()
        if state is None:
            _log("no one-click operation state on disk.")
            return "true"
        if state.get("active"):
            overall = "ACTIVE"
        elif state.get("phase") in ("COMPLETE", "FAILED", "CANCELED"):
            overall = state["phase"]
        else:
            overall = "FAILED" if state.get("failure_reason") else "COMPLETE"
        _log(f"OVERALL: {overall}")
        _log(f"operation {state.get('operation_id')}: active={state.get('active')} "
             f"phase={state.get('phase')} started={state.get('start_time')} "
             f"last_update={state.get('last_update')}")
        _log(f"sequence: {state.get('sequence_path')}")
        _log(f"completed: {state.get('completed_phases')}")
        for phase_name, result in (state.get("phase_results") or {}).items():
            _log(f"  {phase_name}: {result}")
        if state.get("failure_reason"):
            _log_error(f"failure: {state['failure_reason']}")
        _log(f"rolled_back={state.get('rolled_back')} saved={state.get('saved')} "
             f"cleanup_complete={state.get('cleanup_complete')}")
        in_memory = _ACTIVE.get("machine") is not None
        _log(f"ticker live in this interpreter: {in_memory}")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def cancel():
    try:
        machine = _ACTIVE.get("machine")
        if machine is not None:
            machine["cancel"] = True
            _log("cancel requested (in-memory ticker will stop on its next tick).")
        state = _read_state()
        if state is not None and state.get("active"):
            state["cancel_requested"] = True
            _write_state(state)
            _log("cancel flag written to state file (covers a ticker from a previous module load).")
        if machine is None and (state is None or not state.get("active")):
            _log("nothing to cancel.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def resume():
    """Conservative resume after an editor restart or module reload killed the
    ticker mid-run. Only resumes when the recorded next stage's live-state guard
    passes; otherwise refuses with instructions."""
    try:
        _reload_core()
        if _ACTIVE.get("machine") is not None:
            _log_error("a ticker is already live in this interpreter; nothing to resume.")
            return ""
        state = _read_state()
        if state is None or not state.get("active"):
            _log_error("no interrupted active operation found in the state file.")
            return ""
        params = state.get("params") or {}
        plan = _build_stage_plan(params)
        completed = set(state.get("completed_phases") or [])
        index = 0
        for position, (name, _shape, _destructive) in enumerate(plan):
            if name not in completed:
                index = position
                break
        else:
            index = len(plan)
        name = plan[index][0] if index < len(plan) else "<final report>"
        _log(f"resuming operation {state.get('operation_id')} at stage {index + 1}/{len(plan)}: {name}")
        machine = {
            "state": state, "params": params, "plan": plan, "index": index,
            "mode": "settle", "tick": 0, "settle_ticks": 0, "stable_count": 0,
            "last_sample": None, "probe_settle": True, "cancel": False,
            "start_seconds": _time.time(),
        }
        if index < len(plan):
            ok, reason = _pre_stage_guard(machine, plan[index][1])
            if not ok:
                _log_error(f"REFUSING to resume: {reason}. Use the step-by-step phases "
                           "(status/next/rollback) to recover manually.")
                return ""
        register_fn, _u = _tick_api()
        _ACTIVE["machine"] = machine
        _ACTIVE["handle"] = register_fn(_on_tick)
        _log("resume ticker registered.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def plumbing_test(stages=3, ticks_between=5):
    """Read-only self test of the tick machinery: runs no-op stages across real
    editor ticks and writes progress into the state file. Touches no animation."""
    try:
        _reload_core()
        if _ACTIVE.get("machine") is not None or _active_run_check() is not None:
            _log_error("an operation is active; not starting the plumbing test.")
            return ""
        register_fn, _u = _tick_api()
        if register_fn is None:
            _log_error("tick API unavailable.")
            return ""
        test_state = {
            "operation_id": f"plumbing_{uuid.uuid4().hex[:6]}", "active": True,
            "cancel_requested": False, "phase": "PLUMBING", "completed_phases": [],
            "phase_results": {}, "sequence_path": core._focused_sequence_path(),
            "params": {}, "start_time": _now_text(), "failure_reason": "",
            "rolled_back": "", "saved": False, "cleanup_complete": False,
        }

        counter = {"stage": 0, "tick": 0}

        def _test_tick(_delta):
            counter["tick"] += 1
            if counter["tick"] % ticks_between != 0:
                return
            counter["stage"] += 1
            _log(f"plumbing stage {counter['stage']}/{stages} executed on editor tick {counter['tick']}")
            test_state["completed_phases"].append(f"PLUMBING_{counter['stage']}")
            _write_state(test_state)
            if counter["stage"] >= stages:
                test_state["active"] = False
                test_state["phase"] = "COMPLETE"
                _write_state(test_state)
                _log(f"plumbing test COMPLETE after {counter['tick']} ticks.")
                try:
                    _r, unregister_fn = _tick_api()
                    unregister_fn(_ACTIVE["handle"])
                except Exception:
                    pass
                _ACTIVE["handle"] = None
                _ACTIVE["machine"] = None

        _ACTIVE["machine"] = {"state": test_state}
        _ACTIVE["handle"] = register_fn(_test_tick)
        _log(f"plumbing test registered: {stages} no-op stages, one per {ticks_between} ticks.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""
