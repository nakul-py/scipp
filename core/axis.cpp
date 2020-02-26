// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2020 Scipp contributors (https://github.com/scipp)
/// @file
/// @author Simon Heybrock
#include "scipp/core/axis.h"
#include "scipp/core/view_decl.h"

namespace scipp::core {

void UnalignedAccess::set(const std::string &key, Variable var) const {
  m_unaligned->insert_or_assign(key, std::move(var));
}
void UnalignedAccess::erase(const std::string &key) const {
  m_unaligned->erase(m_unaligned->find(key));
}

DatasetAxis::DatasetAxis(const DatasetAxisConstView &data)
    : m_data(Variable(data.data())) {}

UnalignedConstView DatasetAxis::unaligned() const {
  typename UnalignedConstView::holder_type items;
  for (const auto &[key, value] : m_unaligned)
    items.emplace(key, std::pair{&value, nullptr});
  return unaligned_const_view_type{std::move(items)};
}

UnalignedView DatasetAxis::unaligned() {
  typename UnalignedConstView::holder_type items;
  for (auto &&[key, value] : m_unaligned)
    items.emplace(key, std::pair{&value, &value});
  return unaligned_view_type{UnalignedAccess(this, &m_unaligned),
                             std::move(items)};
}

const UnalignedConstView &DatasetAxisConstView::unaligned() const noexcept {
  return m_unaligned;
}

const UnalignedView &DatasetAxisView::unaligned() const noexcept {
  return m_unaligned;
}

void DatasetAxis::rename(const Dim from, const Dim to) {
  m_data.rename(from, to);
}

bool operator==(const DatasetAxisConstView &a, const DatasetAxisConstView &b) {
  return a.data() == b.data() && a.unaligned() == b.unaligned();
}
bool operator!=(const DatasetAxisConstView &a, const DatasetAxisConstView &b) {
  return !(a == b);
}
bool operator==(const VariableConstView &a, const DatasetAxisConstView &b) {
  return a == b.data() && b.unaligned().empty();
}
bool operator!=(const VariableConstView &a, const DatasetAxisConstView &b) {
  return !(a == b);
}
bool operator==(const DatasetAxisConstView &a, const VariableConstView &b) {
  return b == a;
}
bool operator!=(const DatasetAxisConstView &a, const VariableConstView &b) {
  return !(a == b);
}

DatasetAxisView DatasetAxisView::
operator+=(const VariableConstView &other) const {
  data() += other;
  for (const auto &item : unaligned())
    item.second += other;
  return *this;
}
DatasetAxisView DatasetAxisView::
operator-=(const VariableConstView &other) const {
  data() -= other;
  for (const auto &item : unaligned())
    item.second -= other;
  return *this;
}
DatasetAxisView DatasetAxisView::
operator*=(const VariableConstView &other) const {
  data() *= other;
  for (const auto &item : unaligned())
    item.second *= other;
  return *this;
}
DatasetAxisView DatasetAxisView::
operator/=(const VariableConstView &other) const {
  data() /= other;
  for (const auto &item : unaligned())
    item.second /= other;
  return *this;
}
DatasetAxisView DatasetAxisView::
operator+=(const DatasetAxisConstView &) const {
  throw std::runtime_error("Operations between axes not supported yet.");
}
DatasetAxisView DatasetAxisView::
operator-=(const DatasetAxisConstView &) const {
  throw std::runtime_error("Operations between axes not supported yet.");
}
DatasetAxisView DatasetAxisView::
operator*=(const DatasetAxisConstView &) const {
  throw std::runtime_error("Operations between axes not supported yet.");
}
DatasetAxisView DatasetAxisView::
operator/=(const DatasetAxisConstView &) const {
  throw std::runtime_error("Operations between axes not supported yet.");
}

DatasetAxis resize(const DatasetAxisConstView &var, const Dim dim,
                   const scipp::index size) {
  return DatasetAxis(resize(var.data(), dim, size));
}
DatasetAxis concatenate(const DatasetAxisConstView &a,
                        const DatasetAxisConstView &b, const Dim dim) {
  return DatasetAxis(concatenate(a.data(), b.data(), dim));
}

DatasetAxis copy(const DatasetAxisConstView &axis) {
  DatasetAxis out(Variable(axis.data()));
  for (const auto &item : axis.unaligned())
    out.unaligned().set(item.first, Variable(item.second));
  return out;
}

DatasetAxis flatten(const DatasetAxisConstView &, const Dim) {
  throw std::runtime_error("flatten not supported yet.");
}

} // namespace scipp::core
