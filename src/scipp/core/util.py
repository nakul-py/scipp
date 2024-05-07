# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
# @author Simon Heybrock

from ..typing import VariableLikeType
from .cpp_classes import DataArray, Dataset, Variable
from .like import empty_like


def _copy_dict_for_overwrite(mapping: dict[str, Variable]) -> dict[str, Variable]:
    return {name: copy_for_overwrite(var) for name, var in mapping.items()}


def copy_for_overwrite(obj: VariableLikeType) -> VariableLikeType:
    """
    Copy a Scipp object for overwriting.

    Unlike :py:func:`scipp.empty_like` this does not preserve (and share) coord,
    mask, and attr values. Instead, those values are not initialized, just like the
    data values.
    """
    if isinstance(obj, Variable):
        return empty_like(obj)
    if isinstance(obj, DataArray):
        return DataArray(
            copy_for_overwrite(obj.data),
            coords=_copy_dict_for_overwrite(obj.coords),
            masks=_copy_dict_for_overwrite(obj.masks),
            attrs=_copy_dict_for_overwrite(obj.attrs),
        )
    ds = Dataset(coords=_copy_dict_for_overwrite(obj.coords))
    for name, da in obj.items():
        ds[name] = DataArray(
            copy_for_overwrite(da.data),
            masks=_copy_dict_for_overwrite(da.masks),
            attrs=_copy_dict_for_overwrite(da.attrs),
        )
    return ds


class VisibleDeprecationWarning(UserWarning):
    """Visible deprecation warning.

    By default, Python and in particular Jupyter will not show deprecation
    warnings, so this class can be used when a very visible warning is helpful.
    """


VisibleDeprecationWarning.__module__ = 'scipp'
