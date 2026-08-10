for node in app.getChildren():
    inputs = []
    for index in range(node.getMaxInputCount()):
        source = node.getInput(index)
        inputs.append(source.getScriptName() if source is not None else "-")
    print(
        "CODEX_NODE|{0}|{1}|{2}|{3}".format(
            node.getScriptName(),
            node.getPluginID(),
            node.getPosition(),
            ",".join(inputs),
        )
    )
