# -*- coding: utf-8 -*-
# Natron PyPlug
"""Portable Pipe Tools Smart Read PyPlug.

This first scaffold deliberately contains only a native Natron Read node and
the public controls needed to prove the PyPlug and GUI structure. Production
path-selection behavior belongs in SmartReadExt.py and smart_read_core.py.
"""

import sys

try:
    from SmartReadExt import *  # noqa: F403 - Natron's PyPlug extension pattern
except ImportError:
    pass


def getPluginID():
    return "com.portablepipetools.SmartRead"


def getLabel():
    return "SmartRead"


def getVersion():
    return 1


def getGrouping():
    return "PortablePipeTools"


def getPluginDescription():
    return "Pipeline-aware image reader for Portable Pipe Tools projects."


def _alias(group, group_param_name, node, node_param_name):
    group_param = group.getParam(group_param_name)
    node_param = node.getParam(node_param_name)
    if group_param is None or node_param is None:
        raise RuntimeError(
            "SmartRead could not connect parameter {0} to Read1.{1}".format(
                group_param_name, node_param_name
            )
        )
    if not group_param.setAsAlias(node_param):
        raise RuntimeError(
            "SmartRead parameter types do not match for {0} and Read1.{1}".format(
                group_param_name, node_param_name
            )
        )


def createInstance(app, group):
    controls = group.createPageParam("smartRead", "Smart Read")

    source_file = group.createFileParam("sourceFile", "File")
    source_file.setSequenceEnabled(True)
    source_file.setHelp("Image sequence or movie read by the internal Natron Read node.")
    controls.addParam(source_file)

    first_frame = group.createIntParam("firstFrame", "First Frame")
    first_frame.setAnimationEnabled(False)
    first_frame.setHelp("First frame available from the source.")
    controls.addParam(first_frame)

    last_frame = group.createIntParam("lastFrame", "Last Frame")
    last_frame.setAnimationEnabled(False)
    last_frame.setHelp("Last frame available from the source.")
    controls.addParam(last_frame)

    group.setPagesOrder(["smartRead", "Node", "Settings"])
    group.refreshUserParamsGUI()

    reader = app.createNode("fr.inria.built-in.Read", 1, group)
    if reader is None:
        raise RuntimeError("SmartRead could not create its internal Read node")
    reader.setScriptName("Read1")
    reader.setLabel("Read1")
    reader.setPosition(0, 0)

    output = app.createNode("fr.inria.built-in.Output", 1, group)
    if output is None:
        raise RuntimeError("SmartRead could not create its internal Output node")
    output.setScriptName("Output1")
    output.setLabel("Output1")
    output.setPosition(0, 100)
    output.connectInput(0, reader)

    _alias(group, "sourceFile", reader, "filename")
    _alias(group, "firstFrame", reader, "firstFrame")
    _alias(group, "lastFrame", reader, "lastFrame")

    group.setSubGraphEditable(False)

    try:
        extension_module = sys.modules["SmartReadExt"]
    except KeyError:
        extension_module = None
    if (
        extension_module is not None
        and hasattr(extension_module, "createInstanceExt")
        and callable(extension_module.createInstanceExt)
    ):
        extension_module.createInstanceExt(app, group)

