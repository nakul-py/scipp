// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2021 Scipp contributors (https://github.com/scipp)
#include "test_util.h"
#include <gtest/gtest.h>

#include "scipp/dataset/shape.h"
#include "scipp/variable/arithmetic.h"
#include "scipp/variable/shape.h"

using namespace scipp;
using namespace scipp::core;
using namespace scipp::dataset;

TEST(ResizeTest, data_array_1d) {
  const auto var = makeVariable<double>(Dims{Dim::X}, Shape{2}, Values{1, 2});
  DataArray a(var);
  a.coords().set(Dim::X, var);
  a.attrs().set(Dim::Y, var);
  a.masks().set("mask", var);
  DataArray expected(makeVariable<double>(Dims{Dim::X}, Shape{3}));
  EXPECT_EQ(resize(a, Dim::X, 3), expected);
}

TEST(ResizeTest, data_array_2d) {
  const auto var = makeVariable<double>(Dims{Dim::Y, Dim::X}, Shape{3, 2},
                                        Values{1, 2, 3, 4, 5, 6});
  auto x = var.slice({Dim::Y, 0});
  auto y = var.slice({Dim::X, 0});
  DataArray a(var);
  a.coords().set(Dim::X, x);
  a.coords().set(Dim::Y, y);
  a.attrs().set(Dim("unaligned-x"), x);
  a.attrs().set(Dim("unaligned-y"), y);
  a.masks().set("mask-x", x);
  a.masks().set("mask-y", y);

  DataArray expected(makeVariable<double>(Dims{Dim::Y, Dim::X}, Shape{1, 2}));
  expected.coords().set(Dim::X, x);
  expected.attrs().set(Dim("unaligned-x"), x);
  expected.masks().set("mask-x", x);

  EXPECT_EQ(resize(a, Dim::Y, 1), expected);

  Dataset d({{"a", a}});
  Dataset expected_d({{"a", expected}});
  EXPECT_EQ(resize(d, Dim::Y, 1), expected_d);
}

TEST(StackingTest, split_x) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X, reshape(arange(Dim::X, 6), {{Dim::Row, 2}, {Dim::Tof, 3}}) +
                  0.1 * units::one);
  expected.coords().set(Dim::Y, a.coords()[Dim::Y]);

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}}), expected);
}

TEST(StackingTest, split_y) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Row, 2}, {Dim::Tof, 2}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::Y, reshape(arange(Dim::Y, 4), {{Dim::Row, 2}, {Dim::Tof, 2}}) +
                  0.2 * units::one);
  expected.coords().set(Dim::X, a.coords()[Dim::X]);

  EXPECT_EQ(stack(a, Dim::Y, {{Dim::Row, 2}, {Dim::Tof, 2}}), expected);
}

TEST(StackingTest, split_into_3_dims) {
  const auto var = arange(Dim::X, 24);
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 24) + 0.1 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Tof, 2}, {Dim::Y, 3}, {Dim::Z, 4}});
  DataArray expected(rshp);
  expected.coords().set(Dim::X, rshp + 0.1 * units::one);

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Tof, 2}, {Dim::Y, 3}, {Dim::Z, 4}}),
            expected);
}

TEST(StackingTest, flatten) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.1, 0.1, 0.1, 0.1, 1.1, 1.1, 1.1, 1.1,
                                  2.1, 2.1, 2.1, 2.1, 3.1, 3.1, 3.1, 3.1,
                                  4.1, 4.1, 4.1, 4.1, 5.1, 5.1, 5.1, 5.1}));
  expected.coords().set(
      Dim::Y,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2}));

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, round_trip) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  auto reshaped = stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}});
  EXPECT_EQ(unstack(reshaped, {Dim::Row, Dim::Tof}, Dim::X), a);
}

TEST(StackingTest, split_x_binedges_x) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 7) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      makeVariable<double>(Dims{Dim::Row, Dim::Tof}, Shape{2, 4},
                           Values{0.1, 1.1, 2.1, 3.1, 3.1, 4.1, 5.1, 6.1}));
  expected.coords().set(Dim::Y, a.coords()[Dim::Y]);

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}}), expected);
}

TEST(StackingTest, split_y_binedges_y) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 5) + 0.2 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Row, 2}, {Dim::Tof, 2}});
  DataArray expected(rshp);
  expected.coords().set(Dim::X, a.coords()[Dim::X]);
  expected.coords().set(
      Dim::Y, makeVariable<double>(Dims{Dim::Row, Dim::Tof}, Shape{2, 3},
                                   Values{0.2, 1.2, 2.2, 2.2, 3.2, 4.2}));

  EXPECT_EQ(stack(a, Dim::Y, {{Dim::Row, 2}, {Dim::Tof, 2}}), expected);
}

TEST(StackingTest, flatten_binedges_x) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 7) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  // Note: x coord is dropped because od mismatching bin edges during
  // concatenate.
  expected.coords().set(
      Dim::Y,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2}));

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, flatten_binedges_y) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 5) + 0.2 * units::one);

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.1, 0.1, 0.1, 0.1, 1.1, 1.1, 1.1, 1.1,
                                  2.1, 2.1, 2.1, 2.1, 3.1, 3.1, 3.1, 3.1,
                                  4.1, 4.1, 4.1, 4.1, 5.1, 5.1, 5.1, 5.1}));
  // Note: y coord is dropped because od mismatching bin edges during
  // concatenate.

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, round_trip_binedges) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 7) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  auto reshaped = stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}});
  EXPECT_EQ(unstack(reshaped, {Dim::Row, Dim::Tof}, Dim::X), a);
}

TEST(StackingTest, split_x_with_attrs) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);
  a.attrs().set(Dim::Qx, arange(Dim::X, 6) + 0.3 * units::one);
  a.attrs().set(Dim::Qy, arange(Dim::Y, 4) + 0.4 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X, reshape(arange(Dim::X, 6), {{Dim::Row, 2}, {Dim::Tof, 3}}) +
                  0.1 * units::one);
  expected.coords().set(Dim::Y, a.coords()[Dim::Y]);
  expected.attrs().set(
      Dim::Qx, reshape(arange(Dim::X, 6), {{Dim::Row, 2}, {Dim::Tof, 3}}) +
                   0.3 * units::one);
  expected.attrs().set(Dim::Qy, a.attrs()[Dim::Qy]);

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}}), expected);
}

TEST(StackingTest, flatten_with_attrs) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);
  a.attrs().set(Dim::Qx, arange(Dim::X, 6) + 0.3 * units::one);
  a.attrs().set(Dim::Qy, arange(Dim::Y, 4) + 0.4 * units::one);

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.1, 0.1, 0.1, 0.1, 1.1, 1.1, 1.1, 1.1,
                                  2.1, 2.1, 2.1, 2.1, 3.1, 3.1, 3.1, 3.1,
                                  4.1, 4.1, 4.1, 4.1, 5.1, 5.1, 5.1, 5.1}));
  expected.coords().set(
      Dim::Y,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2}));
  expected.attrs().set(
      Dim::Qx,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.3, 0.3, 0.3, 0.3, 1.3, 1.3, 1.3, 1.3,
                                  2.3, 2.3, 2.3, 2.3, 3.3, 3.3, 3.3, 3.3,
                                  4.3, 4.3, 4.3, 4.3, 5.3, 5.3, 5.3, 5.3}));
  expected.attrs().set(
      Dim::Qy,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.4, 1.4, 2.4, 3.4, 0.4, 1.4, 2.4, 3.4,
                                  0.4, 1.4, 2.4, 3.4, 0.4, 1.4, 2.4, 3.4,
                                  0.4, 1.4, 2.4, 3.4, 0.4, 1.4, 2.4, 3.4}));

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, split_x_with_2d_coord) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X,
                 reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}}) +
                     0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}}) +
          0.1 * units::one);
  expected.coords().set(Dim::Y, a.coords()[Dim::Y]);

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}}), expected);
}

TEST(StackingTest, flatten_with_2d_coord) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X,
                 reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}}) +
                     0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  expected.coords().set(Dim::X, arange(Dim::Z, 24) + 0.1 * units::one);
  expected.coords().set(
      Dim::Y,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2}));

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, split_x_with_masks) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);
  a.masks().set("mask_x", makeVariable<bool>(
                              Dims{Dim::X}, Shape{6},
                              Values{true, true, true, false, false, false}));
  a.masks().set("mask_y", makeVariable<bool>(Dims{Dim::Y}, Shape{4},
                                             Values{true, true, false, true}));
  a.masks().set(
      "mask2d",
      makeVariable<bool>(Dims{Dim::X, Dim::Y}, Shape{6, 4},
                         Values{true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                true,  false, true,  false, true,  false,
                                true,  true,  true,  false, false, false}));

  const auto rshp =
      reshape(arange(Dim::X, 24), {{Dim::Row, 2}, {Dim::Tof, 3}, {Dim::Y, 4}});
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X, reshape(arange(Dim::X, 6), {{Dim::Row, 2}, {Dim::Tof, 3}}) +
                  0.1 * units::one);
  expected.coords().set(Dim::Y, a.coords()[Dim::Y]);
  expected.masks().set(
      "mask_x",
      makeVariable<bool>(Dims{Dim::Row, Dim::Tof}, Shape{2, 3},
                         Values{true, true, true, false, false, false}));
  expected.masks().set("mask_y",
                       makeVariable<bool>(Dims{Dim::Y}, Shape{4},
                                          Values{true, true, false, true}));
  expected.masks().set(
      "mask2d",
      makeVariable<bool>(Dims{Dim::Row, Dim::Tof, Dim::Y}, Shape{2, 3, 4},
                         Values{true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                true,  false, true,  false, true,  false,
                                true,  true,  true,  false, false, false}));

  EXPECT_EQ(stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}}), expected);
}

TEST(StackingTest, flatten_with_masks) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 6) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);
  a.masks().set("mask_x", makeVariable<bool>(
                              Dims{Dim::X}, Shape{6},
                              Values{true, true, true, false, false, false}));
  a.masks().set("mask_y", makeVariable<bool>(Dims{Dim::Y}, Shape{4},
                                             Values{true, true, false, true}));
  a.masks().set(
      "mask2d",
      makeVariable<bool>(Dims{Dim::X, Dim::Y}, Shape{6, 4},
                         Values{true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                true,  false, true,  false, true,  false,
                                true,  true,  true,  false, false, false}));

  const auto rshp = arange(Dim::Z, 24);
  DataArray expected(rshp);
  expected.coords().set(
      Dim::X,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.1, 0.1, 0.1, 0.1, 1.1, 1.1, 1.1, 1.1,
                                  2.1, 2.1, 2.1, 2.1, 3.1, 3.1, 3.1, 3.1,
                                  4.1, 4.1, 4.1, 4.1, 5.1, 5.1, 5.1, 5.1}));
  expected.coords().set(
      Dim::Y,
      makeVariable<double>(Dims{Dim::Z}, Shape{24},
                           Values{0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2,
                                  0.2, 1.2, 2.2, 3.2, 0.2, 1.2, 2.2, 3.2}));

  expected.masks().set(
      "mask_x",
      makeVariable<bool>(Dims{Dim::Z}, Shape{24},
                         Values{true,  true,  true,  true,  true,  true,
                                true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                false, false, false, false, false, false}));
  expected.masks().set(
      "mask_y", makeVariable<bool>(
                    Dims{Dim::Z}, Shape{24},
                    Values{true, true, false, true, true, true, false, true,
                           true, true, false, true, true, true, false, true,
                           true, true, false, true, true, true, false, true}));
  expected.masks().set(
      "mask2d",
      makeVariable<bool>(Dims{Dim::Z}, Shape{24},
                         Values{true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                true,  false, true,  false, true,  false,
                                true,  true,  true,  false, false, false}));

  EXPECT_EQ(unstack(a, {Dim::X, Dim::Y}, Dim::Z), expected);
}

TEST(StackingTest, round_trip_with_all) {
  const auto var = reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}});
  DataArray a(var);
  a.coords().set(Dim::X, arange(Dim::X, 7) + 0.1 * units::one);
  a.coords().set(Dim::Y, arange(Dim::Y, 4) + 0.2 * units::one);
  a.coords().set(Dim::Z,
                 reshape(arange(Dim::X, 24), {{Dim::X, 6}, {Dim::Y, 4}}) +
                     0.5 * units::one);
  a.attrs().set(Dim::Qx, arange(Dim::X, 6) + 0.3 * units::one);
  a.attrs().set(Dim::Qy, arange(Dim::Y, 4) + 0.4 * units::one);
  a.masks().set("mask_x", makeVariable<bool>(
                              Dims{Dim::X}, Shape{6},
                              Values{true, true, true, false, false, false}));
  a.masks().set("mask_y", makeVariable<bool>(Dims{Dim::Y}, Shape{4},
                                             Values{true, true, false, true}));
  a.masks().set(
      "mask2d",
      makeVariable<bool>(Dims{Dim::X, Dim::Y}, Shape{6, 4},
                         Values{true,  true,  true,  true,  true,  true,
                                false, false, false, false, false, false,
                                true,  false, true,  false, true,  false,
                                true,  true,  true,  false, false, false}));
  auto reshaped = stack(a, Dim::X, {{Dim::Row, 2}, {Dim::Tof, 3}});
  EXPECT_EQ(unstack(reshaped, {Dim::Row, Dim::Tof}, Dim::X), a);
}
