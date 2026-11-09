#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2016 DaltonST (heavly rewrited), 2026 un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

try:
    from qt.core import QColor, QPainter, QPaintEvent, QRect, Qt, QWidget
except ImportError:
    from PyQt5.Qt import QColor, QPainter, QPaintEvent, QRect, Qt, QWidget


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


class Chart:
    def __init__(self):
        self.data: List[ColorData] = []
    
    def setData(self, data: List[ColorData]):
        self.data = data.copy()
    
    def draw(self, painter: QPainter, rect: QRect):
        raise NotImplementedError('draw() need to be overridden in a subclass')


class PieChart(Chart):
    def draw(self, painter: QPainter, rect: QRect):
        painter.save()
        painter.translate(rect.x(), rect.y())
        # ensure square
        size = min(rect.height(), rect.width())
        rect.setHeight(size)
        rect.setWidth(size)
        # draw splices
        ## startAngle and spanAngle must be specified in 1/16th of a degree,
        ## i.e. a full circle equals 5760 (16 * 360)
        painter.setPen(Qt.transparent)
        vtotal = float(sum(e.count for e in self.data))
        start_angle = offset = 90 * 16
        first_slice = True
        overlap = 4  # overlap to avoid weird edge
        for d in self.data[:-1]:
            v = d.count / vtotal
            painter.setBrush(QColor(d.color))
            span_angle = round(v * -360.0 * 16)
            painter.drawPie(
                rect,
                start_angle + (overlap if first_slice else 0),  # backward overlap (overide by the last)
                span_angle - overlap*(2 if first_slice else 1),  # frontward overlap (overide by the next)
            )
            start_angle += span_angle
            first_slice = False
        if self.data:
            painter.setBrush(QColor(self.data[-1].color))
            span_angle = start_angle + 360 * 16 - offset
            painter.drawPie(rect, offset, max(0, span_angle))
        painter.restore()


class ViewChartWidget(QWidget):
    chart: Chart
    _colors: Iterator[QColor]
    
    def __init__(self, chart: Chart=None, parent=None):
        QWidget.__init__(self, parent=parent)
        self.values: List[ColorData] = []
        self.chart = chart or PieChart()
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
        self.update()

    def clear(self):
        self._colors = cycle(COLORS)
        self.values.clear()
        self.update()

    def setChart(self, chart: Chart):
        self.chart = chart
        self.update()

    def paintEvent(self, event: QPaintEvent):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.chart.setData(self.values)
            self.chart.draw(painter, QRect(0, 0, event.rect().width(), event.rect().height()))
