"""Scene-linear HDR cubemaps captured at a movable, temporary editor locator.

Spawn a locator, position it, then capture. Only the new TextureCube is saved.
The editor-only locator and transient internal 360 camera are removed after a
successful save; failed or cancelled captures leave the locator for another try.
"""

import datetime
import re

import unreal


OUTPUT_DIRECTORY = "/Game/Materials/Textures/HDRI"
CAPTURE_TAG = "QuickWidgetToolsHDRICapture"
LOCATOR_TAG = "QuickWidgetToolsHDRILocator"
DEFAULT_FACE_SIZE = 4096
WARMUP_FRAMES = 24
_job = None
last_result = None
last_error = None


def _configure_capture(component):
    component.set_editor_property("capture_every_frame", False)
    component.set_editor_property("capture_on_movement", False)
    component.set_editor_property("always_persist_rendering_state", True)
    component.set_editor_property("capture_rotation", False)
    component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR_NO_ALPHA)

    # Cube captures default to disabling GI/reflections, even in a Lumen project.
    # Explicitly opt into the project's renderer, while retaining volume settings.
    settings = component.get_editor_property("post_process_settings")
    if unreal.SystemLibrary.get_console_variable_int_value("r.DynamicGlobalIlluminationMethod") == 1:
        settings.set_editor_property("override_dynamic_global_illumination_method", True)
        settings.set_editor_property("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    if unreal.SystemLibrary.get_console_variable_int_value("r.ReflectionMethod") == 1:
        settings.set_editor_property("override_reflection_method", True)
        settings.set_editor_property("reflection_method", unreal.ReflectionMethod.LUMEN)
    component.set_editor_property("post_process_settings", settings)
    component.set_editor_property("post_process_blend_weight", 1.0)


def _has_tool_tag(actor, actor_class, tag):
    return unreal.SystemLibrary.is_valid(actor) and isinstance(actor, actor_class) and actor.actor_has_tag(tag)


def _resolve_locator(actor_subsystem, world, required=True):
    # EditorActorSubsystem.get_all_level_actors() omits RF_Transient actors.
    locators = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SphereReflectionCapture)
                if _has_tool_tag(actor, unreal.SphereReflectionCapture, LOCATOR_TAG)]
    selected = [actor for actor in actor_subsystem.get_selected_level_actors() if actor in locators]
    if len(selected) == 1:
        return selected[0]
    if len(selected) > 1 or len(locators) > 1:
        raise RuntimeError("Several HDRI locators exist. Select exactly one HDRI_Capture_Locator to use.")
    if locators:
        return locators[0]
    if required:
        raise RuntimeError("Click Spawn Locator and position its sphere reflection capture before making an HDRI.")
    return None


def spawn_locator():
    """Create or select the tool's temporary, movable sphere reflection locator."""
    if _job is not None:
        unreal.log_warning("[MakeCubeMapHDRI] A capture is already running. Please wait before spawning a locator.")
        return None
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world:
        raise RuntimeError("Open a level before spawning an HDRI locator.")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    locator = _resolve_locator(actors, world, required=False)
    if locator is None:
        camera_info = editor.get_level_viewport_camera_info()
        if not camera_info:
            raise RuntimeError("Open a perspective level viewport before spawning an HDRI locator.")
        location, _rotation = camera_info
        with unreal.ScopedEditorTransaction("Spawn HDRI capture locator"):
            locator = actors.spawn_actor_from_class(unreal.SphereReflectionCapture, location, unreal.Rotator(), transient=False)
            if not locator:
                raise RuntimeError("Could not spawn the HDRI capture locator in the editor world.")
            try:
                locator.set_editor_property("tags", [unreal.Name(LOCATOR_TAG)])
                locator.set_editor_property("is_editor_only_actor", True)
                locator.set_actor_label("HDRI_Capture_Locator")
                locator.set_folder_path("HDRI Captures")
                # Keep the editor billboard/radius, but avoid adding a reflection
                # proxy that would change the scene we are about to photograph.
                reflection = locator.get_component_by_class(unreal.SphereReflectionCaptureComponent)
                if not reflection:
                    raise RuntimeError("The HDRI locator has no sphere reflection capture component.")
                reflection.set_visibility(False, False)
            except Exception:
                actors.destroy_actor(locator)
                raise
    actors.set_selected_level_actors([locator])
    unreal.log("[MakeCubeMapHDRI] Position HDRI_Capture_Locator, then click Make CubeMap HDR.")
    return locator


def _capture_actor(actor_subsystem, location):
    with unreal.ScopedEditorTransaction("Create HDRI 360 capture camera"):
        actor = actor_subsystem.spawn_actor_from_class(unreal.SceneCaptureCube, location, unreal.Rotator(), transient=True)
        if not actor:
            raise RuntimeError("Could not create the 360 capture camera in the editor world.")
        try:
            actor.set_editor_property("tags", [unreal.Name(CAPTURE_TAG)])
            actor.set_actor_label("HDRI_360_Capture")
            actor.set_folder_path("HDRI Captures")
            actor.set_actor_location(location, False, False)
        except Exception:
            actor_subsystem.destroy_actor(actor)
            raise
    return actor


def _destroy_tool_actor(actor_subsystem, actor, actor_class, tag):
    if not unreal.SystemLibrary.is_valid(actor):
        return
    if not _has_tool_tag(actor, actor_class, tag):
        raise RuntimeError("Could not remove a temporary HDRI actor because its tool tag or actor type changed.")
    if not actor_subsystem.destroy_actor(actor):
        raise RuntimeError("Could not remove temporary HDRI actor " + actor.get_path_name())


class _CaptureJob:
    def __init__(self, actor, locator, world, face_size, location):
        self.actor = actor
        self.actor_path = actor.get_path_name()
        self.locator = locator
        self.locator_path = locator.get_path_name()
        self.capture_location = [location.x, location.y, location.z]
        self.world = world
        self.face_size = face_size
        self.component = actor.get_component_by_class(unreal.SceneCaptureComponentCube)
        if not self.component:
            raise RuntimeError("The 360 camera has no cube capture component.")
        self.target = None
        self.callback = None
        self.frames = 0
        self.phase = "warmup"
        self.original_cube_single_pass = None

    def start(self):
        # The default 3-by-2 face atlas would be 24576px wide at 8K, beyond
        # DX12's 2D texture limit. Render the faces separately for this job.
        self.original_cube_single_pass = unreal.SystemLibrary.get_console_variable_int_value("r.SceneCapture.CubeSinglePass")
        unreal.SystemLibrary.execute_console_command(self.world, "r.SceneCapture.CubeSinglePass 0")
        _configure_capture(self.component)
        self.target = unreal.QuickWidgetToolsHDRILibrary.create_hdr_cube_render_target(min(512, self.face_size))
        if not self.target:
            raise RuntimeError("Could not allocate the HDR cube render target.")
        self.component.set_editor_property("texture_target", self.target)
        self.callback = unreal.register_slate_post_tick_callback(self.tick)
        unreal.log("[MakeCubeMapHDRI] Warming up 360 capture; final size: {} x {} per face.".format(self.face_size, self.face_size))

    def tick(self, _delta_seconds):
        if _job is not self or self.phase == "saving":
            return
        try:
            editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            if editor_world != self.world or not unreal.SystemLibrary.is_valid(self.actor):
                raise RuntimeError("HDRI capture cancelled because the level or capture camera changed.")
            if self.phase == "warmup":
                self.component.capture_scene()
                self.frames += 1
                if self.frames >= WARMUP_FRAMES:
                    # Re-registering the component here would discard its warmed
                    # Lumen view states. Only replace the target reference.
                    self.component.set_editor_property("texture_target", None, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                    unreal.QuickWidgetToolsHDRILibrary.release_hdr_cube_render_target(self.target)
                    self.target = unreal.QuickWidgetToolsHDRILibrary.create_hdr_cube_render_target(self.face_size)
                    if not self.target:
                        raise RuntimeError("Could not allocate the final HDR cube render target.")
                    self.component.set_editor_property("texture_target", self.target, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                    self.phase = "capture"
                    unreal.log("[MakeCubeMapHDRI] Taking final HDR snapshot...")
            elif self.phase == "capture":
                self.component.capture_scene()
                unreal.QuickWidgetToolsHDRILibrary.flush_hdri_capture_rendering()
                self.phase = "save"
            elif self.phase == "save":
                self.phase = "saving"
                self.save()
        except Exception as error:
            self.fail(error)

    def save(self):
        global last_result
        # Asset compilation/saving can pump Slate ticks. Stop this callback
        # before entering either operation, while keeping the job's busy guard.
        self.stop_callback()
        level_name = re.sub(r"[^A-Za-z0-9_]", "_", self.world.get_name())
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        name = "T_HDRI_{}_{}K_{}".format(level_name, self.face_size // 1024, stamp)
        if not unreal.EditorAssetLibrary.does_directory_exist(OUTPUT_DIRECTORY):
            if not unreal.EditorAssetLibrary.make_directory(OUTPUT_DIRECTORY):
                raise RuntimeError("Could not create " + OUTPUT_DIRECTORY)
        texture = unreal.QuickWidgetToolsHDRILibrary.create_hdr_texture_cube(self.target, OUTPUT_DIRECTORY + "/" + name)
        if not texture:
            raise RuntimeError("Unreal could not convert the captured HDR pixels into a TextureCube.")
        actual_size = unreal.QuickWidgetToolsHDRILibrary.get_hdr_cube_source_size(texture)
        face_count = unreal.QuickWidgetToolsHDRILibrary.get_hdr_cube_source_slice_count(texture)
        if actual_size != self.face_size or face_count != 6:
            raise RuntimeError("Unexpected captured face size: {} (requested {}).".format(actual_size, self.face_size))
        # Pixels now belong to the TextureCube source. Release the large capture
        # target and Lumen histories before waiting for compression and saving.
        self.release_capture_resources()
        if not unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False):
            raise RuntimeError("Could not save HDRI texture " + texture.get_path_name())
        last_result = {"asset_path": texture.get_path_name(), "face_size": actual_size,
                       "capture_actor": self.actor_path, "locator_actor": self.locator_path,
                       "capture_location": self.capture_location}
        self.cleanup(consume_locator=True)
        unreal.EditorAssetLibrary.sync_browser_to_objects([texture.get_path_name()])
        unreal.log("[MakeCubeMapHDRI] SAVED: {} (six {} x {} HDR faces).".format(texture.get_path_name(), actual_size, actual_size))

    def stop_callback(self):
        if self.callback is not None:
            callback, self.callback = self.callback, None
            try:
                unreal.unregister_slate_post_tick_callback(callback)
            except Exception as error:
                unreal.log_warning("[MakeCubeMapHDRI] Could not unregister capture callback: " + str(error))

    def release_capture_resources(self):
        try:
            if unreal.SystemLibrary.is_valid(self.component):
                try:
                    self.component.set_editor_property("texture_target", None)
                    self.component.set_editor_property("always_persist_rendering_state", False)
                except Exception as error:
                    unreal.log_warning("[MakeCubeMapHDRI] Could not reset capture component: " + str(error))
        finally:
            try:
                if self.target is not None:
                    target, self.target = self.target, None
                    unreal.QuickWidgetToolsHDRILibrary.release_hdr_cube_render_target(target)
            finally:
                try:
                    if self.original_cube_single_pass is not None:
                        value, self.original_cube_single_pass = self.original_cube_single_pass, None
                        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
                        unreal.SystemLibrary.execute_console_command(world, "r.SceneCapture.CubeSinglePass " + str(value))
                except Exception as error:
                    unreal.log_warning("[MakeCubeMapHDRI] Could not restore cube capture renderer setting: " + str(error))

    def cleanup(self, consume_locator=False):
        global _job
        try:
            try:
                self.stop_callback()
                self.release_capture_resources()
            finally:
                actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                transaction_name = "Remove completed HDRI capture locator" if consume_locator else "Remove temporary HDRI capture camera"
                with unreal.ScopedEditorTransaction(transaction_name):
                    # Only the camera created for this particular job is removed.
                    # A locator is consumed only after its texture saved to disk.
                    _destroy_tool_actor(actors, self.actor, unreal.SceneCaptureCube, CAPTURE_TAG)
                    if consume_locator:
                        _destroy_tool_actor(actors, self.locator, unreal.SphereReflectionCapture, LOCATOR_TAG)
        finally:
            if _job is self:
                _job = None

    def fail(self, error):
        global last_error
        last_error = str(error)
        try:
            self.cleanup()
        except Exception as cleanup_error:
            last_error += " Cleanup error: " + str(cleanup_error)
        unreal.log_error("[MakeCubeMapHDRI] " + last_error)


def run(face_size=DEFAULT_FACE_SIZE):
    """Capture at the locator's current position; consume it only after saving."""
    global _job, last_result, last_error
    if _job is not None:
        unreal.log_warning("[MakeCubeMapHDRI] A capture is already running. Please wait for it to finish.")
        return False
    if not isinstance(face_size, int) or face_size < 16 or face_size > 8192 or face_size & (face_size - 1):
        raise ValueError("HDRI face size must be a power of two from 16 to 8192.")
    if not hasattr(unreal, "QuickWidgetToolsHDRILibrary"):
        raise RuntimeError("Restart Unreal to load the updated Quick Widget Tools HDRI helper.")
    last_result = None
    last_error = None
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world:
        raise RuntimeError("Open a level before making an HDRI.")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    locator = _resolve_locator(actors, world)
    reflection = locator.get_component_by_class(unreal.SphereReflectionCaptureComponent)
    if not reflection:
        raise RuntimeError("The HDRI locator has no sphere reflection capture component.")
    position = reflection.get_world_location()
    offset = reflection.get_editor_property("capture_offset")
    # Freeze the point at the click, even if the locator is moved while warming.
    # Reflection capture offsets are world-space offsets, matching Unreal's
    # reflection capture origin even when the locator actor has been rotated.
    location = unreal.Vector(position.x + offset.x, position.y + offset.y, position.z + offset.z)
    actor = _capture_actor(actors, location)
    try:
        _job = _CaptureJob(actor, locator, world, face_size, location)
        _job.start()
    except Exception as error:
        if _job is not None:
            _job.fail(error)
        else:
            last_error = str(error)
            with unreal.ScopedEditorTransaction("Remove temporary HDRI capture camera"):
                _destroy_tool_actor(actors, actor, unreal.SceneCaptureCube, CAPTURE_TAG)
        raise
    return True


def cancel():
    """Release an unfinished capture's GPU resources without saving a texture."""
    if _job is not None:
        if _job.phase == "saving":
            unreal.log_warning("[MakeCubeMapHDRI] The texture is being saved; wait for the save to finish.")
            return False
        _job.cleanup()
    return True

