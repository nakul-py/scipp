#ifndef DATASET_H
#define DATASET_H

#include <vector>

#include "data_array.h"
#include "dimension.h"
#include "index.h"
#include "variable.h"

class Dataset {
public:
  void add(DataArray variable) {
    // TODO prevent duplicate names (if type matches)
    mergeDimensions(variable.dimensions());
    m_variables.push_back(std::move(variable));
  }

  template <class Tag, class... Args>
  void add(const std::string &name, Dimensions dimensions, Args &&... args) {
    auto a =
        makeDataArray<Tag>(std::move(dimensions), std::forward<Args>(args)...);
    a.setName(name);
    add(std::move(a));
  }

  template <class Tag, class T>
  void add(const std::string &name, Dimensions dimensions,
           std::initializer_list<T> values) {
    auto a = makeDataArray<Tag>(std::move(dimensions), values);
    a.setName(name);
    add(std::move(a));
  }

  // TODO addAsEdge

  gsl::index size() const { return m_variables.size(); }
  const DataArray &operator[](gsl::index i) const { return m_variables[i]; }

  // TODO need (helper) types for values and errors (instead of
  // std::vector<double>, which
  // would be duplicate). This is also the reason for T being the column type,
  // not the element type.
  template <class Tag> variable_type_t<Tag> &get() {
    for (auto &item : m_variables) {
      // TODO check for duplicate column types (can use get based on name in
      // that case).
      if (item.type() == Tag::type_id)
        return item.get<Tag>();
    }
    throw std::runtime_error("Dataset does not contain such a variable");
  }

  std::map<Dimension, gsl::index> dimensions() const {
    std::map<Dimension, gsl::index> dims;
    for (gsl::index i = 0; i < m_dimensions.count(); ++i)
      dims[m_dimensions.label(i)] = m_dimensions.size(i);
    return dims;
  }

  template <class Tag> std::vector<Dimension> dimensions() const {
    for (auto &item : m_variables) {
      if (item.type() == Tag::type_id) {
        std::vector<Dimension> dims;
        for (gsl::index i = 0; i < item.dimensions().count(); ++i)
          dims.push_back(item.dimensions().label(i));
        return dims;
      }
    }
    throw std::runtime_error("Dataset does not contain such a column");
  }

private:
  void mergeDimensions(const auto &dims) {
    gsl::index j = 0;
    gsl::index found = 0;
    for (gsl::index i = 0; i < dims.count(); ++i) {
      const auto dim = dims.label(i);
      const auto size = dims.size(i);
      bool found = false;
      for (; j < m_dimensions.count(); ++j) {
        if (m_dimensions.label(j) == dim) {
          if (m_dimensions.size(j) != size) // TODO compare ragged
            throw std::runtime_error(
                "Cannot add variable to Dataset: Dimensions do not match");
          found = true;
          break;
        }
      }
      if (!found) {
        if (m_dimensions.contains(dim))
          throw std::runtime_error(
              "Cannot add variable to Dataset: Dimension order mismatch");
        m_dimensions.add(dim, size);
      }
    }
  }

  Dimensions m_dimensions;
  std::vector<DataArray> m_variables;
};

inline Dataset concatenate(const Dimension dim, const Dataset &d1,
                           const Dataset &d2) {
  // Match type and name, drop missing?
  // What do we have to do to check and compute the resulting dimensions?
  // - If dim is in m_dimensions, *some* of the variables contain it. Those that
  //   do not must then be identical (do not concatenate) or we could
  //   automatically broadcast? Yes!?
  // - If dim is new, concatenate variables if different, copy if same.
  // We will be doing deep comparisons here, it would be nice if we could setup
  // sharing, but d1 and d2 are const, is there a way...? Not without breaking
  // thread safety? Could cache cow_ptr for future sharing setup, done by next
  // non-const op?
  Dataset out;
  for (gsl::index i1 = 0; i1 < d1.size(); ++i1) {
    const auto &var1 = d1[i1];
    bool found{false};
    for (gsl::index i2 = 0; i2 < d2.size(); ++i2) {
      const auto &var2 = d2[i2];
      if ((var1.type() == var2.type()) && (var1.name() == var2.name())) {
        // TODO check if data is the same, do not concatenate if this is a new
        // dimension.
        out.add(concatenate(dim, var1, var2));
        break;
      }
    }
  }
  return out;
}

#endif // DATASET_H
