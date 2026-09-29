from .krita_card_export import CardExtension
from krita import Krita
Krita.instance().addExtension(CardExtension(Krita.instance()))
