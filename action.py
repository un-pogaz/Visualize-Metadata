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

import os
from enum import Enum
from functools import partial
from typing import Dict, Set

from calibre.db.fields import IdentifiersField, ManyToManyField, ManyToOneField, OneToOneField
from calibre.gui2 import choose_dir
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import sort_key

from .common_utils import PLUGIN_NAME, current_db, debug_print, get_gui, get_icon
from .common_utils.librarys import field_name, get_BookIds_all, get_BookIds_search, get_BookIds_virtual
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


def pick_file_to_export(field: str, ext: str, parent=None) -> str:
    EXT = ext.upper()
    ext = ext.lower()
    dir = choose_dir(
        name=f'{ext} dialog',
        title=_('Select folder to export the {} file…').format(EXT),
        window=parent,
    )
    if not dir:
        return
    return os.path.join(dir, f'visualize_export_{field}.{ext}')


def get_analyze_fields() -> Set[str]:
    db = current_db()
    fm = db.field_metadata
    rslt = set()
    fields = set()
    fields.update(fm.displayable_field_keys())
    fields.update(fm.custom_field_keys(False))
    fields.difference_update(('id', 'path', 'uuid', 'comments'))
    fields.difference_update(('title', 'title_sort', 'sort', 'author_sort'))
    for field in fields:
        if fm[field]['datatype'] == 'composite':
            continue
        if fm[field]['datatype'] == 'comments':
            continue
        rslt.add(field)
    return rslt


class GroupSort(Enum):
    alphabetical_ascending = _('Alphabetical (ascending)')
    alphabetical_descending = _('Alphabetical (descending)')
    size_ascending = _('Size (ascending)')
    size_descending = _('Size (descending)')


class VisualizeScope(Enum):
    library = _('Entire library')
    virtual = _('Virtual library')
    search = _('Current search')


def get_visualize_data(field: str, visualize_scope: VisualizeScope, group_sort: GroupSort) -> Dict[str, int]:
    db = current_db().new_api
    field_obj = db.fields[field]
    
    if isinstance(field_obj, IdentifiersField):
        data = {}
        for k,v in field_obj.table.book_col_map.items():
            for i,x in v.items():
                if i not in data:
                    data[i] = set()
                data[i].add(k)
        data[None] = set(db.all_book_ids()).difference(field_obj.table.book_col_map)
    elif isinstance(field_obj, (ManyToManyField, ManyToOneField)):
        data = {}
        for k,v in field_obj.table.id_map.items():
            data[v] = set(field_obj.table.col_book_map[k])
        data[None] = set(db.all_book_ids()).difference(field_obj.table.book_col_map)
    # elif isinstance(field_obj, OneToOneField):
    #     data = {}
    else:
        raise NotImplementedError(_('The type of the field {!r} is not supported.').format(field))
    
    if visualize_scope == VisualizeScope.virtual:
        scope_ids = set(get_BookIds_virtual())
    elif visualize_scope == VisualizeScope.search:
        scope_ids = set(get_BookIds_search())
    else:
        scope_ids = set(get_BookIds_all())
    
    for v in data.values():
        v.intersection_update(scope_ids)
    return {k:len(v) for k,v in data.items() if v}


class VisualizeMetadataDialog(Dialog):
    TITLE = _('Visualize Metadata')
    last_group_sort: GroupSort = GroupSort.alphabetical_ascending
    
    def __init__(self):
        self.data: Dict[str, int] = {}
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
        visualize_scope = {n:n._value_ for n in VisualizeScope._member_map_.values()}
        self.field_selected = KeyValueComboBox(analyze_fields, parent=self)
        self.field_selected.setCurrentIndex(-1)
        self.field_selected.currentIndexChanged.connect(self.field_changed)
        self.visualize_scope = KeyValueComboBox(visualize_scope, parent=self)
        self.button_reload = QPushButton(get_icon('view-refresh.png'), '', self)
        self.button_reload.setToolTip(_('Refresh the visualization'))
        self.button_reload.clicked.connect(self.refresh)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.field_selected)
        h.addWidget(self.visualize_scope)
        h.addWidget(self.button_reload)
        h.addStretch()
        
        group_sort = {n:n._value_ for n in GroupSort._member_map_.values()}
        self.group_sort = KeyValueComboBox(group_sort, selected_key=self.last_group_sort, parent=self)
        self.group_sort.currentIndexChanged.connect(self.group_sort_changed)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.group_sort)
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

    def group_sort_changed(self):
        VisualizeMetadataDialog.last_group_sort = self.group_sort.selected_key()

    def field_changed(self):
        self.field_selected.selected_key()

    def refresh(self):
        if self.field_selected.currentIndex() < 0:
            return
        self.setWindowTitle(self.TITLE + ' :: ' + self.field_selected.currentText())
        self.data = get_visualize_data(
            self.field_selected.selected_key(),
            self.visualize_scope.selected_key(),
            self.group_sort.selected_key(),
        )

    def export_csv(self):
        file = pick_file_to_export(self.field_selected.selected_key(), 'csv', self)
        if not file:
            return
        with open(file, 'wt', newline='\n', encoding='utf-8') as f:
            f.write('\ufeff')  # UTF-8 BOM
            field_name = self.field_selected.currentText().replace('"', '""')
            f.write('"{}","{}"\n'.format(field_name, 'Count'))
            for k,v in self.data.items():
                f.write('"{}",{}\n'.format(k.replace('"', '""'), v))

    def export_json(self):
        import json
        file = pick_file_to_export(self.field_selected.selected_key(), 'json', self)
        if not file:
            return
        with open(file, 'wt', newline='\n', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
