from PartSegCore.algorithm_describe_base import Register
from PartSegCore.image_transforming.interpolate_image import InterpolateImage
from PartSegCore.image_transforming.swap_time_stack import SwapTimeStack
from PartSegCore.image_transforming.transform_base import TransformBase

image_transform_dict = Register(InterpolateImage, SwapTimeStack)

__all__ = ("image_transform_dict", "TransformBase")
