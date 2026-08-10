# -*- coding: utf-8 -*-
# Natron PyPlug
"""Portable Pipe Tools Smart Write PyPlug.

This is the initial UI scaffold. The output checkboxes are intentionally not
wired to path or encoding behavior yet.
"""


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


def _add_output_checkbox(group, page, name, label, help_text):
    checkbox = group.createBooleanParam(name, label)
    checkbox.setDefaultValue(False)
    checkbox.restoreDefaultValue()
    checkbox.setAnimationEnabled(False)
    checkbox.setHelp(help_text)
    page.addParam(checkbox)


def createInstance(app, group):
    controls = group.createPageParam("smartWrite", "Smart Write")

    _add_output_checkbox(
        group,
        controls,
        "exrOutput",
        "EXR Output",
        "Enable EXR output. Output behavior will be added in a future revision.",
    )
    _add_output_checkbox(
        group,
        controls,
        "mp4Output",
        "MP4 Output",
        "Enable MP4 output. Output behavior will be added in a future revision.",
    )
    _add_output_checkbox(
        group,
        controls,
        "movOutput",
        "MOV Output",
        "Enable MOV output. Output behavior will be added in a future revision.",
    )
    _add_output_checkbox(
        group,
        controls,
        "heroOutput",
        "Hero Output",
        "Enable hero output. Output behavior will be added in a future revision.",
    )

    group.setPagesOrder(["smartWrite", "Node", "Settings"])
    group.refreshUserParamsGUI()

    input_node = app.createNode("fr.inria.built-in.Input", 1, group)
    if input_node is None:
        raise RuntimeError("SmartWrite could not create its internal Input node")
    input_node.setScriptName("Input1")
    input_node.setLabel("Input1")
    input_node.setPosition(0, 0)

    writer = app.createNode("fr.inria.built-in.Write", 1, group)
    if writer is None:
        raise RuntimeError("SmartWrite could not create its internal Write node")
    writer.setScriptName("Write1")
    writer.setLabel("Write1")
    writer.setPosition(0, 100)
    writer.connectInput(0, input_node)

    output = app.createNode("fr.inria.built-in.Output", 1, group)
    if output is None:
        raise RuntimeError("SmartWrite could not create its internal Output node")
    output.setScriptName("Output1")
    output.setLabel("Output1")
    output.setPosition(0, 200)
    output.connectInput(0, writer)

    group.setSubGraphEditable(False)
