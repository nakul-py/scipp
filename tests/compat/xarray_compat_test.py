# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

import numpy
import pytest
import xarray
import scipp as sc
from scipp.compat import from_xarray, to_xarray
from ..factory import (make_dense_data_array, make_dense_dataset,
                       make_binned_data_array)


def test_from_xarray_empty_attrs_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((1, )), dims={"x"}, attrs={})

    sc_da = from_xarray(xr_da)

    assert len(sc_da.attrs) == 0

    assert len(sc_da.dims) == 1
    assert "x" in sc_da.dims

    assert len(sc_da.masks) == 0


def test_from_xarray_attrs_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((1, )),
                             dims=["x"],
                             attrs={
                                 "attrib_int": 5,
                                 "attrib_float": 6.54321,
                                 "attrib_str": "test-string",
                             })

    sc_da = from_xarray(xr_da)

    assert sc_da.attrs["attrib_int"].values == 5
    assert sc_da.attrs["attrib_float"].values == 6.54321
    assert sc_da.attrs["attrib_str"].values == "test-string"


def test_from_xarray_named_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((1, )),
                             dims={"x"},
                             name="my-test-dataarray")

    sc_da = from_xarray(xr_da)

    assert sc_da.name == "my-test-dataarray"


def test_from_xarray_1d_1_element_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((1, )), dims=["x"], attrs={})

    sc_da = from_xarray(xr_da)

    assert sc.identical(sc_da, sc.DataArray(data=sc.zeros(dims=["x"], shape=(1, ))))


def test_from_xarray_1d_100_element_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((100, )), dims=["x"], attrs={})

    sc_da = from_xarray(xr_da)

    assert sc.identical(sc_da, sc.DataArray(data=sc.zeros(dims=["x"], shape=(100, ))))


def test_from_xarray_2d_100x100_element_dataarray():
    xr_da = xarray.DataArray(data=numpy.zeros((100, 100)), dims=["x", "y"], attrs={})

    sc_da = from_xarray(xr_da)

    assert sc.identical(sc_da,
                        sc.DataArray(data=sc.zeros(dims=["x", "y"], shape=(100, 100))))


def test_from_xarray_empty_dataset():
    xr_ds = xarray.Dataset(data_vars={})

    sc_ds = from_xarray(xr_ds)

    assert sc.identical(sc_ds, sc.Dataset(data={}))


def test_from_xarray_dataset_with_data():
    xr_ds = xarray.Dataset(
        data_vars={
            "array1": xarray.DataArray(data=numpy.zeros((100, )), dims=["x"], attrs={}),
            "array2": xarray.DataArray(data=numpy.zeros((50, )), dims=["y"], attrs={}),
        })

    sc_ds = from_xarray(xr_ds)

    reference_ds = sc.Dataset(
        data={
            "array1": sc.DataArray(data=sc.zeros(dims=["x"], shape=(100, ))),
            "array2": sc.DataArray(data=sc.zeros(dims=["y"], shape=(50, ))),
        })

    assert sc.identical(sc_ds, reference_ds)


def test_from_xarray_dataset_with_units():
    xr_ds = xarray.Dataset(
        data_vars={
            "array1":
            xarray.DataArray(
                data=numpy.zeros((100, )), dims=["x"], attrs={"units": "m"}),
            "array2":
            xarray.DataArray(data=numpy.zeros((
                50, )), dims=["y"], attrs={"units": "s"}),
        })

    sc_ds = from_xarray(xr_ds)

    reference_ds = sc.Dataset(
        data={
            "array1":
            sc.DataArray(data=sc.zeros(dims=["x"], shape=(100, ), unit=sc.Unit("m"))),
            "array2":
            sc.DataArray(data=sc.zeros(dims=["y"], shape=(50, ), unit=sc.Unit("s"))),
        })

    assert sc.identical(sc_ds, reference_ds)


def test_from_xarray_dataset_with_non_indexed_coords():
    xr_ds = xarray.Dataset(
        data_vars={
            "array1":
            xarray.DataArray(data=numpy.zeros((100, )),
                             dims=["x"],
                             coords={
                                 "x": numpy.arange(100, dtype="int64"),
                             }),
            "array2":
            xarray.DataArray(
                data=numpy.zeros((50, )),
                dims=["y"],
                coords={
                    "y": numpy.arange(50, dtype="int64"),
                    "z": ("y", numpy.arange(0, 100, 2, dtype="int64")
                          ),  # z is a non-index coord
                }),
        })

    sc_ds = from_xarray(xr_ds)

    reference_ds = sc.Dataset(data={
        "array1":
        sc.DataArray(data=sc.zeros(dims=["x"], shape=(100, ), dtype="float64")),
        "array2":
        sc.DataArray(data=sc.zeros(dims=["y"], shape=(50, ), dtype="float64"),
                     attrs={"z": sc.arange("y", 0, 100, 2, dtype="int64")}),
    },
                              coords={
                                  "x": sc.arange("x", 100, dtype="int64"),
                                  "y": sc.arange("y", 50, dtype="int64"),
                              })

    assert sc.identical(sc_ds, reference_ds)


def test_to_xarray_dataarray():

    sc_da = make_dense_data_array(ndim=2)
    xr_da = to_xarray(sc_da)
    assert xr_da.dims == sc_da.dims
    assert xr_da.shape == sc_da.shape
    assert all(x in xr_da.coords for x in ["xx", "yy"])
    assert xr_da.attrs['units'] == 'counts'
    assert numpy.array_equal(xr_da.values, sc_da.values)


def test_to_xarray_dataarray_variances_dropped():

    sc_da = make_dense_data_array(ndim=2, with_variance=True)
    xr_da = to_xarray(sc_da)
    assert xr_da.dims == sc_da.dims
    assert xr_da.shape == sc_da.shape
    assert all(x in xr_da.coords for x in ["xx", "yy"])
    assert xr_da.attrs['units'] == 'counts'
    assert numpy.array_equal(xr_da.values, sc_da.values)


def test_to_xarray_dataarray_fails_on_bin_edges():

    sc_da = make_dense_data_array(ndim=2, binedges=True)
    with pytest.raises(ValueError):
        _ = to_xarray(sc_da)


def test_to_xarray_dataarray_fails_on_binned_data():

    sc_da = make_binned_data_array(ndim=2)
    with pytest.raises(ValueError):
        _ = to_xarray(sc_da)


def test_dataarray_round_trip():

    sc_da = make_dense_data_array(ndim=2)
    assert sc.identical(sc_da, from_xarray(to_xarray(sc_da)))


def test_to_xarray_dataset():

    sc_ds = make_dense_dataset(ndim=2)
    xr_ds = to_xarray(sc_ds)
    assert all(x in xr_ds.coords for x in ["xx", "yy"])
    assert all(x in xr_ds for x in ["a", "b"])
    assert all(xr_ds[x].dims == sc_ds[x].dims for x in ["a", "b"])
    assert all(xr_ds[x].shape == sc_ds[x].shape for x in ["a", "b"])
