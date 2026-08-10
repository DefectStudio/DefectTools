import SmartReadExt
import SmartWriteExt

SmartReadExt.afterProjectLoaded(app)
SmartWriteExt.afterProjectLoaded(app)

for node in app.getChildren():
    if node.getPluginID() != "com.portablepipetools.SmartWrite":
        continue
    for name in ("exrOutput", "mp4Output", "movOutput", "heroOutput"):
        print("CODEX_OPTION|{0}|{1}".format(name, node.getParam(name).get()))
    for name in ("EXRWrite", "MP4Write", "MOVWrite", "HeroWrite"):
        writer = node.getNode(name)
        print(
            "CODEX_WRITER|{0}|plugin={1}|file={2}|disabled={3}|codec={4}".format(
                name,
                writer.getPluginID(),
                writer.getParam("filename").get(),
                writer.getParam("disableNode").get(),
                writer.getParam("codec").get()
                if writer.getParam("codec") is not None
                else "-",
            )
        )
        codec = writer.getParam("codec")
        if codec is not None:
            matches = [
                "{0}:{1}".format(index, option)
                for index, option in enumerate(codec.getOptions())
                if any(
                    token in option.lower()
                    for token in ("264", "265", "mpeg", "prores")
                )
            ]
            print("CODEX_CODECS|{0}|{1}".format(name, ",".join(matches)))
