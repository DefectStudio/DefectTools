"""
Attach Snap Stage Two Snapper parked wrapper.

Safe debugging state:
- create recorder_sphere
- attach recorder_sphere live to the Blueprint Actor skeletal root socket
- do not bake recorder_sphere
- do not run Stage One cleanup
- do not call Control Rig Snapper
- do not edit Blueprint Actor keys
- do not edit global_ctrl keys

This is intentionally equivalent to the proven setup-only Attach Snap method while keeping the
Stage Two import/call path safe for existing Blueprint/Python buttons.
"""

import importlib
import traceback

import unreal

import flatten_world_position_to_global_ctrl_attach_snap_method as attach_base


LOG_PREFIX = "[AttachSnapStageTwoSnapper]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def run(
    bp_actor_name="",
    skeletal_mesh_name="",
    global_ctrl_name="global_ctrl",
    root_bone_name="root",
    sphere_name="recorder_sphere",
    delete_existing=True,
    prefer_selected_global_ctrl_sequence=True,
    frame_increment=1,
    sphere_visual_scale=0.12,
    run_stage_one_first=False,
    run_snapper=False,
):
    """
    Parked safe state.

    run_stage_one_first and run_snapper are ignored intentionally. They remain in the
    signature so existing Editor Utility Widget / Python calls do not break.
    """
    try:
        global attach_base
        attach_base = importlib.reload(attach_base)

        _log("----- parked live Attach setup called -----")
        _log("This pass creates the live-attached recorder_sphere only.")
        _log("No recorder_sphere bake, no Stage One cleanup, no Control Rig Snapper, no global_ctrl edits.")

        result = attach_base.run(
            bp_actor_name=bp_actor_name,
            skeletal_mesh_name=skeletal_mesh_name,
            global_ctrl_name=global_ctrl_name,
            root_bone_name=root_bone_name,
            sphere_name=sphere_name,
            delete_existing=delete_existing,
            prefer_selected_global_ctrl_sequence=prefer_selected_global_ctrl_sequence,
            bake_recorder_sphere=False,
            frame_increment=frame_increment,
            remove_attach_after_bake=True,
            sphere_visual_scale=sphere_visual_scale,
            write_scale_keys=False,
        )

        if result != "true":
            _log_error("Live recorder_sphere Attach setup failed.")
            return ""

        _log("SUCCESS: recorder_sphere is live-attached and left in place.")
        _log("Expected state: recorder_sphere follows Bungie_Char.root; Blueprint Actor keys and global_ctrl keys are untouched.")
        return "true"
    except Exception:
        _log_error(traceback.format_exc())
        return ""


def reload_and_run(**kwargs):
    return run(**kwargs)
