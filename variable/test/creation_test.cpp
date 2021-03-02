// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2021 Scipp contributors (https://github.com/scipp)
#include <gtest/gtest.h>

#include "scipp/variable/creation.h"
#include "test_macros.h"
#include "test_variables.h"

using namespace scipp;
using namespace scipp::variable;

TEST(CreationTest, empty) {
  const auto dims = Dimensions(Dim::X, 2);
  const auto var1 = variable::empty(dims, units::m, dtype<double>, true);
  EXPECT_EQ(var1.dims(), dims);
  EXPECT_EQ(var1.unit(), units::m);
  EXPECT_EQ(var1.dtype(), dtype<double>);
  EXPECT_EQ(var1.hasVariances(), true);
  const auto var2 = variable::empty(dims, units::s, dtype<int32_t>);
  EXPECT_EQ(var2.dims(), dims);
  EXPECT_EQ(var2.unit(), units::s);
  EXPECT_EQ(var2.dtype(), dtype<int32_t>);
  EXPECT_EQ(var2.hasVariances(), false);
}

TEST(CreationTest, ones) {
  const auto dims = Dimensions(Dim::X, 2);
  EXPECT_EQ(
      variable::ones(dims, units::m, dtype<double>, true),
      makeVariable<double>(dims, units::m, Values{1, 1}, Variances{1, 1}));
  EXPECT_EQ(variable::ones(dims, units::s, dtype<int32_t>),
            makeVariable<int32_t>(dims, units::s, Values{1, 1}));
}

TEST_P(DenseVariablesTest, empty_like_fail_if_sizes) {
  const auto var = GetParam();
  EXPECT_THROW_DISCARD(
      empty_like(var, {}, makeVariable<scipp::index>(Values{12})),
      except::TypeError);
}

TEST_P(DenseVariablesTest, empty_like_default_shape) {
  const auto var = GetParam();
  const auto empty = empty_like(var);
  EXPECT_EQ(empty.dtype(), var.dtype());
  EXPECT_EQ(empty.dims(), var.dims());
  EXPECT_EQ(empty.unit(), var.unit());
  EXPECT_EQ(empty.hasVariances(), var.hasVariances());
}

TEST_P(DenseVariablesTest, empty_like_slice_default_shape) {
  const auto var = GetParam();
  if (var.dims().contains(Dim::X)) {
    const auto empty = empty_like(var.slice({Dim::X, 0}));
    EXPECT_EQ(empty.dtype(), var.dtype());
    EXPECT_EQ(empty.dims(), var.slice({Dim::X, 0}).dims());
    EXPECT_EQ(empty.unit(), var.unit());
    EXPECT_EQ(empty.hasVariances(), var.hasVariances());
  }
}

TEST_P(DenseVariablesTest, empty_like) {
  const auto var = GetParam();
  const Dimensions dims(Dim::X, 4);
  const auto empty = empty_like(var, dims);
  EXPECT_EQ(empty.dtype(), var.dtype());
  EXPECT_EQ(empty.dims(), dims);
  EXPECT_EQ(empty.unit(), var.unit());
  EXPECT_EQ(empty.hasVariances(), var.hasVariances());
}

TEST(CreationTest, special_like_double) {
  const auto var = makeVariable<double>(Dims{Dim::X}, Shape{2}, units::m,
                                        Values{1, 2}, Variances{3, 4});
  EXPECT_EQ(special_like(var, variable::FillValue::ZeroNotBool),
            makeVariable<double>(var.dims(), var.unit(), Values{0, 0},
                                 Variances{0, 0}));
  EXPECT_EQ(special_like(var, variable::FillValue::True),
            makeVariable<bool>(var.dims(), var.unit(), Values{true, true}));
  EXPECT_EQ(special_like(var, variable::FillValue::False),
            makeVariable<bool>(var.dims(), var.unit(), Values{false, false}));
  EXPECT_EQ(special_like(var, variable::FillValue::Max),
            makeVariable<double>(var.dims(), var.unit(),
                                 Values{std::numeric_limits<double>::max(),
                                        std::numeric_limits<double>::max()},
                                 Variances{0, 0}));
  EXPECT_EQ(special_like(var, variable::FillValue::Lowest),
            makeVariable<double>(var.dims(), var.unit(),
                                 Values{std::numeric_limits<double>::lowest(),
                                        std::numeric_limits<double>::lowest()},
                                 Variances{0, 0}));
}

TEST(CreationTest, special_like_int) {
  const auto var =
      makeVariable<int64_t>(Dims{Dim::X}, Shape{2}, units::m, Values{1, 2});
  EXPECT_EQ(special_like(var, variable::FillValue::ZeroNotBool),
            makeVariable<int64_t>(var.dims(), var.unit(), Values{0, 0}));
  EXPECT_EQ(special_like(var, variable::FillValue::True),
            makeVariable<bool>(var.dims(), var.unit(), Values{true, true}));
  EXPECT_EQ(special_like(var, variable::FillValue::False),
            makeVariable<bool>(var.dims(), var.unit(), Values{false, false}));
  EXPECT_EQ(special_like(var, variable::FillValue::Max),
            makeVariable<int64_t>(var.dims(), var.unit(),
                                  Values{std::numeric_limits<int64_t>::max(),
                                         std::numeric_limits<int64_t>::max()}));
  EXPECT_EQ(
      special_like(var, variable::FillValue::Lowest),
      makeVariable<int64_t>(var.dims(), var.unit(),
                            Values{std::numeric_limits<int64_t>::lowest(),
                                   std::numeric_limits<int64_t>::lowest()}));
}

TEST(CreationTest, special_like_bool) {
  const auto var =
      makeVariable<bool>(Dims{Dim::X}, Shape{2}, units::m, Values{true, false});
  EXPECT_EQ(special_like(var, variable::FillValue::ZeroNotBool),
            makeVariable<int64_t>(var.dims(), var.unit(), Values{0, 0}));
  EXPECT_EQ(special_like(var, variable::FillValue::Max),
            makeVariable<bool>(var.dims(), var.unit(),
                               Values{std::numeric_limits<bool>::max(),
                                      std::numeric_limits<bool>::max()}));
  EXPECT_EQ(special_like(var, variable::FillValue::Lowest),
            makeVariable<bool>(var.dims(), var.unit(),
                               Values{std::numeric_limits<bool>::lowest(),
                                      std::numeric_limits<bool>::lowest()}));
}
