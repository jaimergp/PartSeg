from abc import ABC

import SimpleITK as sitk
import numpy as np

from project_utils import bisect
from project_utils.channel_class import Channel
from project_utils.segmentation.algorithm_base import SegmentationAlgorithm
from project_utils.convex_fill import convex_fill
from project_utils.image_operations import RadiusType
from project_utils.segmentation.algorithm_describe_base import AlgorithmDescribeBase, AlgorithmProperty
from project_utils.segmentation.denoising import noise_removal_dict
from project_utils.segmentation.segment import close_small_holes, opening


class StackAlgorithm(SegmentationAlgorithm, ABC):
    def __init__(self):
        super().__init__()
        self.exclude_mask = None
        self.channel_num = 0

    def _clean(self):
        super()._clean()
        self.exclude_mask = None

    def set_exclude_mask(self, exclude_mask):
        self.exclude_mask = exclude_mask


class ThresholdPreview(StackAlgorithm):
    @classmethod
    def get_fields(cls):
        return [
                AlgorithmProperty("channel", "Channel", 0, property_type=Channel),
                AlgorithmProperty("noise_removal", "Noise Removal", next(iter(noise_removal_dict.keys())),
                                  possible_values=noise_removal_dict, property_type=AlgorithmDescribeBase),
                AlgorithmProperty("threshold", "Threshold", 1000, (0, 10 ** 6), 100)]

    @classmethod
    def get_name(cls):
        return "Only Threshold"

    def __init__(self):
        super(ThresholdPreview, self).__init__()
        self.noise_removal = None
        self.threshold = 0

    def calculation_run(self, _report_fun):
        self.channel = self.get_channel(self.channel_num)
        image = noise_removal_dict[self.noise_removal["name"]].noise_remove(self.channel, self.image.spacing,
                                                                            self.noise_removal["values"])
        if self.exclude_mask is None:
            res = (image > self.threshold).astype(np.uint8)
        else:
            mask = self.exclude_mask > 0
            if self.exclude_mask is not None:
                result_data_type = self.exclude_mask.dtype
            else:
                result_data_type = np.uint8
            res = (image > self.threshold).astype(result_data_type)
            res[mask] = 0
            if self.exclude_mask is not None:
                res[res > 0] = self.exclude_mask.max() + 1
            res[mask] = self.exclude_mask[mask]
        self.image = None
        self.channel = None
        self.exclude_mask = None
        return res

    def set_parameters(self, channel, threshold, noise_removal):
        self.channel_num = channel
        self.threshold = threshold
        self.noise_removal = noise_removal

    def get_info_text(self):
        return ""


class BaseThresholdAlgorithm(StackAlgorithm, ABC):
    @classmethod
    def get_fields(cls):
        return [AlgorithmProperty("channel", "Channel", 0, property_type=Channel),
                AlgorithmProperty("threshold", "Threshold", 10000, (0, 10 ** 6), 100),
                AlgorithmProperty("minimum_size", "Minimum size", 8000, (20, 10 ** 6), 1000),
                AlgorithmProperty("close_holes", "Close small holes", True, (True, False)),
                AlgorithmProperty("close_holes_size", "Small holes size", 200, (0, 10 ** 3), 10),
                AlgorithmProperty("smooth_border", "Smooth borders", True, (True, False)),
                AlgorithmProperty("smooth_border_radius", "Smooth borders radius", 2, (0, 20), 1),
                AlgorithmProperty("noise_removal", "Noise Removal", next(iter(noise_removal_dict.keys())),
                                  possible_values=noise_removal_dict, property_type=AlgorithmDescribeBase),
                AlgorithmProperty("side_connection", "Connect only sides", False, (True, False)),
                AlgorithmProperty("use_convex", "Use convex_hull", False, (True, False))]

    def __init__(self):
        super().__init__()
        self.threshold = None
        self.minimum_size = None
        self.sizes = None
        self.noise_removal = None
        self.close_holes = False
        self.close_holes_size = 0
        self.smooth_border = False
        self.smooth_border_radius = 0
        self.gauss_2d = False
        self.edge_connection = True
        self.use_convex = False

    def _threshold_image(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def _threshold_and_exclude(self, image, report_fun):
        raise NotImplementedError()

    def calculation_run(self, report_fun):
        report_fun("Gauss", 0)
        self.channel = self.get_channel(self.channel_num)
        image = noise_removal_dict[self.noise_removal["name"]].noise_remove(self.channel, self.image.spacing,
                                                                            self.noise_removal["values"])
        mask = self._threshold_and_exclude(image, report_fun)
        if self.close_holes:
            report_fun("Holes closing", 3)
            mask = close_small_holes(mask, self.close_holes_size)
        report_fun("Components calculating", 4)
        self.segmentation = sitk.GetArrayFromImage(
            sitk.RelabelComponent(
                sitk.ConnectedComponent(
                    sitk.GetImageFromArray(mask), self.edge_connection
                ), 20
            )
        )
        if self.smooth_border:
            report_fun("Smoothing borders", 5)
            self.segmentation = opening(self.segmentation, self.smooth_border_radius, 20)

        self.sizes = np.bincount(self.segmentation.flat)
        ind = bisect(self.sizes[1:], self.minimum_size, lambda x, y: x > y)
        self.image = image
        self.threshold = self.threshold
        self.minimum_size = self.minimum_size
        resp = np.copy(self.segmentation)
        resp[resp > ind] = 0
        if self.use_convex:
            resp = convex_fill(resp)
        if self.exclude_mask is not None:
            resp[resp > 0] += self.exclude_mask.max()
            resp[self.exclude_mask > 0] = self.exclude_mask[self.exclude_mask > 0]
            report_fun("Calculation done", 6)
        return resp

    def _set_parameters(self, channel, threshold, minimum_size, close_holes, smooth_border, noise_removal,
                        close_holes_size, smooth_border_radius, side_connection, use_convex):
        self.channel_num = channel
        self.threshold = threshold
        self.minimum_size = minimum_size
        self.close_holes = close_holes
        self.smooth_border = smooth_border
        self.noise_removal = noise_removal
        self.close_holes_size = close_holes_size
        self.smooth_border_radius = smooth_border_radius
        self.edge_connection = not side_connection
        self.use_convex = use_convex


class ThresholdAlgorithm(BaseThresholdAlgorithm):
    def __init__(self):
        super().__init__()

    @classmethod
    def get_name(cls):
        return "Threshold"

    def _threshold_image(self, image: np.ndarray) -> np.ndarray:
        return np.array(image > self.threshold).astype(np.uint8)

    def _threshold_and_exclude(self, image, report_fun):
        report_fun("Threshold calculation", 1)
        mask = self._threshold_image(image)
        if self.exclude_mask is not None:
            report_fun("Components exclusion apply", 2)
            mask[self.exclude_mask > 0] = 0
        return mask

    def set_parameters(self, *args, **kwargs):
        super()._set_parameters(*args, **kwargs)

    def get_info_text(self):
        return ""


class AutoThresholdAlgorithm(BaseThresholdAlgorithm):
    @classmethod
    def get_fields(cls):
        res = super().get_fields()
        res.insert(1, AlgorithmProperty("suggested_size", "Suggested size", 200000, (0, 10 ** 6), 1000))
        return res

    @classmethod
    def get_name(cls):
        return "Auto Threshold"

    def __init__(self):
        super().__init__()
        self.suggested_size = 0

    def get_gauss(self, gauss_type, gauss_radius):
        if gauss_type == RadiusType.NO:
            return np.copy(self.channel)
        else:
            return super().get_gauss(gauss_type, gauss_radius)

    def _threshold_image(self, image: np.ndarray) -> np.ndarray:
        sitk_image = sitk.GetImageFromArray(image)
        sitk_mask = sitk.ThresholdMaximumConnectedComponents(sitk_image, self.suggested_size)
        # TODO what exactly it returns. Maybe it is already segmented.
        mask = sitk.GetArrayFromImage(sitk_mask)
        min_val = np.min(image[mask > 0])
        if self.threshold < min_val:
            self.threshold = min_val
        mask = (image > self.threshold).astype(np.uint8)
        return mask

    def _threshold_and_exclude(self, image, report_fun):
        if self.exclude_mask is not None:
            report_fun("Components exclusion apply", 1)
            image[self.exclude_mask > 0] = 0
        report_fun("Threshold calculation", 2)
        mask = self._threshold_image(image)
        return mask

    def set_parameters(self, suggested_size, *args, **kwargs):
        self._set_parameters(*args, **kwargs)
        self.suggested_size = suggested_size

    def get_info_text(self):
        return ""


final_algorithm_list = [ThresholdAlgorithm, ThresholdPreview, AutoThresholdAlgorithm]