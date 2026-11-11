#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2026, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import (
        QCheckBox,
        QColor,
        QHBoxLayout,
        QLabel,
        QPalette,
        QPushButton,
        QSplitter,
        Qt,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from PyQt5.Qt import (
        QCheckBox,
        QColor,
        QHBoxLayout,
        QLabel,
        QPalette,
        QPushButton,
        QSplitter,
        Qt,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

import os
from collections import defaultdict
from datetime import datetime
from enum import Enum
from functools import partial
from typing import Dict, Set, Union

from calibre.db.fields import IdentifiersField, ManyToManyField, ManyToOneField, OneToOneField
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import choose_dir
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import is_date_undefined
from calibre.utils.icu import sort_key

from .charts import NO_VALUE, ChartViewWidget, LegendChart
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


def item_style(item: QWidget, *, bold: bool=False, italic: bool=False):
    font = item.font()
    font.setBold(bold)
    font.setItalic(italic)
    item.setFont(font)


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
        if fm[field]['datatype'] in {'composite', 'comments', 'int', 'float'}:
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


class DateGroup(Enum):
    year = _('Year')
    month = _('Month')
    day = _('Day')
    hour = _('Hour')
    minute = _('Minute')


def get_visualize_data(field: str, visualize_scope: VisualizeScope) -> Dict[Union[str, bool, datetime, int], int]:
    db = current_db().new_api
    field_obj = db.fields[field]
    rslt = defaultdict(set)
    if isinstance(field_obj, IdentifiersField):
        for k,v in field_obj.table.book_col_map.items():
            for i,x in v.items():
                if i not in rslt:
                    rslt[i] = set()
                rslt[i].add(k)
        rslt[None] = set(db.all_book_ids()).difference(field_obj.table.book_col_map)
    elif isinstance(field_obj, (ManyToManyField, ManyToOneField)):
        for k,v in field_obj.table.id_map.items():
            rslt[v] = set(field_obj.table.col_book_map[k])
        rslt[None] = set(db.all_book_ids()).difference(field_obj.table.book_col_map)
    elif isinstance(field_obj, OneToOneField):
        for k,v in field_obj.table.book_col_map.items():
            rslt[v].add(k)
        rslt[None] = set(db.all_book_ids()).difference(field_obj.table.book_col_map)
    else:
        raise NotImplementedError(_('The type of the field {!r} is not supported.').format(field))
    
    if visualize_scope == VisualizeScope.virtual:
        scope_ids = set(get_BookIds_virtual())
    elif visualize_scope == VisualizeScope.search:
        scope_ids = set(get_BookIds_search())
    else:
        scope_ids = set(get_BookIds_all())
    
    for v in rslt.values():
        v.intersection_update(scope_ids)
    
    return {k:len(v) for k,v in rslt.items() if v}


def group_visualize_data(
    field: str,
    data: Dict[Union[str, bool, datetime, int], int],
    group_sort: GroupSort,
    date_group: DateGroup,
    exclude_none: bool,
) -> Dict[str, int]:
    db = current_db().new_api
    field_obj = db.fields[field]
    fm = field_obj.table.metadata
    rslt = defaultdict(set)
    def f(x):
        return x
    if fm['datatype'] == 'rating':
        allow_half_stars = bool(fm['display'].get('allow_half_stars'))
        def f(x):
            return rating_to_stars(x, allow_half_stars=allow_half_stars)
    if fm['datatype'] == 'bool':
        def f(x):
            return _('Yes') if x else _('No')
    if fm['datatype'] == 'datetime':
        fmt = '%Y'
        if date_group not in {DateGroup.year,}:
            fmt += '/%m'
        if date_group not in {DateGroup.year, DateGroup.month}:
            fmt += '/%d'
        if date_group == DateGroup.hour:
            fmt += ' %H:00'
        if date_group == DateGroup.minute:
            fmt += ' %H:%M'
        
        def f(x):
            if is_date_undefined(x):
                return None
            return x.strftime(fmt).lstrip('0')
    
    for k,v in data.items():
        if k is None:
            rslt[k].add(v)
            continue
        rslt[f(k)].add(v)
    
    if exclude_none:
        rslt.pop(None, None)
    
    reverse = group_sort in {GroupSort.alphabetical_descending, GroupSort.size_descending}
    def key(k):
        if not k:
            return
        if fm['datatype'] == 'rating':
            return k.count('★'), k.count('⯨')
        return sort_key(k)
    def f(x):
        return x
    if group_sort == GroupSort.alphabetical_ascending:
        def f(kv):
            return bool(kv[0] is None), key(kv[0])
    if group_sort == GroupSort.alphabetical_descending:
        def f(kv):
            return bool(kv[0] is not None), key(kv[0])
    if group_sort in {GroupSort.size_ascending, GroupSort.size_descending}:
        def f(kv):
            return kv[1], key(kv[0])
    
    return dict(sorted(((k, sum(v)) for k,v in rslt.items() if v), key=f, reverse=reverse))


class QColorWidget(QWidget):
    def __init__(self, color: QColor, parent=None):
        QWidget.__init__(self)
        self.color = color
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, color)
        pal.setColor(QPalette.ColorRole.Window, color)
        self.setPalette(pal)
        self.setAutoFillBackground(True)


class VisualizeMetadataDialog(Dialog):
    TITLE = _('Visualize Metadata')
    last_group_sort: GroupSort = GroupSort.size_descending
    last_date_group: DateGroup = DateGroup.day
    
    def __init__(self):
        self.raw_data: Dict[Union[str, bool, datetime, int], int] = {}
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
        self.button_reload.clicked.connect(self.load_data)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.field_selected)
        h.addWidget(self.visualize_scope)
        h.addWidget(self.button_reload)
        h.addStretch()
        
        group_sort = {n:n._value_ for n in GroupSort._member_map_.values()}
        self.group_sort = KeyValueComboBox(group_sort, selected_key=self.last_group_sort, parent=self)
        self.group_sort.currentIndexChanged.connect(self.refresh)
        
        self.label_group = QLabel(_('Group by:'), self)
        self.label_group.setVisible(False)
        
        date_group = {n:n._value_ for n in DateGroup._member_map_.values()}
        self.date_group = KeyValueComboBox(date_group, selected_key=self.last_date_group, parent=self)
        self.date_group.currentIndexChanged.connect(self.refresh)
        self.date_group.setVisible(False)
        
        self.exclude_none = QCheckBox(_('Exclude books without value'), self)
        self.exclude_none.checkStateChanged.connect(self.refresh)
        
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.group_sort)
        h.addWidget(self.label_group)
        h.addWidget(self.date_group)
        h.addWidget(self.exclude_none)
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
        
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setOpaqueResize(True)
        splitter.setHandleWidth(5)
        splitter.setChildrenCollapsible(False)
        l.addWidget(splitter, 1)
        
        self.chart = ChartViewWidget(parent=self)
        self.chart.setMinimumSize(10, 10)
        
        self.legends = ChartViewWidget(chart=LegendChart(), parent=self)
        self.legends.setMinimumSize(10, 10)
        
        splitter.addWidget(self.chart)
        splitter.addWidget(self.legends)
        splitter.setSizes((400, 200))
        self.chart.values = self.legends.values  # make chared reference

    def field_changed(self):
        db = current_db()
        fm = db.field_metadata
        fm = fm[self.field_selected.selected_key()]
        self.label_group.setVisible(fm['datatype'] == 'datetime')
        self.date_group.setVisible(fm['datatype'] == 'datetime')

    def load_data(self):
        if self.field_selected.currentIndex() < 0:
            return
        self.setWindowTitle(self.TITLE + ' :: ' + self.field_selected.currentText())
        self.raw_data = get_visualize_data(
            field=self.field_selected.selected_key(),
            visualize_scope=self.visualize_scope.selected_key(),
        )
        self.refresh()

    def refresh(self):
        VisualizeMetadataDialog.last_group_sort = self.group_sort.selected_key()
        VisualizeMetadataDialog.last_date_group = self.date_group.selected_key()
        if self.field_selected.currentIndex() < 0:
            return
        self.data = group_visualize_data(
            field=self.field_selected.selected_key(),
            data=self.raw_data,
            group_sort=self.group_sort.selected_key(),
            date_group=self.date_group.selected_key(),
            exclude_none=self.exclude_none.isChecked(),
        )
        
        self.legends.replaceDatas(self.data.items())
        self.chart.update()  # use chared reference with legends

    def export_csv(self):
        if not self.data:
            return
        file = pick_file_to_export(self.field_selected.selected_key(), 'csv', self)
        if not file:
            return
        no_value = f'<{NO_VALUE}>'
        with open(file, 'w', newline='\n', encoding='utf-8') as f:
            f.write('\ufeff')  # UTF-8 BOM
            field_name = self.field_selected.currentText().replace('"', '""')
            f.write('"{}","{}"\n'.format('Count', field_name))
            for k,v in self.data.items():
                if k is None:
                    k = no_value
                f.write('{},"{}"\n'.format(v, k.replace('"', '""')))

    def export_json(self):
        import json
        if not self.data:
            return
        file = pick_file_to_export(self.field_selected.selected_key(), 'json', self)
        if not file:
            return
        no_value = f'<{NO_VALUE}>'
        data = {(no_value if k is None else k):v for k,v in self.data.items()}
        with open(file, 'w', newline='\n', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
