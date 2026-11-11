#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2026 un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import QAbstractScrollArea, QColor, QPainter, QPaintEvent, QPen, QRect, QSize, Qt
except ImportError:
    from PyQt5.Qt import QAbstractScrollArea, QColor, QPainter, QPaintEvent, QPen, QRect, QSize, Qt

from dataclasses import dataclass
from itertools import cycle
from typing import Iterable, Iterator, List, NamedTuple, Tuple

NO_VALUE = _('no value')

COLORS = [
    QColor('#3366CC'),
    QColor('#DC3912'),
    QColor('#FF9900'),
    QColor('#109618'),
    QColor('#990099'),
    QColor('#0099C6'),
    QColor('#DD4477'),
    QColor('#66AA00'),
    QColor('#B82E2E'),
    QColor('#316395'),
    QColor('#994499'),
    QColor('#22AA99'),
    QColor('#AAAA11'),
    QColor('#6633CC'),
    QColor('#16D620'),
    QColor('#FF6666'),
    QColor('#66CCFF'),
    QColor('#FF33FF'),
    QColor('#666600'),
    QColor('#FF00CC'),
    QColor('#0033FF'),
    QColor('#000033'),
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
    def calcMinimumSize(self, values: List[ColorData]) -> QSize:
        raise NotImplementedError('calcMinimumSize() need to be overridden in a subclass')

    def draw(self, painter: QPainter, rect: QRect, values: List[ColorData]):
        raise NotImplementedError('draw() need to be overridden in a subclass')


class PieChart(Chart):
    outline_width: float = 0

    def calcMinimumSize(self, values: List[ColorData]) -> QSize:
        return QSize(0, 0)

    def draw(self, painter: QPainter, rect: QRect, values: List[ColorData]):
        # ensure square
        size = min(rect.height(), rect.width())
        rect = QRect(rect)
        rect.setHeight(size)
        rect.setWidth(size)
        
        # apply outline
        if self.outline_width > 0:
            dpr = painter.device().devicePixelRatioF()
            width = self.outline_width * dpr
            offset = width / 2
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
        for d in values[:-1]:
            v = d.count / vtotal
            span_angle = round(v * -360.0 * 16)
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


class ChartViewWidget(QAbstractScrollArea):
    chart: Chart
    _colors: Iterator[QColor]
    
    def __init__(self, chart: Chart=None, parent=None):
        QAbstractScrollArea.__init__(self, parent)
        self.setStyleSheet('QAbstractScrollArea{background: transparent; border: none}')
        self.values: List[ColorData] = []
        self.setChart(chart or PieChart())
        self.clear()

    def addData(self, name: str, count: int):
        self.addDatas([(name, count)])

    def addDatas(self, datas: Iterable[Tuple[str, int]]):
        for name, count in datas:
            self.values.append(ColorData(
                color=next(self._colors),
                name=name,
                count=count,
            ))
        self.updateScrollbarRanges()

    def clear(self):
        self._colors = cycle(COLORS)
        self.values.clear()
        self.updateScrollbarRanges()

    def replaceDatas(self, datas: Iterable[Tuple[str, int]]):
        self.setUpdatesEnabled(False)
        self.clear()
        self.addDatas(datas)
        self.setUpdatesEnabled(True)
        self.update()

    def setChart(self, chart: Chart):
        self.chart = chart
        self.updateScrollbarRanges()

    def updateScrollbarRanges(self) -> None:
        minimum_size = self.chart.calcMinimumSize()
        viewport_size = self.viewport().size()
        
        sb = self.verticalScrollBar()
        sb.setRange(0, max(0, minimum_size.height() - viewport_size.height()))
        
        sb = self.horizontalScrollBar()
        sb.setRange(0, max(0, minimum_size.width() - viewport_size.width()))
        self.update()

    def paintEvent(self, event: QPaintEvent):
        # Get visible area
        scroll_y = self.verticalScrollBar().value()
        scroll_x = self.horizontalScrollBar().value()
        viewport = self.viewport()
        visible_rect = viewport.rect().translated(scroll_x, scroll_y)
        with QPainter(viewport) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.chart.draw(painter, visible_rect, self.values)
