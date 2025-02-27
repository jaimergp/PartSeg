import typing

from PartSegCore.algorithm_describe_base import AlgorithmProperty
from PartSegCore.image_transforming.transform_base import TransformBase
from PartSegImage import Image


class SwapTimeStack(TransformBase):
    @classmethod
    def transform(
        cls, image: Image, arguments: dict, callback_function: typing.Optional[typing.Callable[[str, int], None]] = None
    ) -> Image:
        return image.swap_time_and_stack()

    @classmethod
    def get_fields_per_dimension(cls, component_list: typing.List[str]):
        return cls.get_fields()

    @classmethod
    def calculate_initial(cls, image: Image):
        return cls.get_default_values()

    @classmethod
    def get_name(cls) -> str:
        return "Swap time and Z dim"

    @classmethod
    def get_fields(cls) -> typing.List[typing.Union[AlgorithmProperty, str]]:
        return []
