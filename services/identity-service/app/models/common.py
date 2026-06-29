from enum import Enum


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]
