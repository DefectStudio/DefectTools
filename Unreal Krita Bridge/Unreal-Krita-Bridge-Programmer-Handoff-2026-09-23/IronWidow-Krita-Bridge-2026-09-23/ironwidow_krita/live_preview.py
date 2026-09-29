"""Krita local preview sender: one explicit node, debounced full frames, no auto-save."""
import hashlib, http.client, json, threading, time
from pathlib import Path
from krita import Krita
from PyQt5.QtCore import QTimer,QBuffer,QIODevice,Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QApplication
from .context import ROOT

_dialog=None
class LiveDialog(QDialog):
    def __init__(self):
        super().__init__(Krita.instance().activeWindow().qwindow())
        self.setWindowTitle('Iron Widow — Live Preview');self.resize(520,270)
        box=QVBoxLayout(self)
        self.label=QLabel('In Unreal bind a projected mesh. Select a painting layer/group here, then Bind.');self.label.setWordWrap(True);box.addWidget(self.label)
        for label,fn in [('Bind Selected Painting / Reconnect',self.bind),('Full Resync',self.resync),('Commit Painting (does not save KRA)',self.commit),('Stop Sending',self.stop)]:
            b=QPushButton(label);b.clicked.connect(fn);box.addWidget(b)
        self.doc=None;self.node=None;self.binding=None;self.busy=False;self.result=None;self.seq=0;self.last=None;self.candidate=None;self.force=False;self.enabled=False;self.samples=[];self.epoch=0
        self.last_contact=0
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(350)
    def message(self,text): self.label.setText(text)
    def safe_node(self,node):
        if node.type() in ('filelayer','clonelayer'): raise ValueError('Reference/file/clone layers cannot be sent. Bind a separate painting layer/group.')
        for child in node.childNodes(): self.safe_node(child)
    def bind(self):
        try:
            if self.busy: raise ValueError('Wait for the current request before rebinding.')
            doc=Krita.instance().activeDocument();node=doc.activeNode() if doc else None
            if not node or node.type() not in ('paintlayer','grouplayer'): raise ValueError('Select one paint layer or painting group.')
            self.safe_node(node)
            if doc.colorModel()!='RGBA' or doc.colorDepth()!='U8' or doc.colorProfile()!='sRGB-elle-V2-srgbtrc.icc':
                raise ValueError('Prototype requires RGBA 8-bit sRGB-elle-V2-srgbtrc.icc; no silent color conversion.')
            binding=json.loads((ROOT/'live-preview.json').read_text())
            if not binding.get('enabled'): raise ValueError('Bind Selected Projection in Unreal first.')
            if binding['host']!='127.0.0.1' or binding['identity']['project']!=str(ROOT.parent.parent.resolve()).casefold(): raise ValueError('Wrong project or non-local endpoint')
            if [doc.width(),doc.height()]!=[binding['width'],binding['height']]: raise ValueError('Canvas size differs from bound shot')
            self.epoch+=1;self.doc=doc;self.node=node;self.node_id=node.uniqueId();self.binding=binding;self.seq=time.time_ns();self.last=None;self.candidate=None;self.force=True;self.enabled=True
            self.message('Bound '+node.name()+' → '+binding['identity']['shot']+'. Waiting for full resync.')
        except Exception as exc:self.message(str(exc))
    def resync(self):
        if not self.binding:self.bind()
        else:self.enabled=True;self.force=True;self.last=None;self.message('Full resync pending')
    def stop(self):self.enabled=False;self.message('Sending stopped. Use Stop Live Preview in Unreal to restore durable painting.')
    def send(self,operation,data=b'',digest=None):
        if self.busy:return
        self.busy=True;self.result=None;binding=dict(self.binding);epoch=self.epoch;self.seq+=1;seq=self.seq;begin=time.perf_counter()
        def work():
            connection=None
            try:
                connection=http.client.HTTPConnection('127.0.0.1',int(binding['port']),timeout=25)
                connection.request('POST',operation,body=data,headers={'Content-Type':'image/png','X-Token':binding['token'],'X-Session':binding['session'],'X-Sequence':str(seq)})
                response=connection.getresponse();result=json.loads(response.read(65536))
                if response.status!=200 or not result.get('ok'):raise ValueError(result.get('error','Connection rejected'))
                self.result=(epoch,True,result,digest,(time.perf_counter()-begin)*1000,operation)
            except Exception as exc:self.result=(epoch,False,str(exc),None,0,operation)
            finally:
                if connection:connection.close()
        threading.Thread(target=work,daemon=True).start()
    def commit(self):
        if not self.binding or not self.last or self.busy:self.message('Wait for an acknowledged preview, then Commit.');return
        # Commit exactly the last frame acknowledged by Unreal; warn if editing is pending.
        try:
            if self.current_hash()!=self.last:self.force=True;self.message('Painting changed; wait for its preview acknowledgment before Commit.');return
        except Exception as exc:
            self.enabled=False;self.message('Commit refused: '+str(exc));return
        self.enabled=False;self.send('/commit')
    def pixels(self):
        if self.doc not in Krita.instance().documents():raise ValueError('Bound document closed')
        node=self.doc.nodeByUniqueID(self.node_id)
        if not node:raise ValueError('Bound node removed; bind again')
        self.safe_node(node)
        if self.doc.colorProfile()!='sRGB-elle-V2-srgbtrc.icc' or self.doc.colorModel()!='RGBA' or self.doc.colorDepth()!='U8':raise ValueError('Document color space changed')
        if [self.doc.width(),self.doc.height()]!=[self.binding['width'],self.binding['height']]:raise ValueError('Canvas resized')
        return bytes(node.projectionPixelData(0,0,self.doc.width(),self.doc.height()))
    def current_hash(self):return hashlib.sha256(self.pixels()).hexdigest()
    def poll(self):
        if self.result is not None:
            epoch,ok,result,digest,ms,op=self.result;self.result=None;self.busy=False
            if epoch==self.epoch:
                if not ok:self.enabled=False;self.message('Disconnected / rejected: '+result+' — Reconnect to rebind.');return
                self.last_contact=time.monotonic()
                if op=='/status':return
                if op=='/commit':self.last=None;self.message('Painting committed in Unreal. KRA was not saved. Rebind to continue.');return
                self.last=digest;self.samples.append(dict(roundtrip_ms=ms,**result));self.samples=self.samples[-120:]
                self.message('Live: frame %d acknowledged • %.0f ms round trip • KRA unsaved by bridge'%(result['sequence'],ms))
        if not self.enabled or self.busy or QApplication.mouseButtons()!=Qt.NoButton:return
        try:
            begin=time.perf_counter();pixels=self.pixels();digest=hashlib.sha256(pixels).hexdigest()
            if digest==self.last and not self.force:
                if time.monotonic()-self.last_contact>2:self.send('/status')
                return
            if digest!=self.candidate and not self.force:self.candidate=digest;return
            self.force=False
            # Integer Krita RGBA pixels are BGRA; Format_ARGB32 is non-premultiplied BGRA on Windows.
            image=QImage(pixels,self.doc.width(),self.doc.height(),self.doc.width()*4,QImage.Format_ARGB32).copy()
            buffer=QBuffer();buffer.open(QIODevice.WriteOnly)
            if not image.save(buffer,'PNG'):raise ValueError('PNG encoding failed')
            data=bytes(buffer.data());self.encode_ms=(time.perf_counter()-begin)*1000
            self.send('/frame',data,digest)
        except Exception as exc:self.enabled=False;self.message('Preview paused: '+str(exc))
    def closeEvent(self,event):self.enabled=False;super().closeEvent(event)

def open_dialog():
    global _dialog
    if _dialog is None:_dialog=LiveDialog()
    _dialog.show();_dialog.raise_();_dialog.activateWindow()

def install(window=None):
    # During createActions the new window need not be in app.windows() yet.
    # Use the window Krita supplied; enumeration is only for manual hot install.
    windows=[window] if window is not None else Krita.instance().windows()
    for window in windows:
        action=window.createAction('ironwidow_live_preview','Iron Widow: Live Preview...','tools/scripts')
        try:action.triggered.disconnect()
        except TypeError:pass
        action.triggered.connect(open_dialog)
