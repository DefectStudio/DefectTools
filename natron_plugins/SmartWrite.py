# -*- coding: utf-8 -*-
# Natron PyPlug
"""Portable Pipe Tools Smart Write PyPlug.

Output paths and checkbox behavior are implemented in SmartWriteExt.py so this
PyPlug structure can remain small and easy to regenerate.
"""

import sys

try:
    from SmartWriteExt import *  # noqa: F403 - Natron's PyPlug extension pattern
except ImportError:
    pass


def getPluginID():
    return "com.portablepipetools.SmartWrite"


def getLabel():
    return "SmartWrite"


def getVersion():
    return 1


def getGrouping():
    return "PortablePipeTools"


def getPluginDescription():
    return "Pipeline-aware multi-format writer for Portable Pipe Tools projects."


def _add_output_checkbox(group, page, name, label, default_value, help_text):
    checkbox = group.createBooleanParam(name, label)
    checkbox.setDefaultValue(default_value)
    checkbox.restoreDefaultValue()
    checkbox.setAnimationEnabled(False)
    checkbox.setAddNewLine(True)
    checkbox.setHelp(help_text)
    page.addParam(checkbox)


def _add_render_button(group, page, name, label, help_text, enabled=True):
    button = group.createButtonParam(name, label)
    button.setHelp(help_text)
    button.setEnabled(enabled)
    button.setAddNewLine(False)
    page.addParam(button)


def createInstance(app, group):
    controls = group.createPageParam("smartWrite", "Smart Write")

    layout_version = group.createIntParam("smartWriteUiVersion", "UI Version")
    layout_version.setDefaultValue(3)
    layout_version.restoreDefaultValue()
    layout_version.setAnimationEnabled(False)
    layout_version.setVisible(False)
    controls.addParam(layout_version)

    _add_render_button(
        group,
        controls,
        "renderAll",
        "Render All",
        "Render every enabled Smart Write output over the project frame range.",
    )

    _add_output_checkbox(
        group,
        controls,
        "exrOutput",
        "EXR Output",
        True,
        "Write a versioned beauty EXR sequence under comp/_output.",
    )
    _add_render_button(
        group,
        controls,
        "renderEXR",
        "Render EXR",
        "Render only the enabled EXR beauty output.",
    )
    _add_output_checkbox(
        group,
        controls,
        "mp4Output",
        "MP4 Output",
        True,
        "Write a versioned beauty MP4 under comp/_output.",
    )
    _add_render_button(
        group,
        controls,
        "renderMP4",
        "Render MP4",
        "Render only the enabled MP4 output.",
    )
    _add_output_checkbox(
        group,
        controls,
        "movOutput",
        "MOV Output",
        False,
        "Write a versioned beauty MOV under comp/_output.",
    )
    _add_render_button(
        group,
        controls,
        "renderMOV",
        "Render MOV",
        "Render only the enabled MOV output.",
        enabled=False,
    )
    _add_output_checkbox(
        group,
        controls,
        "heroOutput",
        "Hero Output",
        True,
        "Write the unversioned hero EXR sequence under comp/_output/_hero.",
    )
    _add_render_button(
        group,
        controls,
        "renderHero",
        "Render Hero",
        "Render only the enabled Hero EXR output.",
    )

    group.getParam("renderAll").setAddNewLine(True)
    for checkbox_name, button_name in (
        ("exrOutput", "renderEXR"),
        ("mp4Output", "renderMP4"),
        ("movOutput", "renderMOV"),
        ("heroOutput", "renderHero"),
    ):
        group.getParam(checkbox_name).setAddNewLine(True)
        group.getParam(button_name).setAddNewLine(False)

    group.setPagesOrder(["smartWrite", "Node", "Settings"])
    group.refreshUserParamsGUI()

    input_node = app.createNode("fr.inria.built-in.Input", 1, group)
    if input_node is None:
        raise RuntimeError("SmartWrite could not create its internal Input node")
    input_node.setScriptName("Input1")
    input_node.setLabel("Input1")
    input_node.setPosition(0, 0)

    writer_specs = (
        ("EXRWrite", "EXR Write", -300),
        ("MP4Write", "MP4 Write", -100),
        ("MOVWrite", "MOV Write", 100),
        ("HeroWrite", "Hero Write", 300),
    )
    for script_name, label, x_position in writer_specs:
        writer = app.createNode("fr.inria.built-in.Write", 1, group)
        if writer is None:
            raise RuntimeError(
                "SmartWrite could not create its internal {0} node".format(label)
            )
        writer.setScriptName(script_name)
        writer.setLabel(label)
        writer.setPosition(x_position, 100)
        writer.connectInput(0, input_node)

    output = app.createNode("fr.inria.built-in.Output", 1, group)
    if output is None:
        raise RuntimeError("SmartWrite could not create its internal Output node")
    output.setScriptName("Output1")
    output.setLabel("Output1")
    output.setPosition(0, 200)
    output.connectInput(0, input_node)

    group.setSubGraphEditable(False)

    try:
        extension_module = sys.modules["SmartWriteExt"]
    except KeyError:
        extension_module = None
    if (
        extension_module is not None
        and hasattr(extension_module, "createInstanceExt")
        and callable(extension_module.createInstanceExt)
    ):
        extension_module.createInstanceExt(app, group)
