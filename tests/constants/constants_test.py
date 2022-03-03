# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)
import scipp as sc
import scipy.constants as theirs
import scipp.constants as ours

import pytest


@pytest.mark.parametrize("name", dir(ours))
def test_constant(name):
    var = getattr(ours, name)
    if not isinstance(var, sc.Variable):
        pytest.skip()
    assert var.value == getattr(theirs, name)


def test_physical_constants():
    v, u, e = theirs.physical_constants['speed of light in vacuum']
    var = ours.physical_constants('speed of light in vacuum')
    assert var.value == v
    assert var.unit == u
    assert var.variance is None
    var = ours.physical_constants('speed of light in vacuum', with_variance=True)
    assert var.variance == e * e


@pytest.mark.parametrize(
    "var", [ours.m_e, ours.physical_constants('speed of light in vacuum')])
def test_constants_cannot_be_modified(var):
    original = var.copy()
    with pytest.raises(sc.VariableError):
        var *= 2.0
    assert sc.identical(var, original)
