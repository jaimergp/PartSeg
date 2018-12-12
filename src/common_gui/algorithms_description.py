import typing
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from enum import Enum
from typing import List, Type, Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QHideEvent, QPainter, QPaintEvent
from PyQt5.QtWidgets import QComboBox, QCheckBox, QWidget, QVBoxLayout, QLabel, QFormLayout, \
    QScrollArea, QLineEdit, QStackedLayout
from six import with_metaclass

from common_gui.dim_combobox import DimComboBox
from common_gui.universal_gui_part import CustomSpinBox, CustomDoubleSpinBox
from partseg_utils.channel_class import Channel
from project_utils_qt.error_dialog import ErrorDialog
from partseg_utils.image_operations import RadiusType
from partseg_utils.segmentation.algorithm_base import SegmentationAlgorithm, SegmentationResult
from partseg_utils.segmentation.algorithm_describe_base import AlgorithmProperty, AlgorithmDescribeBase
from project_utils_qt.segmentation_thread import SegmentationThread
from project_utils_qt.settings import ImageSettings, BaseSettings
from tiff_image import Image


class EnumComboBox(QComboBox):
    def __init__(self, enum: type(Enum), parent=None):
        super().__init__(parent=parent)
        self.enum = enum
        self.addItems(list(map(str,  enum.__members__.values())))

    def get_value(self):
        return list(self.enum.__members__.values())[self.currentIndex()]

    def set_value(self, value: Enum):
        self.setCurrentText(value.name)


class ChannelComboBox(QComboBox):
    def get_value(self):
        return self.currentIndex()

    def set_value(self, val):
        self.setCurrentIndex(int(val))

    def change_channels_num(self, num):
        index = self.currentIndex()
        self.clear()
        self.addItems(map(str, range(1, num + 1)))
        if index < 0 or index > num:
            index = 0
        self.setCurrentIndex(index)


class QtAlgorithmProperty(AlgorithmProperty):
    qt_class_dict = {int: CustomSpinBox, float: CustomDoubleSpinBox, list: QComboBox, bool: QCheckBox,
                     RadiusType: DimComboBox}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._widget = self._get_field()
        self.change_fun = self.get_change_signal(self._widget)
        self._getter, self._setter = self.get_setter_and_getter_function(self._widget)

    def get_value(self):
        return self._getter(self._widget)

    def set_value(self, val):
        return self._setter(self._widget, val)

    def get_field(self):
        return self._widget

    @classmethod
    def from_algorithm_property(cls, ob):
        """
        :type ob: AlgorithmProperty | str
        :param ob: AlgorithmProperty object or label
        :return: QtAlgorithmProperty | QLabel
        """
        if isinstance(ob, AlgorithmProperty):
            return cls(name=ob.name, user_name=ob.user_name, default_value=ob.default_value, options_range=ob.range,
                       single_steep=ob.single_step, property_type=ob.value_type, possible_values=ob.possible_values)
        elif isinstance(ob, str):
            return QLabel(ob)
        raise ValueError(f"unknown parameter type {type(ob)} of {ob}")

    def _get_field(self) -> QWidget:
        if issubclass(self.value_type, Channel):
            res = ChannelComboBox()
            res.change_channels_num(10)
            return res
        elif issubclass(self.value_type, AlgorithmDescribeBase):
            res = SubAlgorithmWidget(self)
        elif issubclass(self.value_type, bool):
            res = QCheckBox()
            res.setChecked(bool(self.default_value))
        elif issubclass(self.value_type, int):
            res = CustomSpinBox()
            assert isinstance(self.default_value, int)
            if self.range is not None:
                res.setRange(*self.range)
            res.setValue(self.default_value)
        elif issubclass(self.value_type, float):
            res = CustomDoubleSpinBox()
            assert isinstance(self.default_value, float)
            if self.range is not None:
                res.setRange(*self.range)
            res.setValue(self.default_value)
        elif issubclass(self.value_type, str):
            res = QLineEdit()
            res.setText(str(self.default_value))
        elif issubclass(self.value_type, Enum):
            res = EnumComboBox(self.value_type)
            # noinspection PyUnresolvedReference,PyUnresolvedReferences
            # res.addItems(self.value_type.__members__.keys())
            # noinspection PyUnresolvedReferences
            res.set_value(self.default_value)
        elif issubclass(self.value_type, list):
            res = QComboBox()
            res.addItems(list(map(str, self.possible_values)))
            res.setCurrentIndex(self.possible_values.index(self.default_value))
        else:
            raise ValueError(f"Unknown class: {self.value_type}")
        return res

    @staticmethod
    def get_change_signal(widget: QWidget):
        if isinstance(widget, QComboBox):
            return widget.currentIndexChanged
        elif isinstance(widget, QCheckBox):
            return widget.stateChanged
        elif isinstance(widget, (CustomDoubleSpinBox, CustomSpinBox)):
            return widget.valueChanged
        elif isinstance(widget, QLineEdit):
            return widget.textChanged
        elif isinstance(widget, SubAlgorithmWidget):
            return widget.values_changed
        raise ValueError(f"Unsupported type: {type(widget)}")

    @staticmethod
    def get_setter_and_getter_function(widget: QWidget):
        if isinstance(widget, ChannelComboBox):
            return widget.__class__.get_value, widget.__class__.set_value
        if isinstance(widget, EnumComboBox):
            return widget.__class__.get_value, widget.__class__.set_value
        if isinstance(widget, QComboBox):
            return widget.__class__.currentText, widget.__class__.setCurrentText
        elif isinstance(widget, QCheckBox):
            return widget.__class__.isChecked, widget.__class__.setChecked
        elif isinstance(widget, CustomSpinBox):
            return widget.__class__.value, widget.__class__.setValue
        elif isinstance(widget, CustomDoubleSpinBox):
            return widget.__class__.value, widget.__class__.setValue
        elif isinstance(widget, QLineEdit):
            return widget.__class__.text, widget.__class__.setText
        elif isinstance(widget, SubAlgorithmWidget):
            return widget.__class__.get_values, widget.__class__.set_values
        raise ValueError(f"Unsupported type: {type(widget)}")


class FormWidget(QWidget):
    value_changed = pyqtSignal()

    def __init__(self, fields: typing.List[AlgorithmProperty]):
        super().__init__()
        self.widgets_dict: typing.Dict[str, QtAlgorithmProperty] = dict()
        self.channels_chose: typing.List[typing.Union[ChannelComboBox, SubAlgorithmWidget]] = []
        layout = QFormLayout()
        element_list = map(QtAlgorithmProperty.from_algorithm_property, fields)
        for el in element_list:
            if isinstance(el, QLabel):
                layout.addRow(el)
            elif isinstance(el.get_field(), SubAlgorithmWidget):
                layout.addRow(QLabel(el.user_name), el.get_field().choose)
                layout.addRow(el.get_field())
                self.widgets_dict[el.name] = el
                el.change_fun.connect(self.value_changed.emit)
            else:
                self.widgets_dict[el.name] = el
                layout.addRow(QLabel(el.user_name), el.get_field())
                # noinspection PyUnresolvedReferences
                el.change_fun.connect(self.value_changed.emit)
                if issubclass(el.value_type, Channel):
                    # noinspection PyTypeChecker
                    self.channels_chose.append(el.get_field())
        self.setLayout(layout)

    def has_elements(self):
        return len(self.widgets_dict) > 0

    def get_values(self):
        return dict(((name, el.get_value()) for name, el in self.widgets_dict.items()))

    def set_values(self, values: dict):
        for name, value in values.items():
            if name in self.widgets_dict:
                self.widgets_dict[name].set_value(value)

    def image_changed(self, image: Image):
        if not image:
            return
        for channel_widget in self.channels_chose:
            if isinstance(channel_widget, ChannelComboBox):
                channel_widget.change_channels_num(image.channels)
            else:
                channel_widget.change_channels_num(image)


class SubAlgorithmWidget(QWidget):
    values_changed = pyqtSignal()

    def __init__(self, algorithm_property: AlgorithmProperty):
        super().__init__()
        assert isinstance(algorithm_property.possible_values, dict)
        assert isinstance(algorithm_property.default_value, str)
        self.property = algorithm_property
        self.widget_dict: typing.Dict[str, FormWidget] = {}
        # TODO protect for recursion
        widget = FormWidget(algorithm_property.possible_values[algorithm_property.default_value].get_fields())
        widget.layout().setContentsMargins(0, 0, 0, 0)
        widget.value_changed.connect(self.values_changed)

        self.widget_dict[algorithm_property.default_value] = widget
        self.choose = QComboBox(self)
        self.choose.addItems(algorithm_property.possible_values.keys())
        self.setContentsMargins(0, 0, 0, 0)

        self.choose.setCurrentText(algorithm_property.default_value)

        self.choose.currentTextChanged.connect(self.algorithm_choose)
        # self.setStyleSheet("border: 1px solid red")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        tmp_widget = QWidget(self)
        # tmp_widget.setMinimumHeight(5000)
        layout.addWidget(tmp_widget)
        self.tmp_widget = tmp_widget
        self.setLayout(layout)

    """def add_to_layout(self, layout: QFormLayout):
        print("[add_to_layout]")
        lay1 = self.layout().takeAt(0).layout()
        label = lay1.takeAt(0).widget()
        lay1.removeWidget(label)
        lay1.removeWidget(self.choose)
        self.layout().removeWidget(self.current_widget)
        layout.addRow(label.text(), self.choose)
        layout.addRow(self.current_widget)
        self.current_layout = layout"""

    def set_values(self, val: dict):
        if not isinstance(val, dict):
            return
        self.choose.setCurrentText(val["name"])
        if val["name"] not in self.widget_dict:
            self.algorithm_choose(val["name"])
        self.widget_dict[val["name"]].set_values(val["values"])

    def get_values(self):
        name = self.choose.currentText()
        values = self.widget_dict[name].get_values()
        return {"name": name, "values": values}

    def change_channels_num(self, image: Image):
        for i in range(self.layout().count()):
            el = self.layout().itemAt(i)
            if el.widget() and isinstance(el.widget(), FormWidget):
                el.widget().image_changed(image)

    def algorithm_choose(self, name):
        if name not in self.widget_dict:
            self.widget_dict[name] = FormWidget(self.property.possible_values[name].get_fields())
            self.widget_dict[name].layout().setContentsMargins(0, 0, 0, 0)
            self.layout().addWidget(self.widget_dict[name])
            self.widget_dict[name].value_changed.connect(self.values_changed)
        widget = self.widget_dict[name]
        for i in range(self.layout().count()):
            lay_elem = self.layout().itemAt(i)
            if lay_elem.widget():
                lay_elem.widget().hide()
        widget.show()
        self.values_changed.emit()

    def showEvent(self, _event):
        # workaround for changing size
        self.tmp_widget.hide()

    def paintEvent(self, event: QPaintEvent):
        name = self.choose.currentText()
        if self.widget_dict[name].has_elements() and event.rect().top()  == 0 and event.rect().left() == 0:
            painter = QPainter(self)
            painter.drawRect(event.rect())


class AbstractAlgorithmSettingsWidget(with_metaclass(ABCMeta, object)):
    def __init__(self):
        pass

    @abstractmethod
    def get_values(self):
        """
        :return: dict[str, object]
        """
        return dict()


class BaseAlgorithmSettingsWidget(QScrollArea):
    values_changed = pyqtSignal()
    algorithm_thread: SegmentationThread
    gauss_radius_name = "gauss_radius"
    use_gauss_name = "use_gauss"

    def __init__(self, settings: BaseSettings, name, algorithm: Type[SegmentationAlgorithm]):
        """
        For algorithm which works on one channel
        :type settings: ImageSettings
        :param settings:
        """
        super().__init__()
        self.widget_list = []
        self.name = name
        self.algorithm = algorithm
        main_layout = QVBoxLayout()
        self.info_label = QLabel()
        self.info_label.setHidden(True)
        main_layout.addWidget(self.info_label)
        self.form_widget = FormWidget(algorithm.get_fields())
        self.form_widget.value_changed.connect(self.values_changed.emit)
        self.form_widget.setMinimumHeight(1500)
        self.setWidget(self.form_widget)
        self.settings = settings
        value_dict = self.settings.get(f"algorithms.{self.name}", {})
        self.set_values(value_dict)
        # self.settings.image_changed[Image].connect(self.image_changed)
        self.algorithm_thread = SegmentationThread(algorithm())
        self.algorithm_thread.info_signal.connect(self.show_info)
        self.algorithm_thread.exception_occurred.connect(self.exception_occurred)

    def exception_occurred(self, exc: Exception):
        dial = ErrorDialog(exc, "Error during segmentation", f"{self.name}")
        dial.exec()

    def show_info(self, text):
        self.info_label.setText(text)
        self.info_label.setVisible(True)

    def image_changed(self, image: Image):
        self.algorithm_thread.algorithm.set_image(image)
        self.form_widget.image_changed(image)

    def set_mask(self, mask):
        self.algorithm_thread.algorithm.set_mask(mask)

    def set_values(self, values_dict):
        self.form_widget.set_values(values_dict)

    def get_values(self):
        return self.form_widget.get_values()

    def channel_num(self):
        return self.channels_chose.currentIndex()

    def execute(self, exclude_mask=None):
        values = self.get_values()
        self.settings.set(f"algorithms.{self.name}", deepcopy(values))
        self.algorithm_thread.set_parameters(**values)
        self.algorithm_thread.start()

    def hideEvent(self, a0: QHideEvent):
        self.algorithm_thread.clean()


class AlgorithmSettingsWidget(BaseAlgorithmSettingsWidget):
    def execute(self, exclude_mask=None):
        self.algorithm_thread.algorithm.set_exclude_mask(exclude_mask)
        self.algorithm_thread.algorithm.set_image(self.settings.image)
        super().execute(exclude_mask)


class InteractiveAlgorithmSettingsWidget(BaseAlgorithmSettingsWidget):
    algorithm_thread: SegmentationThread

    def __init__(self, settings, name, algorithm: Type[SegmentationAlgorithm],
                 selector: List[QWidget]):
        super().__init__(settings, name, algorithm)
        self.selector = selector
        self.algorithm_thread.finished.connect(self.enable_selector)
        self.algorithm_thread.started.connect(self.disable_selector)
        # self.form_widget.value_changed.connect(self.value_updated)
        # noinspection PyUnresolvedReferences
        settings.mask_changed.connect(self.change_mask)

    def value_updated(self):
        if not self.parent().interactive:
            return
        self.execute()

    def change_mask(self):
        if not self.isVisible():
            return
        self.algorithm_thread.algorithm.set_mask(self.settings.mask)

    def disable_selector(self):
        for el in self.selector:
            el.setDisabled(True)

    def enable_selector(self):
        for el in self.selector:
            el.setEnabled(True)


class AlgorithmChoose(QWidget):
    finished = pyqtSignal()
    started = pyqtSignal()
    result = pyqtSignal(SegmentationResult)
    value_changed = pyqtSignal()
    algorithm_changed = pyqtSignal(str)

    def __init__(self, settings: BaseSettings, algorithms: Dict[str, Type[SegmentationAlgorithm]],
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.stack_layout = QStackedLayout()
        self.algorithm_choose = QComboBox()
        self.algorithm_dict = {}
        widgets_list = []
        for name, val in algorithms.items():
            self.algorithm_choose.addItem(name)
            widget = InteractiveAlgorithmSettingsWidget(settings, name, val, [])
            self.algorithm_dict[name] = widget
            widgets_list.append(widget)
            widget.algorithm_thread.execution_done.connect(self.result.emit)
            widget.algorithm_thread.finished.connect(self.finished.emit)
            widget.algorithm_thread.started.connect(self.started.emit)
            widget.values_changed.connect(self.value_changed.emit)
            # widget.setMinimumHeight(5000)
            # widget.algorithm.progress_signal.connect(self.progress_info)
            self.stack_layout.addWidget(widget)

        self.algorithm_choose.currentTextChanged.connect(self.change_algorithm)
        self.settings.image_changed.connect(self.image_changed)

        name = self.settings.get("current_algorithm", "")
        if name:
            self.algorithm_choose.setCurrentText(name)

        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.algorithm_choose)
        layout.addLayout(self.stack_layout)
        self.setLayout(layout)

    def change_algorithm(self, name, values: dict = None):
        self.settings.set("current_algorithm", name)
        widget = self.stack_layout.currentWidget()
        self.blockSignals(True)
        if name != widget.name:
            widget = self.algorithm_dict[name]
            self.stack_layout.setCurrentWidget(widget)
            widget.image_changed(self.settings.image)
            if hasattr(widget, "set_mask") and hasattr(self.settings, "mask"):
                widget.set_mask(self.settings.mask)
        elif values is None:
            self.blockSignals(False)
            return
        if values is not None:
            widget.set_values(values)
        self.algorithm_choose.setCurrentText(name)
        self.blockSignals(False)
        self.algorithm_changed.emit(name)

    def image_changed(self):
        current_widget = self.stack_layout.currentWidget()
        current_widget.image_changed(self.settings.image)
        if hasattr(self.settings, "mask") and hasattr(current_widget, "change_mask"):
            current_widget.change_mask()

    def current_widget(self):
        return self.stack_layout.currentWidget()

    def get_info_text(self):
        return self.current_widget().algorithm_thread.get_info_text()


# AbstractAlgorithmSettingsWidget.register(AlgorithmSettingsWidget)
