// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2022 Scipp contributors (https://github.com/scipp)
/// @file
/// @author Jan-Lukas Wynen
#pragma once

#include <functional>
#include <mutex>
#include <shared_mutex>
#include <vector>

#include "scipp/common/index.h"

#include "scipp-core_export.h"
#include "scipp/core/except.h"

namespace scipp::core {
namespace dict_detail {
template <class It1, class It2> struct ValueType {
  using type = std::pair<const typename It1::value_type,
                         std::add_lvalue_reference_t<typename It2::value_type>>;
};

template <class It1> struct ValueType<It1, void> {
  using type = std::add_lvalue_reference_t<typename It1::value_type>;
};

template <class Container, class It1, class It2, size_t... IteratorIndices>
class Iterator {
  static_assert(sizeof...(IteratorIndices) > 0 &&
                sizeof...(IteratorIndices) < 3);

public:
  using difference_type = std::ptrdiff_t;
  using value_type = typename ValueType<It1, It2>::type;
  using pointer = std::add_pointer_t<std::remove_reference_t<value_type>>;
  using reference = std::add_lvalue_reference_t<value_type>;

  template <class T>
  Iterator(std::reference_wrapper<Container> container, T &&it1)
      : m_iterators{std::forward<T>(it1)}, m_container(container),
        m_end_address(container.get().data() + container.get().size()) {}

  template <class T, class U>
  Iterator(std::reference_wrapper<Container> container, T &&it1, U &&it2)
      : m_iterators{std::forward<T>(it1), std::forward<U>(it2)},
        m_container(container),
        m_end_address(container.get().data() + container.get().size()) {}

  Iterator(const Iterator &other) = default;
  Iterator(Iterator &&other) noexcept = default;
  Iterator &operator=(const Iterator &other) = default;
  Iterator &operator=(Iterator &&other) noexcept = default;
  ~Iterator() noexcept = default;

  decltype(auto) operator*() const {
    expect_container_unchanged();
    if constexpr (sizeof...(IteratorIndices) == 1) {
      return *std::get<0>(m_iterators);
    } else {
      return std::make_pair(std::ref(*std::get<0>(m_iterators)),
                            std::ref(*std::get<1>(m_iterators)));
    }
  }

  Iterator &operator++() {
    expect_container_unchanged();
    (++std::get<IteratorIndices>(m_iterators), ...);
    return *this;
  }

  bool operator==(const Iterator &other) const noexcept {
    // Assuming m_iterators are always in sync.
    return std::get<0>(m_iterators) == std::get<0>(other.m_iterators);
  }

  bool operator!=(const Iterator &other) const noexcept {
    return !(*this == other);
  }

private:
  using IteratorStorage =
      std::tuple<typename std::tuple_element<IteratorIndices,
                                             std::tuple<It1, It2>>::type...>;

  IteratorStorage m_iterators;
  std::reference_wrapper<Container> m_container;
  const void *m_end_address;

  void expect_container_unchanged() const {
    if (m_container.get().data() + m_container.get().size() != m_end_address) {
      throw std::runtime_error("dictionary changed size during iteration");
    }
  }

  friend void swap(Iterator &a, Iterator &b) {
    swap(a.m_iterators, b.m_iterators);
    swap(a.m_container, b.m_container);
    std::swap(a.m_end_address, b.m_end_address);
  }
};

template <class Container, class It1, class It2 = void> struct IteratorType {
  using type = Iterator<Container, It1, It2, 0, 1>;
};

template <class Container, class It1>
struct IteratorType<Container, It1, void> {
  using type = Iterator<Container, It1, void, 0>;
};
} // namespace dict_detail
} // namespace scipp::core

namespace std {
template <class Container, class It1, class It2, size_t... IteratorIndices>
struct iterator_traits<scipp::core::dict_detail::Iterator<Container, It1, It2,
                                                          IteratorIndices...>> {
private:
  using I = scipp::core::dict_detail::Iterator<Container, It1, It2,
                                               IteratorIndices...>;

public:
  using difference_type = typename I::difference_type;
  using value_type = typename I::value_type;
  using pointer = typename I::pointer;
  using reference = typename I::reference;

  // It is a forward iterator for most use cases.
  // But it misses
  //  - post-increment: it++ and *it++  (easy, but not needed right now)
  //  - arrow: it->  (difficult because of temporary pair)
  using iterator_category = std::forward_iterator_tag;
};
} // namespace std

namespace scipp::core {
template <class Key, class Value> class SCIPP_CORE_EXPORT Dict {
  using Keys = std::vector<Key>;
  using Values = std::vector<Value>;

public:
  using key_type = Key;
  using mapped_type = Value;
  using value_iterator =
      typename dict_detail::IteratorType<Values,
                                         typename Values::iterator>::type;
  using iterator =
      typename dict_detail::IteratorType<Keys, typename Keys::const_iterator,
                                         typename Values::iterator>::type;
  using const_key_iterator =
      typename dict_detail::IteratorType<const Keys,
                                         typename Keys::const_iterator>::type;
  using const_value_iterator =
      typename dict_detail::IteratorType<const Values,
                                         typename Values::const_iterator>::type;
  using const_iterator =
      typename dict_detail::IteratorType<const Keys,
                                         typename Keys::const_iterator,
                                         typename Values::const_iterator>::type;

  // moving and destroying not thread safe
  // and only safe on LHS off assignment, not RHS
  Dict() = default;
  ~Dict() noexcept = default;
  Dict(const Dict &other)
      : m_keys(other.m_keys), m_values(other.m_values), m_mutex() {}
  Dict(Dict &&other) noexcept = default;
  Dict &operator=(const Dict &other) {
    std::unique_lock lock_self_{m_mutex};
    m_keys = other.m_keys;
    m_values = other.m_values;
    return *this;
  }
  Dict &operator=(Dict &&other) noexcept = default;

  /// Return the number of elements.
  [[nodiscard]] index size() const noexcept { return scipp::size(m_keys); }
  /// Return true if there are 0 elements.
  [[nodiscard]] bool empty() const noexcept { return size() == 0; }
  /// Return the number of elements that space is currently allocated for.
  [[nodiscard]] index capacity() const noexcept { return m_keys.capacity(); }

  void reserve(const index new_capacity) {
    std::unique_lock lock_{m_mutex};
    m_keys.reserve(new_capacity);
    m_values.reserve(new_capacity);
  }

  [[nodiscard]] bool contains(const Key &key) const noexcept {
    std::shared_lock lock_{m_mutex};
    return find(key) != -1;
  }

  template <class V> void insert_or_assign(const key_type &key, V &&value) {
    std::unique_lock lock_{m_mutex};
    if (const auto idx = find(key); idx == -1) {
      m_keys.push_back(key);
      m_values.emplace_back(std::forward<V>(value));
    } else {
      m_values[idx] = std::forward<V>(value);
    }
  }

  [[nodiscard]] const mapped_type &operator[](const key_type &key) const {
    std::shared_lock lock_{m_mutex};
    return m_values[expect_find(key)];
  }

  [[nodiscard]] mapped_type &operator[](const key_type &key) {
    std::shared_lock lock_{m_mutex};
    return m_values[expect_find(key)];
  }

  [[nodiscard]] auto keys_begin() const noexcept {
    return const_key_iterator(m_keys, m_keys.cbegin());
  }

  [[nodiscard]] auto keys_end() const noexcept {
    return const_key_iterator(m_keys, m_keys.cend());
  }

  [[nodiscard]] auto values_begin() noexcept {
    return value_iterator(m_values, m_values.begin());
  }

  [[nodiscard]] auto values_end() noexcept {
    return value_iterator(m_values, m_values.end());
  }

  [[nodiscard]] auto values_begin() const noexcept {
    return const_value_iterator(m_values, m_values.begin());
  }

  [[nodiscard]] auto values_end() const noexcept {
    return const_value_iterator(m_values, m_values.end());
  }

  [[nodiscard]] auto begin() noexcept {
    return iterator(m_keys, m_keys.cbegin(), m_values.begin());
  }

  [[nodiscard]] auto end() noexcept {
    return iterator(m_keys, m_keys.cend(), m_values.end());
  }

  [[nodiscard]] auto begin() const noexcept {
    return const_iterator(m_keys, m_keys.cbegin(), m_values.begin());
  }

  [[nodiscard]] auto end() const noexcept {
    return const_iterator(m_keys, m_keys.cend(), m_values.begin());
  }

private:
  Keys m_keys;
  Values m_values;
  mutable std::shared_mutex m_mutex;

  scipp::index find(const Key &key) const noexcept {
    const auto it = std::find(m_keys.begin(), m_keys.end(), key);
    if (it == m_keys.end()) {
      return -1;
    }
    return std::distance(m_keys.begin(), it);
  }

  scipp::index expect_find(const Key &key) const {
    if (const auto idx = find(key); idx != -1) {
      return idx;
    }
    using std::to_string;
    throw except::NotFoundError(to_string(key));
  }
};
} // namespace scipp::core
