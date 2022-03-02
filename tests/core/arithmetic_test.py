# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)
# @author Jan-Lukas Wynen
import numpy as np

import scipp as sc


def make_variables():
    data = np.arange(1, 4, dtype=float)
    a = sc.Variable(dims=['x'], values=data)
    b = sc.Variable(dims=['x'], values=data)
    a_slice = a['x', :]
    b_slice = b['x', :]
    return a, b, a_slice, b_slice, data


# This check is important: It can happen that an implementation of,
# e.g., __iadd__ does an in-place modification, updating `b`, but then the
# return value is assigned to `a`, which could break the connection unless
# the correct Python object is returned.
def test_iadd_returns_original_object():
    a = sc.scalar(1.2)
    b = a
    a += 1.0
    assert sc.identical(a, b)


def test_isub_returns_original_object():
    a = sc.scalar(1.2)
    b = a
    a -= 1.0
    assert sc.identical(a, b)


def test_imul_returns_original_object():
    a = sc.scalar(1.2)
    b = a
    a *= 1.0
    assert sc.identical(a, b)


def test_itruediv_returns_original_object():
    a = sc.scalar(1.2)
    b = a
    a /= 1.0
    assert sc.identical(a, b)


def test_add_variable():
    a, b, a_slice, b_slice, data = make_variables()
    c = a + b
    assert np.array_equal(c.values, data + data)
    c = a + 2.0
    assert np.array_equal(c.values, data + 2.0)
    c = a + b_slice
    assert np.array_equal(c.values, data + data)
    c += b
    assert np.array_equal(c.values, data + data + data)
    c += b_slice
    assert np.array_equal(c.values, data + data + data + data)
    c = 3.5 + c
    assert np.array_equal(c.values, data + data + data + data + 3.5)


def test_sub_variable():
    a, b, a_slice, b_slice, data = make_variables()
    c = a - b
    assert np.array_equal(c.values, data - data)
    c = a - 2.0
    assert np.array_equal(c.values, data - 2.0)
    c = a - b_slice
    assert np.array_equal(c.values, data - data)
    c -= b
    assert np.array_equal(c.values, data - data - data)
    c -= b_slice
    assert np.array_equal(c.values, data - data - data - data)
    c = 3.5 - c
    assert np.array_equal(c.values, 3.5 - data + data + data + data)


def test_mul_variable():
    a, b, a_slice, b_slice, data = make_variables()
    c = a * b
    assert np.array_equal(c.values, data * data)
    c = a * 2.0
    assert np.array_equal(c.values, data * 2.0)
    c = a * b_slice
    assert np.array_equal(c.values, data * data)
    c *= b
    assert np.array_equal(c.values, data * data * data)
    c *= b_slice
    assert np.array_equal(c.values, data * data * data * data)
    c = 3.5 * c
    assert np.array_equal(c.values, data * data * data * data * 3.5)


def test_truediv_variable():
    a, b, a_slice, b_slice, data = make_variables()
    c = a / b
    assert np.array_equal(c.values, data / data)
    c = a / 2.0
    assert np.array_equal(c.values, data / 2.0)
    c = a / b_slice
    assert np.array_equal(c.values, data / data)
    c /= b
    assert np.array_equal(c.values, data / data / data)
    c /= b_slice
    assert np.array_equal(c.values, data / data / data / data)
    c = 2.0 / a
    assert np.array_equal(c.values, 2.0 / data)


def test_pow_variable():
    a, b, a_slice, b_slice, data = make_variables()
    c = a**b
    assert np.array_equal(c.values, data**data)
    c **= b
    assert np.array_equal(c.values, (data**data)**data)
    c = a**3
    assert np.array_equal(c.values, data**3)
    c **= 3
    assert np.array_equal(c.values, (data**3)**3)
    c = a**3.0
    assert np.array_equal(c.values, data**3.0)
    c **= 3.0
    assert np.array_equal(c.values, (data**3.0)**3.0)
    c = a**b_slice
    assert np.array_equal(c.values, data**data)
    c **= b_slice
    assert np.array_equal(c.values, (data**data)**data)
    c = 2**b
    assert np.array_equal(c.values, 2**data)
    c = 2.0**b
    assert np.array_equal(c.values, 2.0**data)


def test_bitwise_ior_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    a |= b
    assert sc.identical(a, sc.scalar(True))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    a |= b
    assert sc.identical(
        a, sc.Variable(dims=['x'], values=np.array([False, True, True, True])))


def test_bitwise_or_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    assert sc.identical((a | b), sc.scalar(True))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    assert sc.identical((a | b),
                        sc.Variable(dims=['x'],
                                    values=np.array([False, True, True, True])))


def test_bitwise_iand_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    a &= b
    assert sc.identical(a, sc.scalar(False))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    a &= b
    assert sc.identical(
        a, sc.Variable(dims=['x'], values=np.array([False, False, False, True])))


def test_bitwise_and_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    assert sc.identical((a & b), sc.scalar(False))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    assert sc.identical((a & b),
                        sc.Variable(dims=['x'],
                                    values=np.array([False, False, False, True])))


def test_ixor_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    a ^= b
    assert sc.identical(a, sc.scalar(True))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    a ^= b
    assert sc.identical(
        a, sc.Variable(dims=['x'], values=np.array([False, True, True, False])))


def test_xor_variable_with_variable():
    a = sc.scalar(False)
    b = sc.scalar(True)
    assert sc.identical((a ^ b), sc.scalar(True))

    a = sc.Variable(dims=['x'], values=np.array([False, True, False, True]))
    b = sc.Variable(dims=['x'], values=np.array([False, False, True, True]))
    assert sc.identical((a ^ b),
                        sc.Variable(dims=['x'],
                                    values=np.array([False, True, True, False])))


def test_iadd_variable_with_scalar():
    v = sc.Variable(dims=['x'], values=[10.0])
    expected = sc.Variable(dims=['x'], values=[12.0])
    v += 2
    assert sc.identical(v, expected)


def test_isub_variable_with_scalar():
    v = sc.Variable(dims=['x'], values=[10.0])
    expected = sc.Variable(dims=['x'], values=[9.0])
    v -= 1
    assert sc.identical(v, expected)


def test_imul_variable_with_scalar():
    v = sc.Variable(dims=['x'], values=[10.0])
    expected = sc.Variable(dims=['x'], values=[30.0])
    v *= 3
    assert sc.identical(v, expected)


def test_itruediv_variable_with_scalar():
    v = sc.Variable(dims=['x'], values=[10.0])
    expected = sc.Variable(dims=['x'], values=[5.0])
    v /= 2
    assert sc.identical(v, expected)


def test_add_dataarray_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 2.0, 20.0, 2.0)
    assert sc.identical(da + da, expected)


def test_sub_dataarray_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    assert sc.identical(da - da, expected)


def test_mul_dataarray_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 1.0, 10.0)**2
    assert sc.identical(da * da, expected)


def test_truediv_dataarray_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.ones_like(da)
    assert sc.identical(da / da, expected)


def test_add_dataarray_with_variable():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 2.0, 20.0, 2.0)
    assert sc.identical(da + da.data, expected)
    assert sc.identical(da.data + da, expected)


def test_sub_dataarray_with_variable():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    assert sc.identical(da - da.data, expected)
    assert sc.identical(da.data - da, expected)


def test_mul_dataarray_with_variable():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 1.0, 10.0)**2
    assert sc.identical(da * da.data, expected)
    assert sc.identical(da.data * da, expected)


def test_truediv_dataarray_with_variable():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.ones_like(da)
    assert sc.identical(da / da.data, expected)
    assert sc.identical(da.data / da, expected)


def test_add_dataarray_with_scalar():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 3.0, 12.0)
    assert sc.identical(da + 2.0, expected)
    assert sc.identical(2.0 + da, expected)


def test_sub_dataarray_with_scalar():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 1.0, 10.0) - 2.0
    assert sc.identical(da - 2.0, expected)
    expected.data = 2.0 - sc.arange('x', 1.0, 10.0)
    assert sc.identical(2.0 - da, expected)


def test_mul_dataarray_with_scalar():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 2.0, 20.0, 2.0)
    assert sc.identical(da * 2.0, expected)
    assert sc.identical(2.0 * da, expected)


def test_truediv_dataarray_with_scalar():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = sc.zeros_like(da)
    expected.data = sc.arange('x', 1.0, 10.0) / 2.0
    assert sc.identical(da / 2.0, expected)
    expected.data = 2.0 / sc.arange('x', 1.0, 10.0)
    assert sc.identical(2.0 / da, expected)


def test_iadd_dataset_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    ds = sc.Dataset({'data': da.copy()})
    expected = sc.Dataset({'data': da + da})
    ds += da
    assert sc.identical(ds, expected)


def test_isub_dataset_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    ds = sc.Dataset({'data': da.copy()})
    expected = sc.Dataset({'data': da - da})
    ds -= da
    assert sc.identical(ds, expected)


def test_imul_dataset_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    ds = sc.Dataset({'data': da.copy()})
    expected = sc.Dataset({'data': da * da})
    ds *= da
    assert sc.identical(ds, expected)


def test_itruediv_dataset_with_dataarray():
    da = sc.DataArray(sc.arange('x', 1.0, 10.0),
                      coords={'x': sc.arange('x', 10.0, 20.0)})
    ds = sc.Dataset({'data': da.copy()})
    expected = sc.Dataset({'data': da / da})
    ds /= da
    assert sc.identical(ds, expected)


def test_iadd_dataset_with_scalar():
    ds = sc.Dataset(data={'data': sc.arange('x', 10.0)},
                    coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = ds.copy()
    expected['data'] = ds['data'] + 2.0

    ds += 2.0
    assert sc.identical(ds, expected)


def test_isub_dataset_with_scalar():
    ds = sc.Dataset(data={'data': sc.arange('x', 10.0)},
                    coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = ds.copy()
    expected['data'] = ds['data'] - 3.0

    ds -= 3.0
    assert sc.identical(ds, expected)


def test_imul_dataset_with_scalar():
    ds = sc.Dataset(data={'data': sc.arange('x', 10.0)},
                    coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = ds.copy()
    expected['data'] = ds['data'] * 1.5

    ds *= 1.5
    assert sc.identical(ds, expected)


def test_itruediv_dataset_with_scalar():
    ds = sc.Dataset(data={'data': sc.arange('x', 10.0)},
                    coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = ds.copy()
    expected['data'] = ds['data'] / 0.5

    ds /= 0.5
    assert sc.identical(ds, expected)


def test_isub_dataset_with_dataset_broadcast():
    ds = sc.Dataset(data={'data': sc.arange('x', 10.0)},
                    coords={'x': sc.arange('x', 10.0, 20.0)})
    expected = ds - ds['x', 0]
    ds -= ds['x', 0]
    assert sc.identical(ds, expected)
