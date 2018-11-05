from .partseg_utils import SegmentationPipeline
from .calculate_pipeline import calculate_pipeline
from project_utils.progress_thread import ProgressTread
from tiff_image import Image
import numpy as np
import typing


class CalculatePipelineThread(ProgressTread):
    def __init__(self, image: Image, mask:typing.Union[np.ndarray, None], pipeline: SegmentationPipeline):
        super().__init__()
        self.image =image
        self.mask = mask
        self.pipeline = pipeline
        self.result = None

    def run(self):
        try:
            self.result = calculate_pipeline(image=self.image, mask=self.mask, pipeline=self.pipeline,
                                             report_fun=self.info_function)
        except Exception as e:
            self.error_signal.emit(e)
