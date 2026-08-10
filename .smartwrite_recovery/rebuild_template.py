TARGET = (
    "F:/Defect Dropbox/defect/s3bishop/sequences/ZZZ/ZZZ_000_0000/"
    "comp/natron/ZZZ_000_0000_comp_v001.rebuilt.ntp"
)

nodes = {node.getScriptName(): node for node in app.getChildren()}
required = ("Read1", "OCIOColorSpace1", "Premult1", "Write1")
missing = [name for name in required if name not in nodes]
if missing:
    raise RuntimeError("Recovery source is missing nodes: {0}".format(missing))

smart_read = app.createNode("com.portablepipetools.SmartRead")
smart_write = app.createNode("com.portablepipetools.SmartWrite")
if smart_read is None or smart_write is None:
    raise RuntimeError("Could not create SmartRead and SmartWrite")

smart_read.setScriptName("SmartRead1")
smart_write.setScriptName("SmartWrite1")
smart_read.setPosition(*nodes["Read1"].getPosition())
smart_write.setPosition(*nodes["Write1"].getPosition())

nodes["OCIOColorSpace1"].disconnectInput(0)
if nodes["OCIOColorSpace1"].connectInput(0, smart_read) is False:
    raise RuntimeError("Could not connect SmartRead to OCIOColorSpace1")
if smart_write.connectInput(0, nodes["Premult1"]) is False:
    raise RuntimeError("Could not connect Premult1 to SmartWrite")

nodes["Read1"].destroy(False)
nodes["Write1"].destroy(False)

if not app.saveProjectAs(TARGET):
    raise RuntimeError("Natron failed to save rebuilt template")
print("CODEX_RECOVERY_SAVED|{0}".format(TARGET))
