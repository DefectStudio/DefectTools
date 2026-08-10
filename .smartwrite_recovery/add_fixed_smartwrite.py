TARGET = (
    "F:/Defect Dropbox/defect/s3bishop/sequences/ZZZ/ZZZ_000_0000/"
    "comp/natron/ZZZ_000_0000_comp_v001.recovered-current-v5.ntp"
)

nodes = {node.getScriptName(): node for node in app.getChildren()}
if "Premult1" not in nodes:
    raise RuntimeError("Recovery source is missing Premult1")
if any(
    node.getPluginID() == "com.portablepipetools.SmartWrite"
    for node in app.getChildren()
):
    raise RuntimeError("Recovery source already contains SmartWrite")

smart_write = app.createNode("com.portablepipetools.SmartWrite")
if smart_write is None:
    raise RuntimeError("Could not create the fixed SmartWrite")
smart_write.setScriptName("SmartWrite1")
smart_write.setPosition(*nodes["Premult1"].getPosition())
if smart_write.connectInput(0, nodes["Premult1"]) is False:
    raise RuntimeError("Could not connect Premult1 to SmartWrite")

if not app.saveProjectAs(TARGET):
    raise RuntimeError("Natron failed to save the recovered template")
print("CODEX_RECOVERY_SAVED|{0}".format(TARGET))
