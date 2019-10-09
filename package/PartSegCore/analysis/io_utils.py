import typing

import numpy as np
import packaging.version

from PartSegCore.io_utils import ProjectInfoBase
from PartSegImage import Image
from .analysis_utils import HistoryElement

project_version_info = packaging.version.Version("1.0")


class ProjectTuple(ProjectInfoBase, typing.NamedTuple):
    file_path: str
    image: Image
    segmentation: typing.Optional[np.ndarray] = None
    full_segmentation: typing.Optional[np.ndarray] = None
    mask: typing.Optional[np.ndarray] = None
    history: typing.List[HistoryElement] = []
    algorithm_parameters: dict = {}
    errors: str = ""

    def get_raw_copy(self):
        return ProjectTuple(self.file_path, self.image.substitute())

    def is_raw(self):
        return self.segmentation is None

    def replace_(self, *args, **kwargs):
        return self._replace(*args, **kwargs)


class MaskInfo(typing.NamedTuple):
    file_path: str
    mask_array: np.ndarray
