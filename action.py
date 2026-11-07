#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2026, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import QHBoxLayout, QPushButton, QToolButton, QVBoxLayout
except ImportError:
    from PyQt5.Qt import QHBoxLayout, QPushButton, QToolButton, QVBoxLayout

from functools import partial
from typing import Set

from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import sort_key

from .common_utils import PLUGIN_NAME, current_db, debug_print, get_gui, get_icon
from .common_utils.librarys import field_name
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


def get_analyze_fields() -> Set[str]:
    db = current_db()
    fm = db.field_metadata
    rslt = set()
    fields = set()
    fields.update(fm.displayable_field_keys())
    fields.update(fm.custom_field_keys(False))
    fields.difference_update(('id', 'path', 'uuid'))
    fields.difference_update(('title', 'title_sort', 'sort', 'author_sort'))
    for field in fields:
        if fm[field]['datatype'] == 'comments':
            continue
        rslt.add(field)
    return rslt


class VisualizeMetadataDialog(Dialog):
    TITLE = _('Visualize Metadata')
    
    def __init__(self):
        Dialog.__init__(self,
            title=self.TITLE,
            name='plugin.VisualizeMetadata:VisualizeMetadataDialog',
            parent=get_gui(),
        )

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.setLayout(l)
        self.setMinimumSize(500, 400)
        
        db = current_db()
        fm = db.field_metadata
        analyze_fields = dict(sorted(
            ((n,field_name(n, fm)) for n in get_analyze_fields()),
            key=lambda x:sort_key(x[1]),
        ))
        self.field_selected = KeyValueComboBox(analyze_fields, parent=self)
        self.field_selected.setCurrentIndex(-1)
        self.field_selected.currentIndexChanged.connect(self.field_changed)
        self.button_reload = QPushButton(get_icon('view-refresh.png'), '', self)
        self.button_reload.setToolTip(_('Refresh the visualization'))
        self.button_reload.clicked.connect(self.refresh)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.field_selected)
        h.addWidget(self.button_reload)
        h.addStretch()
        
        csv = QPushButton('Export CSV', self)
        csv.clicked.connect(self.export_csv)
        json = QPushButton('Export JSON', self)
        json.clicked.connect(self.export_json)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(csv)
        h.addWidget(json)
        h.addStretch()
        
        l.addStretch()

    def field_changed(self):
        self.field_selected.selected_key()

    def refresh(self):
        if self.field_selected.currentIndex() < 0:
            return
        self.setWindowTitle(self.TITLE + ' :: ' + self.field_selected.currentText())

    def export_csv(self):
        pass

    def export_json(self):
        pass
