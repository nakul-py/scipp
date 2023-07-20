# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
# @author Simon Heybrock
from typing import Dict, Optional

from .._scipp.core import CoordError, DataArray, Dataset, Variable
from ..typing import VariableLikeType
from .argument_handlers import combine_dict_args
from .bins import bins


def _rename_dims(
    self: VariableLikeType, dims_dict: Optional[Dict[str, str]] = None, /, **names: str
) -> VariableLikeType:
    """Rename dimensions.

    The renaming can be defined:

    - using a dict mapping the old to new names, e.g.
      ``rename_dims({'x': 'a', 'y': 'b'})``
    - using keyword arguments, e.g. ``rename_dims(x='a', y='b')``

    In both cases, x is renamed to a and y to b.

    Dimensions not specified in either input are unchanged.

    This function only renames dimensions.
    See the ``rename`` method to also rename coordinates and attributes.

    Parameters
    ----------
    dims_dict:
        Dictionary mapping old to new names.
    names:
        Mapping of old to new names as keyword arguments.

    Returns
    -------
    :
        A new object with renamed dimensions.
    """
    return self._rename_dims(combine_dict_args(dims_dict, names))


def _rename_variable(
    var: Variable, dims_dict: Dict[str, str] = None, /, **names: str
) -> Variable:
    """Rename dimension labels.

    The renaming can be defined:

    - using a dict mapping the old to new names, e.g. ``rename({'x': 'a', 'y': 'b'})``
    - using keyword arguments, e.g. ``rename(x='a', y='b')``

    In both cases, x is renamed to a and y to b.

    Dimensions not specified in either input are unchanged.

    Parameters
    ----------
    dims_dict:
        Dictionary mapping old to new names.
    names:
        Mapping of old to new names as keyword arguments.

    Returns
    -------
    :
        A new variable with renamed dimensions which shares a buffer with the input.

    See Also
    --------
    scipp.Variable.rename_dims:
        Equivalent for ``Variable`` but differs for ``DataArray`` and ``Dataset``.
    """
    return var.rename_dims(combine_dict_args(dims_dict, names))


def _rename_data_array(
    da: DataArray, dims_dict: Dict[str, str] = None, /, **names: str
) -> DataArray:
    """Rename the dimensions, coordinates, and attributes.

    The renaming can be defined:

    - using a dict mapping the old to new names, e.g. ``rename({'x': 'a', 'y': 'b'})``
    - using keyword arguments, e.g. ``rename(x='a', y='b')``

    In both cases, x is renamed to a and y to b.

    Names not specified in either input are unchanged.

    Parameters
    ----------
    dims_dict:
        Dictionary mapping old to new names.
    names:
        Mapping of old to new names as keyword arguments.

    Returns
    -------
    :
        A new data array with renamed dimensions, coordinates, and attributes.
        Buffers are shared with the input.

    See Also
    --------
    scipp.DataArray.rename_dims:
        Only rename dimensions, not coordinates and attributes.
    """
    renaming_dict = combine_dict_args(dims_dict, names)
    out = da.rename_dims(renaming_dict)
    if out.bins is not None:
        out.data = bins(**out.bins.constituents)
    for old, new in renaming_dict.items():
        if new in out.meta:
            raise CoordError(
                f"Cannot rename '{old}' to '{new}', since a coord or attr named {new} "
                "already exists."
            )
        for meta in (out.coords, out.attrs):
            if old in meta:
                meta[new] = meta.pop(old)
        if out.bins is not None:
            for meta in (out.bins.coords, out.bins.attrs):
                if old in meta:
                    meta[new] = meta.pop(old)
    return out


def _rename_dataset(
    ds: Dataset, dims_dict: Dict[str, str] = None, /, **names: str
) -> Dataset:
    """Rename the dimensions, coordinates and attributes of all the items.

    The renaming can be defined:

    - using a dict mapping the old to new names, e.g. ``rename({'x': 'a', 'y': 'b'})``
    - using keyword arguments, e.g. ``rename(x='a', y='b')``

    In both cases, x is renamed to a and y to b.

    Names not specified in either input are unchanged.

    Parameters
    ----------
    dims_dict:
        Dictionary mapping old to new names.
    names:
        Mapping of old to new names as keyword arguments.

    Returns
    -------
    :
        A new dataset with renamed dimensions, coordinates, and attributes.
        Buffers are shared with the input.

    See Also
    --------
    scipp.Dataset.rename_dims:
        Only rename dimensions, not coordinates and attributes.
    """
    dims_dict = combine_dict_args(dims_dict, names)
    return Dataset(
        {key: _rename_data_array(value, dims_dict) for key, value in ds.items()}
    )
