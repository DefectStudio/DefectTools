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
    return 10


def getGrouping():
    return "PortablePipeTools"


def getPluginDescription():
    return "Pipeline-aware image reader for Portable Pipe Tools projects."


def createInstance(app, group):
    controls = group.createPageParam("smartRead", "Smart Read")

    element = group.createStringParam("element", "Element")
    element.setDefaultValue("beauty")
    element.restoreDefaultValue()
    element.setAnimationEnabled(False)
    element.setHelp(
        "Render element used in version folders named SHOT_ELEMENT_v###."
    )
    controls.addParam(element)

    refresh = group.createButtonParam("refresh", "Refresh")
    refresh.setHelp("Rescan this shot for available versions of the current element.")
    controls.addParam(refresh)

    latest = group.createBooleanParam("latest", "Latest")
    latest.setDefaultValue(True)
    latest.restoreDefaultValue()
    latest.setAnimationEnabled(False)
    latest.setHelp("Automatically use the highest EXR version available for this shot.")
    controls.addParam(latest)

    version = group.createChoiceParam("version", "File")
    version.addOption("No EXR versions found", "")
    version.setAnimationEnabled(False)
    version.setHelp(
        "Available EXR versions for this element. Latest automatically selects "
        "the newest entry when versions are refreshed."
    )
    controls.addParam(version)

    source_missing = group.createBooleanParam("sourceMissing", "Source Missing")
    source_missing.setDefaultValue(False)
    source_missing.restoreDefaultValue()
    source_missing.setAnimationEnabled(False)
    source_missing.setVisible(False)
    controls.addParam(source_missing)

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
