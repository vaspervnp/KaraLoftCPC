"""Blender scene + render settings for the CPC overscan title screen.

Run inside Blender (via the MCP bridge, or `blender --python this.py`).
It renders a 192x272 PNG which tools/png2screen.py then quantises into
overscan.bin.

The two settings that matter for CPC output:

  resolution 192x272   - one render pixel per Mode 0 pixel, no resampling
  pixel aspect 2:1     - Mode 0 pixels are twice as wide as they are tall.
                         Telling Blender that makes it frame the camera for
                         the shape the monitor actually shows, instead of
                         producing art that looks squashed on hardware.

The camera is orthographic, as plan.md 5 (Module 2) asks for.

Everything is built in a DEDICATED SCENE ("KaraTitle"). The script never
clears or edits whatever else is open in Blender -- switching scenes is
also how you get a clean render without disturbing other work.

The scene built here is a PLACEHOLDER: a pyramid, an eye and a starfield.
Replace build_scene() with the real artwork; configure_render() and the
downstream pipeline stay as they are.
"""
import math

import bpy

WIDTH, HEIGHT = 192, 272
SCENE_NAME = "KaraTitle"


def title_scene():
    """Get, or create, our own scene. Existing scenes are left alone."""
    scene = bpy.data.scenes.get(SCENE_NAME)
    if scene is None:
        scene = bpy.data.scenes.new(SCENE_NAME)
    else:
        for obj in list(scene.collection.objects):     # only ever our own
            scene.collection.objects.unlink(obj)
            if obj.users == 0:
                bpy.data.objects.remove(obj)
    # The EEVEE identifier has changed between Blender versions; pick
    # whichever real-time engine this build actually offers.
    available = scene.render.bl_rna.properties["engine"].enum_items.keys()
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if engine in available:
            scene.render.engine = engine
            break
    return scene


def emissive(name, colour, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*colour, 1.0)
    emit.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def diffuse(name, colour, roughness=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_scene():
    scene = title_scene()
    bpy.context.window.scene = scene       # ops need it to be the active scene
    scene.world = bpy.data.worlds.new("KaraWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.01, 0.01, 0.06, 1.0)
    bg.inputs["Strength"].default_value = 1.0

    # --- the pyramid: a 4-sided cone ---
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=2.6, depth=3.4,
                                    location=(0, 0, 0.2))
    pyramid = bpy.context.object
    pyramid.name = "Pyramid"
    pyramid.rotation_euler = (0, 0, math.radians(45))
    pyramid.data.materials.append(diffuse("Stone", (0.55, 0.42, 0.18), 0.75))

    # --- the all-seeing eye, floating above the capstone ---
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.62, location=(0, -0.3, 2.85))
    eye = bpy.context.object
    eye.name = "Eye"
    eye.scale = (1.0, 0.45, 1.0)
    eye.data.materials.append(emissive("EyeGlow", (1.0, 0.92, 0.45), 6.0))

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.26, location=(0, -0.62, 2.85))
    pupil = bpy.context.object
    pupil.name = "Pupil"
    pupil.data.materials.append(diffuse("Pupil", (0.02, 0.02, 0.05), 0.2))

    # --- ground ---
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1.5))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(diffuse("Sand", (0.30, 0.20, 0.08), 0.9))

    # --- starfield ---
    star_mat = emissive("Star", (1.0, 1.0, 1.0), 12.0)
    rng = [(-5.2, 6.4), (3.9, 7.8), (-4.6, 5.1), (4.8, 6.9), (-2.7, 8.3),
           (2.1, 8.8), (-6.0, 4.3), (5.9, 4.6), (-3.4, 7.0), (1.2, 7.4)]
    for i, (x, z) in enumerate(rng):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(x, 9.0, z))
        star = bpy.context.object
        star.name = f"Star{i:02d}"
        star.data.materials.append(star_mat)

    # --- key light ---
    bpy.ops.object.light_add(type="SUN", location=(-6, -8, 9))
    sun = bpy.context.object
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(52), 0, math.radians(-38))

    # --- orthographic camera ---
    bpy.ops.object.camera_add(location=(0, -14, 2.2))
    cam = bpy.context.object
    cam.name = "TitleCamera"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 9.5
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    return cam


def configure_render(path, scene=None):
    scene = scene or bpy.data.scenes[SCENE_NAME]
    scene.render.resolution_x = WIDTH
    scene.render.resolution_y = HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 2.0        # Mode 0 pixels are wide
    scene.render.pixel_aspect_y = 1.0
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = path
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass


def render(path, scene=None):
    scene = scene or bpy.data.scenes[SCENE_NAME]
    configure_render(path, scene)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    return path
