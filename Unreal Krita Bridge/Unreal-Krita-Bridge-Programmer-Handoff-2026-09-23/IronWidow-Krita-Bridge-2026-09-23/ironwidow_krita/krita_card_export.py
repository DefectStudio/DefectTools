"""Krita cutout exporter; reads artwork and writes separate versioned exports only."""
import json, uuid, hashlib, time
from pathlib import Path
from krita import Krita, Extension
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QPushButton,QLabel,
    QDoubleSpinBox,QCheckBox,QFileDialog,QMessageBox)

from .context import ROOT,owned
_extension=None

def rgba(doc,node,use_selection=False):
    if node.colorModel()!='RGBA' or node.colorDepth()!='U8':
        raise ValueError('The cutout layer must use RGB/Alpha, 8-bit integer. Convert a copy if needed.')
    w,h=doc.width(),doc.height()
    raw=bytearray(node.projectionPixelData(0,0,w,h))
    if len(raw)!=w*h*4:raise ValueError('Krita did not return a complete RGBA layer.')
    raw[0::4],raw[2::4]=raw[2::4],raw[0::4]
    if use_selection:
        sel=doc.selection()
        if sel is None:raise ValueError('No selection. Refine a selection or export a transparent layer.')
        mask=bytes(sel.pixelData(0,0,w,h))
        if len(mask)!=w*h:raise ValueError('Incomplete selection mask.')
        raw[3::4]=bytes((a*m+127)//255 for a,m in zip(raw[3::4],mask))
    alpha=raw[3::4]; indices=[i for i,a in enumerate(alpha) if a]
    if not indices:raise ValueError('The chosen layer/selection is completely transparent.')
    x0=min(i%w for i in indices);x1=max(i%w for i in indices)+1
    y0=min(indices)//w;y1=max(indices)//w+1
    rect_solid=all(alpha[y*w+x]==255 for y in range(y0,y1) for x in range(x0,x1))
    return w,h,bytes(raw),[x0,y0,x1,y1],rect_solid

def export_node(doc,node,shot_path,anchor=None,card_id=None,use_selection=False,allow_rectangle=False):
    path=owned(shot_path);shot=json.loads(path.read_text(encoding='utf-8'))
    if shot.get('schema')!=1 or shot.get('projection')!='perspective' or not shot.get('map_id'):
        raise ValueError('Choose a saved perspective shot from this bridge.')
    w,h,pixels,bounds,solid=rgba(doc,node,use_selection)
    if [w,h]!=[shot['image_width'],shot['image_height']]:raise ValueError('Canvas dimensions do not match the saved shot.')
    if solid and not allow_rectangle:
        raise ValueError('This is an opaque rectangle, not a transparent cutout. Refine the mask or explicitly allow a rectangular card.')
    anchor=anchor or [(bounds[0]+bounds[2])/2,bounds[3]]
    if not (0<=anchor[0]<=w and 0<=anchor[1]<=h):raise ValueError('Anchor must lie on the canvas.')
    card_id=card_id or 'Card_'+uuid.uuid4().hex
    if not card_id.startswith('Card_') or not card_id[5:].isalnum():raise ValueError('Invalid card identity.')
    folder=ROOT/'cards'/card_id/('Export_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    png=folder/'cutout.png'
    image=QImage(pixels,w,h,w*4,QImage.Format_RGBA8888).copy()
    if not image.save(str(png),'PNG'):raise IOError('Krita could not write cutout PNG.')
    data=dict(schema=1,kind='KritaCutoutCard',id=card_id,shot_manifest=str(path.resolve()),
        shot_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),shot_id=shot['id'],map_id=shot['map_id'],
        canvas_size=[w,h],crop_offset=[0,0],export_size=[w,h],alpha_bounds=bounds,anchor_px=anchor,
        png='cutout.png',png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),
        layer_name=node.name(),source_document=doc.fileName(),selection_applied=use_selection,
        rectangle_explicit=allow_rectangle,created=time.time())
    manifest=folder/'card.json';manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
    latest=ROOT/'cards'/'latest.json';stage=latest.with_suffix('.tmp')
    stage.write_text(json.dumps({'manifest':str(manifest)}),encoding='utf-8');stage.replace(latest)
    return manifest

class CardDialog(QDialog):
    def __init__(self,parent=None,update=False):
        super().__init__(parent);self.setWindowTitle('Unreal Cutout Card');self.resize(650,540)
        self.doc=Krita.instance().activeDocument()
        if not self.doc:raise ValueError('Open a document first.')
        self.node=self.doc.activeNode();self.shot=None;self.card_id=None
        layout=QVBoxLayout(self)
        note=QLabel('Export the active layer with alpha. A selection only clips pixels; it does not remove the background.\nThe painting and its layers are left intact. Choose the exact shot used to paint this canvas.');note.setWordWrap(True);layout.addWidget(note)
        choose=QPushButton('Choose saved shotâ€¦');choose.clicked.connect(self.choose_shot);layout.addWidget(choose)
        self.label=QLabel('No source shot chosen');layout.addWidget(self.label)
        self.selection=QCheckBox('Apply current refined selection');layout.addWidget(self.selection)
        self.rectangle=QCheckBox('Allow an intentional opaque rectangular card');layout.addWidget(self.rectangle)
        w,h,pix,bounds,_=rgba(self.doc,self.node)
        self.preview=QLabel();self.preview.setStyleSheet('background:#454545');self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setPixmap(QPixmap.fromImage(QImage(pix,w,h,w*4,QImage.Format_RGBA8888).copy()).scaled(600,260,Qt.KeepAspectRatio,Qt.SmoothTransformation));layout.addWidget(self.preview)
        form=QFormLayout();self.ax=QDoubleSpinBox();self.ay=QDoubleSpinBox()
        self.ax.setRange(0,w);self.ay.setRange(0,h);self.ax.setValue((bounds[0]+bounds[2])/2);self.ay.setValue(bounds[3])
        form.addRow('Anchor X (canvas pixels)',self.ax);form.addRow('Anchor Y (canvas pixels)',self.ay);layout.addLayout(form)
        self.selection.toggled.connect(self.refresh_selection)
        if update:
            path,_=QFileDialog.getOpenFileName(self,'Choose existing card to update',str(ROOT/'cards'),'Card metadata (card.json)')
            if not path:raise ValueError('Update cancelled.')
            old=json.loads(Path(path).read_text());self.card_id=old['id'];self.shot=old['shot_manifest']
            self.ax.setValue(old['anchor_px'][0]);self.ay.setValue(old['anchor_px'][1]);self.label.setText(old['shot_id']+' / '+self.card_id)
        send=QPushButton('Export Update' if update else 'Send Cutout Card');send.clicked.connect(self.send);layout.addWidget(send)
    def refresh_selection(self,checked):
        try:
            w,h,pix,bounds,_=rgba(self.doc,self.node,checked)
            self.preview.setPixmap(QPixmap.fromImage(QImage(pix,w,h,w*4,QImage.Format_RGBA8888).copy()).scaled(600,260,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            if not self.card_id:
                self.ax.setValue((bounds[0]+bounds[2])/2);self.ay.setValue(bounds[3])
        except Exception as exc:
            self.selection.blockSignals(True);self.selection.setChecked(False);self.selection.blockSignals(False)
            QMessageBox.warning(self,'Selection unavailable',str(exc))
    def choose_shot(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose exact source shot',str(ROOT/'shots'),'Saved shot (shot.json)')
        if path:self.shot=path;self.label.setText(path)
    def send(self):
        try:
            if not self.shot:raise ValueError('Choose the exact saved source shot first.')
            result=export_node(self.doc,self.node,self.shot,[self.ax.value(),self.ay.value()],self.card_id,self.selection.isChecked(),self.rectangle.isChecked())
            QMessageBox.information(self,'Cutout exported','Export ready. In Unreal, click Use Latest Krita Export, then Import Cutout on Support or Update Selected Card.\n'+str(result));self.accept()
        except Exception as exc:QMessageBox.warning(self,'Cutout not exported',str(exc))

class CardExtension(Extension):
    def setup(self):pass
    def createActions(self,window):
        from . import live_preview
        live_preview.install(window)
        action=window.createAction('ironwidow_layer_return','Iron Widow: Return Painting to Layer...','tools/scripts')
        try:action.triggered.disconnect()
        except TypeError:pass
        def return_paint(checked=False):
            from . import krita_layer_export
            krita_layer_export.open_dialog()
        action.triggered.connect(return_paint)
        for key,label,update in [('send','Iron Widow: Send Cutout Card...',False),('update','Iron Widow: Update Cutout Card...',True)]:
            action=window.createAction('ironwidow_cutout_'+key,label,'tools/scripts')
            # Krita may call createActions during addExtension as well as startup.
            # Rebinding our own action must not stack modal dialogs.
            try:action.triggered.disconnect()
            except TypeError:pass
            action.triggered.connect(lambda checked=False,u=update:self.open(u))
    def open(self,update=False):
        try:CardDialog(Krita.instance().activeWindow().qwindow(),update).exec_()
        except Exception as exc:QMessageBox.warning(None,'Cutout Card',str(exc))

def install():
    global _extension
    if _extension:return
    app=Krita.instance();_extension=CardExtension(app);app.addExtension(_extension)
    for window in app.windows():_extension.createActions(window)
