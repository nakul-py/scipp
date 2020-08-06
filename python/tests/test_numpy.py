# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2020 Scipp contributors (https://github.com/scipp)
# @author Simon Heybrock
import numpy as np
import scipp as sc


def test_numpy_self_assign_shift():
    var = sc.Variable(dims=['x'], values=np.arange(8))
    expected = sc.Variable(dims=['x'], values=[0, 1, 0, 1, 2, 3, 6, 7])
    a = np.flip(var.values)
    var['x', 2:6].values = var['x', 0:4].values
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_1d_flip():
    var = sc.Variable(dims=['x'], values=np.arange(100))
    expected = sc.Variable(dims=['x'], values=np.flip(var.values))
    var.values = np.flip(var.values)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_2d_flip_both():
    var = sc.Variable(dims=['y', 'x'], values=np.arange(100).reshape(10, 10))
    expected = sc.Variable(dims=['y', 'x'], values=np.flip(var.values))
    var.values = np.flip(var.values)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_2d_flip_first():
    var = sc.Variable(dims=['y', 'x'], values=np.arange(100).reshape(10, 10))
    expected = sc.Variable(dims=['y', 'x'], values=np.flip(var.values, axis=0))
    var.values = np.flip(var.values, axis=0)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_2d_flip_second():
    var = sc.Variable(dims=['y', 'x'], values=np.arange(100).reshape(10, 10))
    expected = sc.Variable(dims=['y', 'x'], values=np.flip(var.values, axis=1))
    var.values = np.flip(var.values, axis=1)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_shift_2d_flip_both():
    var = sc.Variable(dims=['y', 'x'], values=np.arange(9).reshape(3, 3))
    expected = sc.Variable(dims=['y', 'x'],
                           values=np.array([[0, 1, 2], [3, 4, 3], [6, 1, 0]]))
    var['y', 1:3]['x', 1:3].values = np.flip(var['y', 0:2]['x', 0:2].values)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_shift_2d_flip_first():
    # Special case of shift combined with negative stride: Essentially we walk
    # backwards from "begin", but away from "end" since the outer dim has a
    # positive stride, so a naive range check based does not catch this case.
    var = sc.Variable(dims=['y', 'x'], values=np.arange(9).reshape(3, 3))
    expected = sc.Variable(dims=['y', 'x'],
                           values=np.array([[0, 1, 2], [3, 3, 4], [6, 0, 1]]))
    var['y', 1:3]['x', 1:3].values = np.flip(var['y', 0:2]['x', 0:2].values,
                                             axis=0)
    assert sc.is_equal(var, expected)


def test_numpy_self_assign_shift_2d_flip_second():
    var = sc.Variable(dims=['y', 'x'], values=np.arange(9).reshape(3, 3))
    expected = sc.Variable(dims=['y', 'x'],
                           values=np.array([[0, 1, 2], [3, 1, 0], [6, 4, 3]]))
    var['y', 1:3]['x', 1:3].values = np.flip(var['y', 0:2]['x', 0:2].values,
                                             axis=1)
    assert sc.is_equal(var, expected)
