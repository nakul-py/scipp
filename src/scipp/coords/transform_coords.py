# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)
# @author Simon Heybrock, Jan-Lukas Wynen
import dataclasses
from dataclasses import fields
from fractions import Fraction
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set, Union

from ..core import DataArray, Dataset, DimensionError, VariableError, bins, empty
from ..logging import get_logger
from .coord_table import Coord, CoordTable, Destination
from .graph import Graph, GraphDict, rule_sequence
from .options import Options
from .rule import ComputeRule, FetchRule, RenameRule, Rule, rule_output_names


def transform_coords(x: Union[DataArray, Dataset],
                     targets: Optional[Union[str, Iterable[str]]] = None,
                     /,
                     graph: Optional[GraphDict] = None,
                     *,
                     rename_dims: bool = True,
                     keep_aliases: bool = True,
                     keep_intermediate: bool = True,
                     keep_inputs: bool = True,
                     quiet: bool = False,
                     **kwargs: Callable) -> Union[DataArray, Dataset]:
    """Compute new coords based on transformations of input coords.

    See the section in the user guide on
    `Coordinate transformations <../../user-guide/coordinate-transformations.rst>`_
    for detailed explanations.

    Parameters
    ----------
    x:
        Input object with coords.
    targets:
        Name or list of names of desired output coords.
    graph:
        A graph defining how new coords can be computed from existing
        coords. This may be done in multiple steps.
        The graph is given by a :class:`dict` where:

        - Dict keys are :class:`str` or :class:`tuple` of :class:`str`,
          defining the names of outputs generated by a dict value.
        - Dict values are :class:`str` or a callable (function).
          If :class:`str`, this is a synonym for renaming a coord.
          If a callable, it must either return a single variable or a dict of
          variables. The argument names of callables must be coords in ``x`` or be
          computable by other nodes in ``graph``. The coord names can be overridden by
          the callable by providing a ``__transform_coords_input_keys__`` property,
          returning a list of coord names in the same order as the function arguments.
    rename_dims:
        Rename dimensions if the corresponding dimension coords
        are used as inputs and there is a single output coord
        that can be associated with that dimension.
        See the user guide for more details and examples.
        Default is True.
    keep_aliases:
        If True, aliases for coords defined in graph are
        included in the output. Default is True.
    keep_intermediate:
        Keep attributes created as intermediate results.
        Default is True.
    keep_inputs:
        Keep consumed input coordinates or attributes.
        Default is True.
    quiet:
        If True, no log output is produced. Otherwise, ``transform_coords``
        produces a log of its actions.
    **kwargs:
        Mapping of coords to callables. This can be used as an alternate and brief
        way of specifying targets and graph. If provided, neither ``targets`` nor
        ``graph`` may be given.

    Returns
    -------
    :
        New object with desired coords. Existing data and meta-data is shallow-copied.

    Examples
    --------

    Transform input coordinates ``x`` and ``y`` to a new output coordinate ``xy``:

      >>> da = sc.data.table_xyz(nrow=10)
      >>> transformed = da.transform_coords(xy=lambda x, y: x + y)

    Equivalent full syntax based on a target name and a graph:

      >>> da = sc.data.table_xyz(nrow=10)
      >>> transformed = da.transform_coords('xy', graph={'xy': lambda x, y: x + y})

    Multiple new coordinates can be computed at once. Here ``z2`` is setup as an alias
    of ``z``:

      >>> da = sc.data.table_xyz(nrow=10)
      >>> transformed = da.transform_coords(xy=lambda x, y: x + y, z2='z')

    This is equivalent to

      >>> da = sc.data.table_xyz(nrow=10)
      >>> graph = {'xy': lambda x, y: x + y, 'z2':'z'}
      >>> transformed = da.transform_coords(['xy', 'z2'], graph=graph)

    Multi-step transformations that do not keep intermediate results as coordinates can
    be performed with a graph containing nodes that depend on outputs of other nodes:

      >>> da = sc.data.table_xyz(nrow=10)
      >>> graph = {'xy': lambda x, y: x + y, 'xyz': lambda xy, z: xy + z}
      >>> transformed = da.transform_coords('xyz', graph=graph)
    """
    options = Options(rename_dims=rename_dims,
                      keep_aliases=keep_aliases,
                      keep_intermediate=keep_intermediate,
                      keep_inputs=keep_inputs,
                      quiet=quiet)
    for field in fields(options):
        if not isinstance(getattr(options, field.name), bool):
            raise TypeError(
                f"'{field.name}' is a reserved for keyword argument. "
                "Use explicit targets and graph arguments to create an output "
                "coordinate of this name.")

    if kwargs:
        if targets is not None or graph is not None:
            raise ValueError(
                "Explicit targets or graph not allowed since keyword arguments "
                f"{kwargs} define targets and graph.")

    if targets is None:
        targets = set(kwargs)
        graph = kwargs
    else:
        targets = {targets} if isinstance(targets, str) else set(targets)

    _transform = _transform_dataset if isinstance(x, Dataset) else _transform_data_array
    return _transform(x, targets=targets, graph=Graph(graph), options=options)


def show_graph(graph: GraphDict, size: str = None, simplified: bool = False):
    """Show graphical representation of a graph as required by
    :py:func:`transform_coords`

    Requires the `python-graphviz` package.

    Parameters
    ----------
    graph:
        Transformation graph to show.
    size:
        Size forwarded to graphviz, must be a string, "width,height"
        or "size". In the latter case, the same value is used for
        both width and height.
    simplified:
        If ``True``, do not show the conversion functions,
        only the potential input and output coordinates.

    Returns
    -------
    graph: graphviz.Digraph
        Can be displayed directly in Jupyter.
        See the
        `documentation <https://graphviz.readthedocs.io/en/stable/api.html#graphviz.Digraph>`_
        for details.

    Raises
    ------
    RuntimeError
        If graphviz is not installed.
    """  # noqa
    return Graph(graph).show(size=size, simplified=simplified)


def _transform_data_array(original: DataArray, targets: Set[str], graph: Graph,
                          options: Options) -> DataArray:
    graph = graph.graph_for(original, targets)
    rules = rule_sequence(graph)
    working_coords = CoordTable(rules, targets, options)
    dim_coords = set()
    for rule in rules:
        for name, coord in rule(working_coords).items():
            working_coords.add(name, coord)
            # Check if coord is a dimension-coord. Need to also check if it is in the
            # data dimensions because slicing can produce attrs with dims that are
            # no longer in the data.
            if name in original.dims and coord.has_dim(name):
                dim_coords.add(name)

    dim_name_changes = (_dim_name_changes(graph, dim_coords)
                        if options.rename_dims else {})
    if not options.quiet:
        _log_transform(rules, targets, dim_name_changes, working_coords)
    res = _store_results(original, working_coords, targets)
    return res.rename_dims(dim_name_changes)


def _transform_dataset(original: Dataset, targets: Set[str], graph: Graph, *,
                       options: Options) -> Dataset:
    # Note the inefficiency here in datasets with multiple items: Coord
    # transform is repeated for every item rather than sharing what is
    # possible. Implementing this would be tricky and likely error-prone,
    # since different items may have different attributes. Unless we have
    # clear performance requirements we therefore go with the safe and
    # simple solution
    if len(original) > 0:
        return Dataset(
            data={
                name: _transform_data_array(
                    original[name], targets=targets, graph=graph, options=options)
                for name in original
            })

    # Cannot keep attributes in output anyway.
    # So make sure they are removed as early as possible.
    options = dataclasses.replace(options,
                                  keep_inputs=False,
                                  keep_aliases=False,
                                  keep_intermediate=False)
    dummy = DataArray(empty(sizes=original.sizes), coords=original.coords)
    transformed = _transform_data_array(dummy,
                                        targets=targets,
                                        graph=graph,
                                        options=options)
    return Dataset(coords=transformed.coords)


def _log_transform(rules: List[Rule], targets: Set[str],
                   dim_name_changes: Mapping[str, str], coords: CoordTable) -> None:
    inputs = set(rule_output_names(rules, FetchRule))
    byproducts = {
        name
        for name in (set(rule_output_names(rules, RenameRule))
                     | set(rule_output_names(rules, ComputeRule))) - targets
        if coords.total_usages(name) < 0
    }
    preexisting = {target for target in targets if target in inputs}
    steps = [rule for rule in rules if not isinstance(rule, FetchRule)]

    message = f'Transformed coords ({", ".join(sorted(inputs))}) ' \
              f'-> ({", ".join(sorted(targets))})'
    if byproducts:
        message += f'\n  Byproducts:\n    {", ".join(sorted(byproducts))}'
    if dim_name_changes:
        dim_rename_steps = '\n'.join(f'    {t} <- {f}'
                                     for f, t in dim_name_changes.items())
        message += '\n  Renamed dimensions:\n' + dim_rename_steps
    if preexisting:
        message += ('\n  Outputs already present in input:'
                    f'\n    {", ".join(sorted(preexisting))}')
    message += '\n  Steps:\n' + ('\n'.join(f'    {rule}'
                                           for rule in steps) if steps else '    None')

    get_logger().info(message)


def _store_coord(da: DataArray, name: str, coord: Coord) -> None:

    def try_del(dest):
        if dest == Destination.coord:
            da.coords.pop(name, None)
            if da.bins is not None:
                da.bins.coords.pop(name, None)
        else:
            da.attrs.pop(name, None)
            if da.bins is not None:
                da.bins.attrs.pop(name, None)

    def store(x, c):
        if coord.destination == Destination.coord:
            x.coords[name] = c
        else:
            x.attrs[name] = c

    try_del(coord.destination.other)

    if coord.usages == 0:
        try_del(coord.destination)
    else:
        if coord.has_dense:
            store(da, coord.dense)
        if coord.has_event:
            try:
                store(da.bins, coord.event)
            except (DimensionError, VariableError):
                # Thrown on mismatching bin indices, e.g. slice
                da.data = da.data.copy()
                store(da.bins, coord.event)


def _store_results(da: DataArray, coords: CoordTable, targets: Set[str]) -> DataArray:
    da = da.copy(deep=False)
    if da.bins is not None:
        da.data = bins(**da.bins.constituents)
    for name, coord in coords.items():
        if name in targets:
            coord.destination = Destination.coord
        _store_coord(da, name, coord)
    return da


def _color_dims(graph: Graph, dim_coords: Set[str]) -> Dict[str, Dict[str, Fraction]]:
    colors = {
        coord: {dim: Fraction(0, 1)
                for dim in dim_coords}
        for coord in graph.nodes()
    }
    for dim in dim_coords:
        colors[dim][dim] = Fraction(1, 1)
        depth_first_stack = [dim]
        while depth_first_stack:
            coord = depth_first_stack.pop()
            children = tuple(graph.children_of(coord))
            for child in children:
                # test for produced dim coords
                if child not in dim_coords:
                    colors[child][dim] += colors[coord][dim] * Fraction(
                        1, len(children))
            depth_first_stack.extend(children)

    return colors


def _has_full_color_of_dim(colors: Dict[str, Fraction], dim: str) -> bool:
    return all(fraction == 1 if d == dim else fraction != 1
               for d, fraction in colors.items())


def _dim_name_changes(rule_graph: Graph, dim_coords: Set[str]) -> Dict[str, str]:
    colors = _color_dims(rule_graph, dim_coords)
    nodes = list(rule_graph.nodes_topologically())[::-1]
    name_changes = {}
    for dim in dim_coords:
        for node in nodes:
            if _has_full_color_of_dim(colors[node], dim):
                name_changes[dim] = node
                break
    return name_changes
