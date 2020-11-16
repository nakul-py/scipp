// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2020 Scipp contributors (https://github.com/scipp)
/// @file
/// @author Simon Heybrock
#include <iostream>
#include <numeric>

#include "scipp/core/element/histogram.h"
#include "scipp/core/element/permute.h"
#include "scipp/core/parallel.h"
#include "scipp/core/tag_util.h"

#include "scipp/variable/arithmetic.h"
#include "scipp/variable/bins.h"
#include "scipp/variable/reduction.h"
#include "scipp/variable/shape.h"
#include "scipp/variable/subspan_view.h"
#include "scipp/variable/transform.h"
#include "scipp/variable/util.h"
#include "scipp/variable/variable_factory.h"

#include "scipp/dataset/bins.h"
#include "scipp/dataset/bins_view.h"
#include "scipp/dataset/bucketby.h"
#include "scipp/dataset/except.h"

#include "dataset_operations_common.h"

namespace scipp::dataset {

namespace {

template <class T> auto find_sorting_permutation(const T &key) {
  element_array<scipp::index> p(key.size(), core::default_init_elements);
  std::iota(p.begin(), p.end(), 0);
  core::parallel::parallel_sort(
      p.begin(), p.end(), [&](auto i, auto j) { return key[i] < key[j]; });
  return p;
}

Variable bin_index(const VariableConstView &var,
                   const VariableConstView &edges) {
  const auto dim = edges.dims().inner();
  if (all(is_linspace(edges, dim)).value<bool>()) {
    return variable::transform(var, subspan_view(edges, dim),
                               core::element::bin_index_linspace);
  } else {
    if (!is_sorted(edges, dim))
      throw except::BinEdgeError("Bin edges must be sorted.");
    return variable::transform(var, subspan_view(edges, dim),
                               core::element::bin_index_sorted_edges);
  }
}

void update_indices_by_binning(const VariableView &indices,
                               const VariableConstView &key,
                               const VariableConstView &edges) {
  const auto dim = edges.dims().inner();
  if (all(is_linspace(edges, dim)).value<bool>()) {
    variable::transform_in_place(
        indices, key, subspan_view(edges, dim),
        core::element::update_indices_by_binning_linspace);
  } else {
    if (!is_sorted(edges, dim))
      throw except::BinEdgeError("Bin edges must be sorted.");
    variable::transform_in_place(
        indices, key, subspan_view(edges, dim),
        core::element::update_indices_by_binning_sorted_edges);
  }
}

Variable groups_to_map(const VariableConstView &var, const Dim dim) {
  return variable::transform(subspan_view(var, dim),
                             core::element::groups_to_map);
}

Variable group_index(const VariableConstView &var,
                     const VariableConstView &groups) {
  const auto dim = groups.dims().inner();
  const auto map = groups_to_map(groups, dim);
  return variable::transform(var, map, core::element::group_index);
}

void update_indices_by_grouping(const VariableView &indices,
                                const VariableConstView &key,
                                const VariableConstView &groups) {
  const auto dim = groups.dims().inner();
  const auto map = groups_to_map(groups, dim);
  variable::transform_in_place(indices, key, map,
                               core::element::update_indices_by_grouping);
}

void bin_index_to_full_index(const VariableView &index,
                             const Dimensions &dims) {
  auto sizes = makeVariable<scipp::index>(Dims{Dim::X}, Shape{dims.volume()});
  variable::accumulate_in_place(subspan_view(sizes, Dim::X), index,
                                core::element::bin_index_to_full_index);
}

auto shrink(const Dimensions &dims) {
  auto shrunk = dims;
  shrunk.resize(dims.inner(), dims[dims.inner()] - 1);
  return shrunk;
}

/// `dims` provides dimensions of pre-existing binning, `edges` define
/// additional dimensions.
Variable bin_sizes(const VariableConstView &indices, Dimensions dims) {
  Variable sizes = makeVariable<scipp::index>(dims);
  const auto s = sizes.values<scipp::index>().as_span();
  for (const auto i : indices.values<scipp::index>().as_span())
    if (i >= 0)
      ++s[i];
  return sizes;
}

template <class T> Variable as_subspan_view(T &&binned) {
  if (binned.dtype() == dtype<bin<Variable>>) {
    auto &&[indices, dim, buffer] =
        binned.template constituents<bin<Variable>>();
    return subspan_view(buffer, dim, indices);
  } else if (binned.dtype() == dtype<bin<VariableView>>) {
    auto &&[indices, dim, buffer] =
        binned.template constituents<bin<VariableView>>();
    return subspan_view(buffer, dim, indices);
  } else {
    auto &&[indices, dim, buffer] =
        binned.template constituents<bin<VariableConstView>>();
    return subspan_view(buffer, dim, indices);
  }
}

/// indices is a binned variable with sub-bin indices, i.e., new bins within
/// bins
Variable bin_sizes2(const VariableConstView &sub_bin, const scipp::index nbin) {
  const auto nbins = broadcast(nbin * units::one, sub_bin.dims());
  auto sizes = resize(sub_bin, nbins);
  buckets::reserve(sizes, nbins);
  // const auto &[indices, dim, buffer] =
  // sizes.constituents<bucket<Variable>>();
  // TODO how can we avoid writing subspan_view
  // transform_in_place(subspan_view(buffer, dim, indices),
  // subspan_view(sub_bin));
  variable::transform_in_place(
      as_subspan_view(sizes), as_subspan_view(sub_bin),
      core::element::count_indices); // transform bins, not bin element

  // Variable slices = makeVariable<scipp::index_pair>(
  //    Dims{dim}, Shape{indices.dims.volume() * nbin});
  // Variable sizes = makeVariable<scipp::index>(
  //    Dims{dim}, Shape{indices.dims.volume() * nbin});

  // const auto s = sizes.values<scipp::index>().as_span();
  // for (const auto i : indices.values<scipp::index>().as_span())
  //  if (i >= 0)
  //    ++s[i];
  return sizes;
}

// Notes on threaded impl:
//
// If event is in existing bin, it will stay there. Can use existing bin sizes
// as view over output, and threading will work
// Example:
// - existing pixel binning
// - now bin TOF
// - output has (potentially smaller) pixel bins, use subspan_view
// transform_in_place(subspan_view(out, out_buffer_dim, out_bin_range), data,
// indices)
// => threading over pixel dim
//
// What about binning flat data? order is completely random?
// - sc.bins() with dummy indices => fake 1d binning
//   - maybe use make_non_owning_bins?
// - transpose bucket end/begin (essentially making new dim an outer dim)
//   - can we achieve this by specifying reverse dim order, with no extra code?
// - proceeed as above

template <class T> struct Bin {
  static auto apply(const VariableConstView &var,
                    const VariableConstView &indices,
                    const VariableConstView &sizes) {
    auto [begin, total_size] = sizes_to_begin(sizes);
    auto dims = var.dims();
    // Output may be smaller since values outside bins are dropped.
    dims.resize(dims.inner(), total_size);
    auto binned = variable::variableFactory().create(
        var.dtype(), dims, var.unit(), var.hasVariances());
    const auto indices_ = indices.values<scipp::index>().as_span();
    const auto values = var.values<T>().as_span();
    const auto binned_values = binned.values<T>().as_span();
    const auto current = begin.values<scipp::index>().as_span();
    const auto size = scipp::size(values);
    if (var.hasVariances()) {
      const auto variances = var.variances<T>().as_span();
      const auto binned_variances = binned.variances<T>().as_span();
      for (scipp::index i = 0; i < size; ++i) {
        const auto i_bin = indices_[i];
        if (i_bin < 0)
          continue;
        binned_variances[current[i_bin]] = variances[i];
        binned_values[current[i_bin]++] = values[i];
      }
    } else {
      for (scipp::index i = 0; i < size; ++i) {
        const auto i_bin = indices_[i];
        if (i_bin < 0)
          continue;
        binned_values[current[i_bin]++] = values[i];
      }
    }
    return binned;
  }
};

auto bin(const VariableConstView &var, const VariableConstView &indices,
         const VariableConstView &sizes) {
  return core::CallDType<double, float, int64_t, int32_t, bool, Eigen::Vector3d,
                         std::string>::apply<Bin>(var.dtype(), var, indices,
                                                  sizes);
}

template <class Out>
auto bin2(Out &&out, const Variable &in, const VariableConstView &indices,
          const VariableConstView &sizes) {
  // Size/begin of all sub-bins of an input bin
  // auto [begin, total_size] = sizes_to_begin(buckets::sum(sizes));
  // Output may be smaller since values outside sub-bins are dropped.
  // `binned` does not contain sub-bin dims/ranges yet
  // const auto filtered_input_bin_size = buckets::sum(sizes);
  // auto binned = resize(data, filtered_input_bin_size);
  // buckets::reserve(binned, filtered_input_bin_size);
  /*
  auto dims = in_buffer.dims();
  dims.resize(dim, total_size);
  auto binned_buffer = variable::variableFactory().create(
      in_buffer.dtype(), dims, in_buffer.unit(), in_buffer.hasVariances());
      */

  // if we also use binned_slices, can we "push back"
  // const auto begin_end = unzip(binned_slices);
  // Need:
  // target bin indices *within* input bin (no need for existing bin index!?
  // how to make subspan view covering multiple dims? reshape first?
  // use a binned var instead?
  //
  // bin_sizes should be var of same dims as (binned) input with (equal sized)
  // bins containing list of output bin sizes
  //
  // indices has same dims as (binned) input, "transform" to different bin
  // sizes?

  // data should be bins_view
  transform_in_place(as_subspan_view(out), as_subspan_view(sizes),
                     as_subspan_view(in), as_subspan_view(indices),
                     core::element::bin);
  // return std::get<2>(binned.to_constituents<bucket<Variable>>());

  // transform_in_place(subspan_view(binned_buffer, dim, binned_slices),
  //                   subspan_view(binned_slices, /* all dims not in input */),
  //                   subspan_view(in_buffer, dim, in_slices),
  //                   subspan_view(indices, dim, ), core::element::bin);
}

auto bin(const DataArrayConstView &data, const VariableConstView &indices,
         const VariableConstView &sizes) {
  return dataset::transform(data, [indices, sizes](const auto &var) {
    return var.dims().contains(indices.dims().inner())
               ? bin(var, indices, sizes)
               : copy(var);
  });
}

auto bin2(const VariableConstView &data, const VariableConstView &indices,
          const Dimensions &dims) {
  std::cout << data << '\n';
  std::cout << indices << '\n';
  std::cout << dims << '\n';
  const auto nbin = dims.volume();
  const auto output_bin_sizes = bin_sizes2(indices, nbin);
  const auto filtered_input_bin_size = buckets::sum(output_bin_sizes);
  auto binned = resize(data, filtered_input_bin_size);
  buckets::reserve(binned, filtered_input_bin_size);

  const auto input_bins = bins_view<DataArray>(data);
  const auto output_bins = bins_view<DataArray>(binned);
  bin2(output_bins.data(), input_bins.data(), output_bin_sizes, indices);

  const auto output_dims = merge(data.dims(), dims);
  const auto bin_sizes =
      reshape(std::get<2>(output_bin_sizes.constituents<bucket<Variable>>()),
              output_dims);
  // TODO take into account rebin
  const auto [begin, total_size] = sizes_to_begin(bin_sizes);
  const auto end = begin + bin_sizes;
  auto [ignored_filtered_input_bin_indices, dim, buffer] =
      binned.to_constituents<bucket<DataArray>>();
  std::cout << begin << '\n';
  std::cout << end << '\n';
  return make_bins(zip(begin, end), dim, std::move(buffer));
}

Variable permute(const VariableConstView &var, const Dim dim,
                 const VariableConstView &permutation) {
  return variable::transform(subspan_view(var, dim), permutation,
                             core::element::permute);
}

template <class T> struct MakePermutation {
  static auto apply(const VariableConstView &key) {
    expect::isKey(key);
    // Using span over data since random access via ElementArrayView is slow.
    return makeVariable<scipp::index>(
        key.dims(),
        Values(find_sorting_permutation(key.values<T>().as_span())));
  }
};

auto permute(const DataArrayConstView &data, const Dim dim,
             const VariableConstView &permutation) {
  return dataset::transform(data, [dim, permutation](const auto &var) {
    return var.dims().contains(dim) ? permute(var, dim, permutation)
                                    : copy(var);
  });
}
} // namespace

template <class T>
auto call_sortby(const T &array, const VariableConstView &key) {
  return permute(
      array, key.dims().inner(),
      core::CallDType<double, float, int64_t, int32_t, bool,
                      std::string>::apply<MakePermutation>(key.dtype(), key));
}

template <class... T>
DataArray sortby_impl(const DataArrayConstView &array, const T &... dims) {
  return call_sortby(array, array.coords()[dims]...);
}

DataArray sortby(const DataArrayConstView &array, const Dim dim) {
  return sortby_impl(array, dim);
}

namespace {
DataArray bucketby_impl(const VariableConstView &var,
                        const std::vector<VariableConstView> &edges,
                        const std::vector<VariableConstView> &groups,
                        const std::vector<Dim> &) {
  const auto &[begin_end, dim, array] = var.constituents<bucket<DataArray>>();
  const auto input_bins = bins_view<DataArray>(var);
  const auto [begin, end] = unzip(begin_end);
  const auto input_bin_sizes = bucket_sizes(array.data());
  // zeros_like?
  auto indices =
      make_bins(copy(begin_end), dim, makeVariable<scipp::index>(array.dims()));
  Dimensions dims;
  for (const auto &group : groups) {
    const auto group_dim = group.dims().inner();
    const auto coord = input_bins.coords()[group_dim];
    update_indices_by_grouping(indices, coord, group);
    dims.addInner(group_dim, group.dims()[group_dim]);
  }
  for (const auto &edge : edges) {
    const auto edge_dim = edge.dims().inner();
    const auto coord = input_bins.coords()[edge_dim];
    // TODO does this mean we can do ragged only in two steps?
    // i.e., indices must have same outer dim as edge
    update_indices_by_binning(indices, coord, edge);
    dims.addInner(edge_dim, edge.dims()[edge_dim] - 1);
  }
  // Now `indices` contains the target bucket index for every event.
  //
  // TODO what now? bin_index_to_full_index?
  // also giving bin_sizes?

  /*
for (const auto &edge : edges) {
  const auto coord = array.coords()[edge.dims().inner()];
  // TODO This implicit way of distinguishing edges and non-edges is probably
  // not the ultimate desired solution.
  const bool is_edges =
      (edge.dtype() == dtype<float>) || (edge.dtype() == dtype<double>);
  const auto inner_indices =
      is_edges ? bin_index(coord, edge) : group_index(coord, edge);
  const auto nbin = edge.dims()[edge.dims().inner()] - (is_edges ? 1 : 0);
  dims = merge(dims, is_edges ? shrink(edge.dims()) : edge.dims());
  if (indices) {
    if (bucket_dim != coord.dims().inner())
      throw except::DimensionError(
          "Coords of data to be bucketed have inconsistent dimensions " +
          to_string(bucket_dim) + " and " + to_string(coord.dims().inner()) +
          ". Data that can be bucketed should generally resemble a table, "
          "with a coord column for each bucketed dimension.");
    indices = variable::transform<scipp::index>(
        indices, inner_indices,
        overloaded{[](const units::Unit &, const units::Unit &) {
                     return units::one;
                   },
                   [nbin](const auto i0, const auto i1) {
                     return i0 < 0 || i1 < 0 ? -1 : i0 * nbin + i1;
                   }});
  } else {
    indices = inner_indices;
  }
  bucket_dim = coord.dims().inner();
}
const auto sizes = bin_sizes(indices, dims);
const auto [begin, total_size] = sizes_to_begin(sizes);
const auto end = begin + sizes;
*/
  // TODO We probably want to omit the coord used for grouping in the non-edge
  // case, since it just contains the same value duplicated for every row in the
  // bin.
  // Note that we should then also recreate that variable in concatenate, to
  // ensure that those operations are reversible.
  auto binned = bin2(var, indices, dims);
  std::map<Dim, Variable> coords;
  for (const auto &edge : edges)
    coords[edge.dims().inner()] = copy(edge);
  return {binned, std::move(coords)};
}
} // namespace

// for edges in edges:
//   indices += (bin_index(coord, edge, stride))
// multi-threading:
// - binned view over indices
// - threads: sizes = count(indices)
// - compute offset in output based on accumulation of sizes over threads
// - threads: copy via binned view over indices to output
//
// output is always contiguous
// indices is contiguous
// input is not
// => transform with 3 args? ... but how to split then?
// binned view over output

Variable make_index_range(const Dim dim, const scipp::index size) {
  auto var = makeVariable<scipp::index>(Dims{dim}, Shape{size});
  auto vals = var.values<scipp::index>().as_span();
  std::iota(vals.begin(), vals.end(), 0);
  return var;
}

DataArray bucketby(const DataArrayConstView &array,
                   const std::vector<VariableConstView> &edges,
                   const std::vector<VariableConstView> &groups,
                   const std::vector<Dim> &dim_order) {
  // DataArrayConstView maybe_concat(array);
  // DataArray tmp;
  if (array.dtype() == dtype<bucket<DataArray>>) {
    /*
    // TODO The need for this check may be an indicator that we should support
    // adding another bucketed dimension via a separate function instead of
    // having this dual-purpose `bucketby`.
    for (const auto &edge : edges)
      if (array.dims().contains(edge.dims().inner())) {
        // TODO Very inefficient if new edges extract only a small fraction
        tmp = buckets::concatenate(maybe_concat, edge.dims().inner());
        maybe_concat = DataArrayView(tmp);
      }
    const auto &[begin_end, dim, buffer] =
        maybe_concat.data().constituents<bucket<DataArray>>();
    auto indices =
        makeVariable<scipp::index>(Dims{dim}, Shape{buffer.dims()[dim]});
    indices -= 1 * units::one;
    const auto indices_ = indices.values<scipp::index>().as_span();
    scipp::index current = 0;
    // TODO too restrictive, may want to bin a slice
    for (const auto [begin, end] : begin_end.values<index_pair>().as_span()) {
      for (scipp::index i = begin; i < end; ++i)
        indices_[i] = current;
      ++current;
    }
    */

#if 0
    // 1. Build dims if empty
    // TODO take into account dim_order, including handling grouping without
    // given groups
    static_cast<void>(dim_order) Dimensions binning_dims;
    for (const auto &group : groups)
      binning_dims.add_inner(group.dims().inner());
    for (const auto &edge : edges)
      binning_dims.add_inner(edge.dims().inner());

    // 2. Build input bin index table
    auto indices = makeVariable<scipp::index>(0);
    for (const auto dim : array.dims().labels()) {
      size = array.dims()[dim];
      indices *= size * units::one;
      if (binning_dims.contains[dim]) // changed binning, pretend same input bin
        indices = indices + makeVariable<scipp::index>(Dims{dim}, Shape{size});
      else
        indices = indices + make_index_range(dim, size);
    }

    // 3. Broadcast table to all events in bin
    indices = broadcast(indices, end - begin);

    auto bucketed = bucketby_impl(buffer, edges, groups, dim_order,
                                  std::move(indices), dim, begin_end.dims());
#endif
    // const auto input_bin_sizes = bucket_sizes(array.data());
    // auto indices =
    //    resize(makeVariable<scipp::index>(Values{0}), input_bin_sizes);
    // buckets::reserve(indices, input_bin_sizes);

    auto bucketed = bucketby_impl(array.data(), edges, groups, dim_order);
    copy_metadata(array, bucketed);
    return bucketed;
  } else {
    const auto dim = array.dims().inner();
    const auto begin = makeVariable<scipp::index>(Values{0});
    const auto end = makeVariable<scipp::index>(Values{array.dims()[dim]});
    // TODO use bins_view instead
    const auto tmp = DataArray(make_bins(zip(begin, end), dim, copy(array)));
    return bucketby(tmp, edges, groups, dim_order);
    // return bucketby_impl(maybe_concat, edges, groups, dim_order);
  }
}

} // namespace scipp::dataset
