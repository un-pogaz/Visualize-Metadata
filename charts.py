#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2026 un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import (
        QAbstractScrollArea,
        QColor,
        QFont,
        QFontMetrics,
        QImage,
        QPainter,
        QPaintEvent,
        QPen,
        QPixmap,
        QPixmapCache,
        QRect,
        QResizeEvent,
        QSize,
        QSizeF,
        Qt,
        QWidget,
    )
except ImportError:
    from PyQt5.Qt import (
        QAbstractScrollArea,
        QColor,
        QFont,
        QFontMetrics,
        QImage,
        QPainter,
        QPaintEvent,
        QPen,
        QPixmap,
        QPixmapCache,
        QRect,
        QResizeEvent,
        QSize,
        QSizeF,
        Qt,
        QWidget,
    )

from dataclasses import dataclass
from itertools import cycle
from typing import Iterable, List, NamedTuple, Tuple

from calibre.utils.icu import sort_key

NO_VALUE = _('no value')
LEGEND_FMT = _('{:d}:')

COLORS = [
    QColor('#3366CC'),
    QColor('#DD3311'),
    QColor('#FF9900'),
    QColor('#119922'),
    QColor('#990099'),
    QColor('#0099CC'),
    QColor('#DD4477'),
    QColor('#66AA00'),
    QColor('#BB3333'),
    QColor('#336699'),
    QColor('#22AA99'),
    QColor('#AAAA11'),
    QColor('#6633CC'),
    QColor('#22EE22'),
    QColor('#994499'),
    QColor('#FF6666'),
    QColor('#66CCFF'),
    QColor('#FF33FF'),
    QColor('#666600'),
    QColor('#FF00CC'),
    QColor('#0033FF'),
    QColor('#CC9966'),
    QColor('#99FF33'),
    QColor('#9999FF'),
    QColor('#006600'),
    QColor('#FFFFCC'),
]


class ColorData(NamedTuple):
    color: QColor
    count: int
    name: str


@dataclass
class Chart:
    def calcMinimumSize(self, parent: QWidget, values: List[ColorData]) -> QSize:
        raise NotImplementedError('calcMinimumSize() need to be overridden in a subclass')

    def draw(self, parent: QWidget, painter: QPainter, rect: QRect, values: List[ColorData]):
        raise NotImplementedError('draw() need to be overridden in a subclass')


class LegendChart(Chart):
    entry_height: int = 26
    count_margin: int = 10
    text_margin: int = 5
    
    def calc_legend_size(self, parent: QWidget, values: List[ColorData]) -> Tuple[int, int, int]:
        if not values:
            return 0, 0, 0
        
        fm = parent.fontMetrics()
        font = QFont(parent.font())
        font.setItalic(True)
        fmi = QFontMetrics(font)
        text_w = [0]
        for text in sorted(values, key=lambda x:len(x.name or NO_VALUE), reverse=True)[:5]:
            text = text.name
            if not text:
                text_w.append(fmi.boundingRect(NO_VALUE).width())
            else:
                text_w.append(fm.boundingRect(text).width())
        
        max_count = max((x.count for x in values), default='')
        count_w = fm.boundingRect(LEGEND_FMT.format(max_count)).width()
        
        dpr = parent.devicePixelRatioF()
        return round(self.entry_height * dpr), count_w, max(text_w)
    
    def calcMinimumSize(self, parent: QWidget, values: List[ColorData]) -> QSize:
        if not values:
            return QSize(0, 0)
        
        dpr = parent.devicePixelRatioF()
        count_margin = round(self.count_margin * dpr)
        text_margin = round(self.text_margin * dpr)
        color_w, count_w, text_w = self.calc_legend_size(parent, values)
        height = len(values) * (self.entry_height * dpr)
        width = color_w + count_w + text_w
        width += count_margin + text_margin + max(count_margin, text_margin) / 2
        return QSizeF(width, height).toSize()

    def render_legend_as_pixmap(
        self,
        parent: QWidget,
        legend: ColorData,
        color_width: int,
        count_width: int,
        text_width: int,
    ):
        dpr = parent.devicePixelRatioF()
        count_margin = round(self.count_margin * dpr)
        text_margin = round(self.text_margin * dpr)
        height = round(self.entry_height * dpr)
        width = color_width + count_width + text_width
        width += count_margin + text_margin + max(count_margin, text_margin)
        
        text_color = parent.palette().text().color()
        font = QFont(parent.font())
        
        key = ''.join(map(str, (
            __name__,
            font.key(),
            height,
            width,
            count_margin,
            text_margin,
            legend.color.rgb(),
            legend.name,
            bool(legend.name),
        )))
        rslt = QPixmapCache.find(key)
        if rslt:
            return rslt
        
        ans = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        ans.fill(Qt.transparent)
        ans.setDevicePixelRatio(dpr)
        with QPainter(ans) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
            painter.setFont(font)
            
            painter.setPen(Qt.transparent)
            painter.setBrush(legend.color)
            painter.drawRect(0, 0, color_width, height)
            
            painter.setPen(text_color)
            painter.setBrush(Qt.transparent)
            painter.drawText(
                QRect(color_width + text_margin, 0, count_width, height),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                LEGEND_FMT.format(legend.count),
            )
            
            if not legend.name:
                font.setItalic(True)
                painter.setFont(font)
                text = NO_VALUE
            else:
                text = legend.name
            painter.drawText(
                QRect(color_width + count_width + text_margin*2, 0, text_width, height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
        
        rslt = QPixmap.fromImage(ans)
        QPixmapCache.insert(key, rslt)
        return rslt

    def draw(self, parent: QWidget, painter: QPainter, rect: QRect, values: List[ColorData]):
        dpr = parent.devicePixelRatioF()
        entry_height = round(self.entry_height * dpr)
        color_w, count_w, text_w = self.calc_legend_size(parent, values)
        for i,data in enumerate(values):
            y = i * entry_height
            if y > rect.y() + rect.height():
                break
            if y < rect.y() - entry_height:
                continue
            pixmap = self.render_legend_as_pixmap(parent, data, color_w, count_w, text_w)
            painter.drawPixmap(-rect.x(), y - rect.y(), pixmap)


class PieChart(Chart):
    outline_width: int = 0

    def calcMinimumSize(self, parent: QWidget, values: List[ColorData]) -> QSize:
        return QSize(0, 0)

    def draw(self, parent: QWidget, painter: QPainter, rect: QRect, values: List[ColorData]):
        # ensure square
        size = min(rect.height(), rect.width())
        rect = QRect(rect)
        rect.setHeight(size)
        rect.setWidth(size)
        
        # apply outline
        if self.outline_width > 0:
            dpr = parent.devicePixelRatioF()
            width = self.outline_width * dpr
            offset = width / 2.0
            outline_pen = QPen(Qt.GlobalColor.white, width)
            if len(values) > 1:
                painter.setPen(outline_pen)
            else:
                painter.setPen(Qt.transparent)
            rect = rect.toRectF()
            rect.adjust(offset, offset, -offset, -offset)
            overlap = 0
        else:
            painter.setPen(Qt.transparent)
            overlap = 4
        
        # draw splices
        ## startAngle and spanAngle must be specified in 1/16th of a degree,
        ## i.e. a full circle equals 5760 (16 * 360)
        vtotal = float(sum(e.count for e in values))
        start_angle = offset = 90 * 16
        first_slice = True
        lst_merged = []
        
        def calc_modulo(value):
            i = int(value)
            return i, value - i
        
        for d in values[:-1]:
            v = d.count / vtotal
            span_angle, span_modulo = calc_modulo(v * -360.0 * 16)
            lst_merged.append(span_modulo)
            merged_angle, merged_modulo = calc_modulo(sum(lst_merged))
            if merged_angle < 0:
                span_angle += merged_angle
                lst_merged.clear()
                lst_merged.append(merged_modulo)
            if span_angle >= 0:  # skip empty slices
                continue
            painter.setBrush(d.color)
            painter.drawPie(rect,                                # overlap to avoid weird edge
                start_angle + (overlap if first_slice else 0),   # backward overlap (overide by the last)
                span_angle - overlap*(2 if first_slice else 1),  # frontward overlap (overide by the next)
            )
            start_angle += span_angle
            first_slice = False
        if values:
            painter.setBrush(values[-1].color)
            span_angle = start_angle + 360 * 16 - offset
            painter.drawPie(rect, offset, max(0, span_angle))
        
        if self.outline_width > 0 and len(values) == 1:
            painter.setPen(outline_pen)
            painter.setBrush(Qt.transparent)
            painter.drawEllipse(rect)


class BarChart(Chart):
    bar_width: int = 25
    bar_gap: int = 5

    def calcMinimumSize(self, parent: QWidget, values: List[ColorData]) -> QSize:
        if not values:
            return QSize(0, 0)
        
        dpr = parent.devicePixelRatioF()
        lenght = len(values)
        bar_w = self.bar_width * lenght * dpr
        gap_w = self.bar_gap * (lenght - 1) * dpr
        return QSizeF(bar_w + gap_w, 0).toSize()

    def draw(self, parent: QWidget, painter: QPainter, rect: QRect, values: List[ColorData]):
        dpr = parent.devicePixelRatioF()
        bar_width = round(self.bar_width * dpr)
        bar_gap = round(self.bar_gap * dpr)
        bar_gap_width = bar_width + bar_gap
        
        painter.setPen(Qt.transparent)
        vmax = float(max((e.count for e in values), default=0))
        last_color = QColor(Qt.transparent)
        for i,data in enumerate(values):
            x = i * bar_gap_width
            if x > rect.x() + rect.height() + bar_gap_width:
                break
            if x < rect.x() - bar_width:
                continue
            
            painter.setBrush(data.color)
            painter.drawRect(QRect(
                x - rect.x(),
                rect.bottom(),
                bar_width,
                -max(1, round(rect.height() * (data.count / vmax))),
            ))


class ChartViewWidget(QAbstractScrollArea):
    chart: Chart
    
    def __init__(self, chart: Chart=None, parent=None):
        QAbstractScrollArea.__init__(self, parent)
        self.setStyleSheet('QAbstractScrollArea{background: transparent; border: none}')
        self.values: List[ColorData] = []
        self.setChart(chart or PieChart())
        self.clear()

    def addData(self, name: str, count: int):
        self.addDatas([(name, count)])

    def addDatas(self, datas: Iterable[Tuple[str, int]]):
        lst = []
        lst.extend((x.name, x.count) for x in self.values)
        lst.extend(datas)
        
        def key(x: Tuple[int, Tuple[str, int]]):
            # None at the end, count, name
            return not x[1][0], x[1][1], sort_key(x[1][0])
        
        icolors = cycle(COLORS)
        for c,(i,(n,v)) in zip(icolors, sorted(enumerate(lst), key=key)):
            lst[i] = ColorData(
                color=c,
                name=n,
                count=v,
            )
        self.values.clear()
        self.values.extend(lst)
        self.updateScrollbarRanges()

    def clear(self):
        self.values.clear()
        self.updateScrollbarRanges()

    def replaceDatas(self, datas: Iterable[Tuple[str, int]]):
        ue = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        self.clear()
        self.addDatas(datas)
        self.setUpdatesEnabled(ue)
        self.update()

    def setChart(self, chart: Chart):
        self.chart = chart
        self.updateScrollbarRanges()

    def updateScrollbarRanges(self, update=True):
        viewport = self.viewport()
        minimum_size = self.chart.calcMinimumSize(self, self.values)
        
        sb = self.verticalScrollBar()
        sb.setRange(0, max(0, minimum_size.height() - viewport.height()))
        
        sb = self.horizontalScrollBar()
        sb.setRange(0, max(0, minimum_size.width() - viewport.width()))
        self.update()

    def resizeEvent(self, ev: QResizeEvent):
        ue = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        self.updateScrollbarRanges()
        self.setUpdatesEnabled(ue)
        QAbstractScrollArea.resizeEvent(self, ev)

    def paintEvent(self, ev: QPaintEvent):
        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        scroll_x = self.horizontalScrollBar().value()
        viewport = self.viewport()
        visible_rect = viewport.rect().translated(scroll_x, scroll_y)
        with QPainter(viewport) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.chart.draw(self, painter, visible_rect, self.values)
