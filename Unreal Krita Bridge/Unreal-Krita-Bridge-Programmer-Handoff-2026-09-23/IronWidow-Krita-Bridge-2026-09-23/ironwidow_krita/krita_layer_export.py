"""Native Krita painting-group export with explicit immutable destination identity."""
import json,hashlib,time,uuid
from pathlib import Path
from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QDialog,QVBoxLayout,QLabel,QComboBox,QCheckBox,QPushButton,QMessageBox,QFileDialog
from .krita_card_export import ROOT,rgba
from .context import owned

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def catalog():
    result=[]
    for path in sorted((ROOT/'maps').glob('*/returns.json')):
        names={v:k for k,v in read(path.parent/'layers.json').get('ids',{}).items()}
        for lid,b in read(path).get('bindings',{}).items():
            if b.get('archived') or lid not in names:continue
            lp=Path(b['link']);link=read(lp)
            result.append((lp,link,names[lid]))
    return result
def check_link(path):
    path=owned(path)
    link=read(path)
    for key in ('shot_manifest','context','rgb','depth'):owned(link[key])
    if link.get('kind')!='KritaLayerLink' or sha(link['shot_manifest'])!=link['shot_sha256'] or sha(link['context'])!=link['context_sha256']:raise ValueError('Source shot/capture changed. Create a new association in Unreal.')
    shot=read(link['shot_manifest'])
    if shot['id']!=link['shot_id'] or shot['map_id']!=link['map_id'] or [shot['image_width'],shot['image_height']]!=link['canvas_size']:raise ValueError('Destination framing or ownership is invalid.')
    return link
def annotations(doc):
    raw=bytes(doc.annotation('UnrealLayerReturns'))
    return json.loads(raw) if raw else {}
def annotate(doc,node,lp):
    data=annotations(doc);data[str(node.uniqueId())]=str(Path(lp).resolve())
    doc.setAnnotation('UnrealLayerReturns','Exact Unreal layer return associations',QByteArray(json.dumps(data).encode()))
def export_group(doc,node,link_path,confirm_framing=False):
    lp=Path(link_path);link=check_link(lp)
    known=annotations(doc).get(str(node.uniqueId()))
    if known and Path(known).resolve()!=lp.resolve():raise ValueError('This group is linked to a different shot/layer. Choose its exact destination or create a separate group.')
    if not known and not confirm_framing:raise ValueError('For existing artwork, explicitly confirm the exact source shot framing before association.')
    if node.name().startswith('Reference '):raise ValueError('Reference RGB/depth nodes cannot be returned as paint.')
    w,h,pixels,bounds,_=rgba(doc,node)
    if [w,h]!=link['canvas_size']:raise ValueError('Keep the saved 1920Ã—1080 framing; no crop or resize.')
    folder=lp.parent/('Return_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]);folder.mkdir()
    png=folder/'painting.png'
    if not QImage(pixels,w,h,w*4,QImage.Format_RGBA8888).copy().save(str(png),'PNG'):raise IOError('Could not export the painting.')
    data=dict(schema=1,kind='KritaLayerPainting',map_id=link['map_id'],layer_id=link['layer_id'],link_id=link['id'],shot_id=link['shot_id'],shot_sha256=link['shot_sha256'],link_sha256=sha(lp),canvas_size=[w,h],crop_offset=[0,0],alpha_mode='masked-replacement',png='painting.png',png_sha256=sha(png),source_document=doc.fileName(),source_group=node.name(),source_node_id=str(node.uniqueId()),created=time.time())
    manifest=folder/'painting-return.json';manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temp=lp.parent/'latest-return.tmp';temp.write_text(json.dumps({'manifest':str(manifest)}),encoding='utf-8');temp.replace(lp.parent/'latest-return.json')
    annotate(doc,node,lp)
    return manifest

def put_png(doc,parent,name,path,visible=True):
    im=QImage(str(path)).convertToFormat(QImage.Format_RGBA8888)
    if im.isNull() or [im.width(),im.height()]!=[doc.width(),doc.height()]:raise ValueError('Reference image dimensions are wrong.')
    ptr=im.bits();ptr.setsize(im.byteCount());raw=bytearray(ptr);raw[0::4],raw[2::4]=raw[2::4],raw[0::4]
    node=doc.createNode(name,'paintlayer');parent.addChildNode(node,None);node.setPixelData(QByteArray(bytes(raw)),0,0,im.width(),im.height());node.setVisible(visible);return node
def new_workspace(link_path):
    link=check_link(link_path);shot=read(link['shot_manifest'])
    framing=lambda s:{k:s[k] for k in ['position_cm','rotation_degrees','horizontal_fov_degrees','aspect','near_clip_cm','image_width','image_height']}
    linked=[(p,l,n) for p,l,n in catalog() if l['map_id']==link['map_id'] and framing(read(l['shot_manifest']))==framing(shot)]
    if not linked:raise ValueError('No matching registered destination.')
    app=Krita.instance();doc=app.createDocument(1920,1080,'Unreal Layer Painting','RGBA','U8','',120)
    for n in doc.rootNode().childNodes():n.setVisible(False)
    refs=doc.createNode('Reference RGB and Depth - do not return','grouplayer');doc.rootNode().addChildNode(refs,None);refs.setVisible(False)
    groups=[]
    for lp,l,name in linked:
        check_link(lp)
        group=doc.createNode('Paint '+name,'grouplayer');doc.rootNode().addChildNode(group,None)
        put_png(doc,group,'Editable captured RGB - '+name,l['rgb']);annotate(doc,group,lp);groups.append(group)
        put_png(doc,refs,'Reference RGB '+name,l['rgb']).setLocked(True)
        put_png(doc,refs,'Reference Depth '+name,l['depth']).setLocked(True)
    refs.setLocked(True);doc.refreshProjection();doc.waitForDone();doc.setActiveNode(groups[0])
    folder=ROOT/'layer-paintings';folder.mkdir(exist_ok=True)
    path=folder/('LayerPainting_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.kra')
    if not doc.saveAs(str(path)):raise IOError('Could not save new layered workspace.')
    app.activeWindow().addView(doc);doc.setActiveNode(groups[0]);return doc

class ReturnDialog(QDialog):
    def __init__(self):
        super().__init__(Krita.instance().activeWindow().qwindow());self.setWindowTitle('Return Painting to Unreal Layer');self.resize(760,420)
        self.doc=Krita.instance().activeDocument();layout=QVBoxLayout(self)
        info=QLabel('Export ONE named paint group/layer, including its child masks. Other groups and depth references are excluded.\nUnreal replaces every material slot of this tagged actor group. Alpha below 50% is transparent; soft alpha is stored in PNG but rendered as a cutout. This is not a material-layer compositor.');info.setWordWrap(True);layout.addWidget(info)
        self.dest=QComboBox();self.links=catalog()
        for p,l,n in self.links:self.dest.addItem(n+' | '+l['world']+' | '+l['shot_id']+' | '+l['layer_id'][-8:])
        layout.addWidget(QLabel('Exact destination (map / saved shot / stable layer identity)'));layout.addWidget(self.dest)
        browse=QPushButton('Browse destination layerlink.jsonâ€¦');browse.clicked.connect(self.browse);layout.addWidget(browse)
        create=QPushButton('New Linked Painting Document (matching groups + separate references)');create.clicked.connect(self.create);layout.addWidget(create)
        self.nodes=[n for n in self.doc.rootNode().childNodes() if not n.name().startswith('Reference ')] if self.doc else []
        self.group=QComboBox()
        for n in self.nodes:self.group.addItem(n.name()+' ['+n.type()+']')
        layout.addWidget(QLabel('Named source group/layer from the current document'));layout.addWidget(self.group)
        self.confirm=QCheckBox('Associate existing artwork: I confirm this canvas uses the exact selected saved-shot framing.');layout.addWidget(self.confirm)
        self.group.currentIndexChanged.connect(self.match)
        if self.doc:
            known=annotations(self.doc)
            preferred=next((i for i,n in enumerate(self.nodes) if n==self.doc.activeNode()),None)
            if preferred is None:preferred=next((i for i,n in enumerate(self.nodes) if str(n.uniqueId()) in known),0)
            self.group.setCurrentIndex(preferred)
        send=QPushButton('Export Painting for This Layer');send.clicked.connect(self.send);layout.addWidget(send);self.match()
    def match(self,*args):
        if not self.doc or not self.nodes:return
        n=self.nodes[self.group.currentIndex()];known=annotations(self.doc).get(str(n.uniqueId()))
        if known:
            for i,(p,l,name) in enumerate(self.links):
                if p.resolve()==Path(known).resolve():self.dest.setCurrentIndex(i);break
    def chosen(self):
        if self.dest.currentIndex()<0:raise ValueError('Capture + Link a return layer in Unreal first.')
        return self.links[self.dest.currentIndex()][0]
    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose exact destination',str(ROOT/'maps'),'Layer link (layerlink.json)')
        if path:
            try:
                l=check_link(path);self.links.append((Path(path),l,l['layer_name']));self.dest.addItem(l['layer_name']+' | '+l['map_id']+' | '+l['shot_id']);self.dest.setCurrentIndex(len(self.links)-1)
            except Exception as e:QMessageBox.warning(self,'Invalid destination',str(e))
    def create(self):
        try:new_workspace(self.chosen());self.accept()
        except Exception as e:QMessageBox.warning(self,'Document not created',str(e))
    def send(self):
        try:
            if not self.nodes:raise ValueError('Open a painting document or create a linked one.')
            p=export_group(self.doc,self.nodes[self.group.currentIndex()],self.chosen(),self.confirm.isChecked())
            QMessageBox.information(self,'Layer painting exported','In Unreal, use Update Layer or Update All. The source KRA and other layer exports were not overwritten.\n'+str(p));self.accept()
        except Exception as e:QMessageBox.warning(self,'Layer not exported',str(e))
def open_dialog():ReturnDialog().exec_()
