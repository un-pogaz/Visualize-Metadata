#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2026, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import QToolButton, QVBoxLayout
except ImportError:
    from PyQt5.Qt import QToolButton, QVBoxLayout

from functools import partial

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import Dialog

from .common_utils import PLUGIN_NAME, current_db, debug_print, get_gui, get_icon
from .common_utils.widgets import KeyValueComboBox

PLUGIN_ICON = 'images/plugin.png'


class VisualizeMetadataAction(InterfaceAction):
    name = PLUGIN_NAME
    # Create our top-level menu/toolbar action (text, icon_path, tooltip, keyboard shortcut)
    action_spec = (PLUGIN_NAME, None, _('Visualize Metadata in your library'), None)
    popup_type = QToolButton.MenuButtonPopup
    action_type = 'current'
    dont_add_to = frozenset(['context-menu-device'])
    
    def genesis(self):
        self.all_dialogs = []
        self.qaction.setIcon(get_icon(PLUGIN_ICON))
        self.qaction.triggered.connect(self.show_dialog)
    
    def library_changed(self, db):
        if self.all_dialogs:
            debug_print(f'Closing {len(self.all_dialogs)} dialogs')
        for d in list(self.all_dialogs):
            d.close()
        self.all_dialogs.clear()
    
    def close_dialog(self, dialog, code):
        if dialog in self.all_dialogs:
            self.all_dialogs.remove(dialog)
    
    def show_dialog(self):
        d = VisualizeMetadataDialog()
        self.all_dialogs.append(d)
        d.finished.connect(partial(self.close_dialog, d))
        d.show()


class VisualizeMetadataDialog(Dialog):
    def __init__(self):
        Dialog.__init__(self,
            title=_('Visualize Metadata'),
            name='plugin.VisualizeMetadata:VisualizeMetadataDialog',
            parent=get_gui(),
        )

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.setLayout(l)
