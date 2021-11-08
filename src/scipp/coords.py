# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2021 Scipp contributors (https://github.com/scipp)
# @author Simon Heybrock, Jan-Lukas Wynen

from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from enum import Enum, auto
from graphlib import TopologicalSorter
import inspect
from typing import Any, Callable, Dict, Iterable, List, Mapping,\
    Optional, Set, Tuple, Union

from .core import CoordError, DataArray, Dataset, NotFoundError, VariableError,\
    Variable, bins
from .logging import get_logger

_OptionalCoordTuple = Tuple[Optional[Variable], Optional[Variable]]
GraphDict = Dict[Union[str, Tuple[str, ...]], Union[str, Callable]]


def _argnames(func) -> Tuple[str]:
    spec = inspect.getfullargspec(func)
    if spec.varargs is not None or spec.varkw is not None:
        raise ValueError('Function with variable arguments not allowed in'
                         f' conversion graph: `{func.__name__}`.')
    return tuple(spec.args + spec.kwonlyargs)


def _make_digraph(*args, **kwargs):
    try:
        from graphviz import Digraph
    except ImportError:
        raise RuntimeError('Failed to import `graphviz`, please install `graphviz` if '
                           'using `pip`, or `python-graphviz` if using `conda`.')
    return Digraph(*args, **kwargs)


@dataclass(frozen=True)
class _Options:
    rename_dims: bool
    include_aliases: bool
    keep_intermediate: bool
    keep_inputs: bool


class _Destination(Enum):
    coord = auto()
    attr = auto()


@dataclass
class _Coord:
    dense: Variable  # for dense variable or bin-coord
    event: Variable
    destination: _Destination

    @property
    def has_dense(self) -> bool:
        return self.dense is not None

    @property
    def has_event(self) -> bool:
        return self.event is not None


class _Rule(ABC):
    def __init__(self, out_names: Union[str, Tuple[str]]):
        self.out_names = (out_names, ) if isinstance(out_names, str) else out_names

    @abstractmethod
    def __call__(self, coords: Dict[str, Variable]) -> Dict[str, Variable]:
        """Evaluate the kernel."""

    @property
    @abstractmethod
    def dependencies(self) -> Tuple[str]:
        """Return names of coords that this kernel needs as inputs."""

    @staticmethod
    def _consume_coord(name: str, coords: Mapping[str, _Coord]) -> Variable:
        coord = coords[name]
        coord.destination = _Destination.attr
        return coord

    def _format_out_names(self):
        return str(self.out_names) if len(self.out_names) > 1 else self.out_names[0]


class _FetchRule(_Rule):
    def __init__(self, out_names: Union[str, Tuple[str, ...]],
                 dense_sources: Mapping[str, Variable],
                 event_sources: Optional[Mapping[str, Variable]]):
        super().__init__(out_names)
        self._dense_sources = dense_sources
        self._event_sources = event_sources

    def __call__(self, _) -> Dict[str, _Coord]:
        # TODO remove from sources, requires that sources are for output da not original!
        return {
            out_name: _Coord(dense=self._dense_sources.get(out_name, None),
                             event=self._event_sources.get(out_name, None)
                             if self._event_sources else None,
                             destination=_Destination.coord)
            for out_name in self.out_names
        }

    @property
    def dependencies(self) -> Tuple[str]:
        return ()  # type: ignore

    def __str__(self):
        return f'Input   {self._format_out_names()}'


class _RenameRule(_Rule):
    def __init__(self, out_names: Union[str, Tuple[str, ...]], in_name: str):
        super().__init__(out_names)
        self._in_name = in_name

    def __call__(self, coords: Mapping[str, _Coord]) -> Dict[str, _Coord]:
        return {
            out_name: copy(self._consume_coord(self._in_name, coords))
            for out_name in self.out_names
        }

    @property
    def dependencies(self) -> Tuple[str]:
        return tuple((self._in_name, ))

    def __str__(self):
        return f'Rename  {self._format_out_names()} = {self._in_name}'


class _ComputeRule(_Rule):
    def __init__(self, out_names: Union[str, Tuple[str, ...]], func: Callable):
        super().__init__(out_names)
        self._func = func
        self._arg_names = _argnames(func)

    def __call__(self, coords: Mapping[str, _Coord]) -> Dict[str, _Coord]:
        inputs = {name: self._consume_coord(name, coords) for name in self._arg_names}
        if not any(coord.has_event for coord in inputs.values()):
            outputs = self._compute_pure_dense(inputs)
        else:
            outputs = self._compute_with_events(inputs)
        return self._without_unrequested(outputs)

    def _compute_pure_dense(self, inputs):
        outputs = self._func(**{name: coord.dense for name, coord in inputs.items()})
        outputs = self._to_dict(outputs)
        return {
            name: _Coord(dense=var, event=None, destination=_Destination.coord)
            for name, var in outputs.items()
        }

    def _compute_with_events(self, inputs):
        args = {name: coord.event if coord.has_event else coord.dense
                for name, coord in inputs.items()}
        outputs = self._to_dict(self._func(**args))
        # Dense outputs may be produced as side effects of processing event
        # coords.
        outputs = {name: _Coord(dense=var if var.bins is None else None,
                                event=var if var.bins is not None else None,
                                destination=_Destination.coord)
                   for name, var in outputs.items()}
        return outputs

    def _without_unrequested(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return {key: val for key, val in d.items() if key in self.out_names}

    def _to_dict(self, output) -> Dict[str, Variable]:
        if not isinstance(output, dict):
            if len(self.out_names) != 1:
                raise TypeError('Function returned a single output but '
                                f'{len(self.out_names)} were expected.')
            return {self.out_names[0]: output}
        return output

    @property
    def dependencies(self) -> Tuple[str]:
        return self._arg_names

    def __str__(self):
        return f'Compute {self._format_out_names()} = {self._func.__name__}' \
               f'({", ".join(self._arg_names)})'


def _make_rule(products, producer) -> _Rule:
    if isinstance(producer, str):
        return _RenameRule(products, producer)
    return _ComputeRule(products, producer)


def _non_duplicate_rules(rules: Mapping[str, _Rule]) -> List[_Rule]:
    already_used = set()
    result = []
    for rule in filter(lambda r: r not in already_used,
                       map(lambda n: rules[n], _sort_topologically(rules))):
        already_used.add(rule)
        result.append(rule)
    return result


def _convert_to_rule_graph(graph: GraphDict) -> Dict[str, _Rule]:
    rule_graph = {}
    for products, producer in graph.items():
        rule = _make_rule(products, producer)
        for product in (products, ) if isinstance(products, str) else products:
            if product in rule_graph:
                raise ValueError(
                    f'Duplicate output name defined in conversion graph: {product}')
            rule_graph[product] = rule
    return rule_graph


def _sort_topologically(graph: Mapping[str, _Rule]) -> Iterable[str]:
    yield from TopologicalSorter(
        {out: rule.dependencies
         for out, rule in graph.items()}).static_order()


def _is_meta_data(name: str, data:DataArray)->bool:
    return name in data.meta or (data.bins is not None and name in data.bins.meta)


class Graph:
    def __init__(self, graph):
        self._graph = _convert_to_rule_graph(graph)

    def subgraph(self, data: DataArray, targets: Tuple[str, ...]) -> Dict[str, _Rule]:
        subgraph = {}
        pending = list(targets)
        while pending:
            out_name = pending.pop()
            if out_name in subgraph:
                continue
            rule = self._rule_for(out_name, data)
            subgraph[out_name] = rule
            pending.extend(rule.dependencies)
        return subgraph

    def _rule_for(self, out_name: str, data: DataArray) -> _Rule:
        if _is_meta_data(out_name, data):
            return _FetchRule(out_name, data.meta,
                              data.bins.meta if data.bins else None)
        try:
            return self._graph[out_name]
        except KeyError:
            raise CoordError(
                f"Coordinate '{out_name}' does not exist in the input data "
                "and no rule has been provided to compute it.") from None

    def show(self, size=None, simplified=False):
        dot = _make_digraph(strict=True)
        dot.attr('node', shape='box', height='0.1')
        dot.attr(size=size)
        for output, rule in self._graph.items():
            if isinstance(rule, _RenameRule):  # rename
                dot.edge(rule.dependencies[0], output, style='dashed')
            else:
                if not simplified:
                    # TODO
                    name = f'{rule._func.__name__}(...)'
                    dot.node(name, shape='ellipse', style='filled', color='lightgrey')
                    dot.edge(name, output)
                else:
                    name = output
                for arg in rule.dependencies:
                    dot.edge(arg, name)
        return dot


def _log_plan(rules: List[_Rule], dim_name_changes: Mapping[str, str]) -> None:
    get_logger().info('''Transforming coords
  Renaming dimensions:
%s
  Rules:
%s''', '\n'.join(f'    {f} -> {t}' for f, t in dim_name_changes.items()),
                      '\n'.join(f'    {rule}' for rule in rules))


def _store_coord(data: DataArray, name: str, coord: _Coord):
    def out(x):
        return x.coords if coord.destination == _Destination.coord else x.attrs

    def del_other(x):
        try:
            if coord.destination == _Destination.coord:
                del x.attrs[name]
            else:
                del x.coords[name]
        except NotFoundError:
            pass

    if coord.has_dense:
        out(data)[name] = coord.dense
        del_other(data)
    if coord.has_event:
        try:
            out(data.bins)[name] = coord.event
        except VariableError:
            # Thrown on mismatching bin indices, e.g. slice
            data.data = data.data.copy()
            out(data.bins)[name] = coord.event
        del_other(data.bins)


def _store_results(data: DataArray, coords: Dict[str, _Coord], targets: Tuple[str, ...],
                   blacklist: Set[str]) -> DataArray:
    data = data.copy(deep=False)
    if data.bins is not None:
        data.data = bins(**data.bins.constituents)
    for name, coord in coords.items():
        if name in blacklist:
            continue
        if name in targets:
            coord.destination = _Destination.coord
        _store_coord(data, name, coord)
    return data


def _rules_of_type(rules: List[_Rule], rule_type: type) -> Iterable[_Rule]:
    yield from filter(lambda rule: isinstance(rule, rule_type), rules)


def _rule_output_names(rules: List[_Rule], rule_type: type) -> Iterable[str]:
    for rule in _rules_of_type(rules, rule_type):
        yield from rule.out_names


def _storage_blacklist(targets: Tuple[str, ...], rules: List[_Rule],
                       options: _Options) -> Set[str]:
    def _out_names(rule_type):
        yield from filter(lambda name: name not in targets,
                          _rule_output_names(rules, rule_type))

    blacklist = set()
    inputs = set(_out_names(_FetchRule))
    if not options.keep_inputs:
        for inp in inputs:
            blacklist.add(inp)
    if not options.keep_intermediate:
        for rule in rules:
            for dep in rule.dependencies:
                if dep not in inputs:
                    blacklist.add(dep)
    if not options.include_aliases:
        for alias in _out_names(_RenameRule):
            blacklist.add(alias)
    return blacklist


def _initial_dims_to_rename(x: DataArray, rules: List[_Rule]) -> Dict[str, List[str]]:
    res = {}
    for rule in filter(lambda r: isinstance(r, _FetchRule), rules):
        for name in rule.out_names:
            if name in x.dims:
                res[name] = []
    return res


def _rules_with_dep(dep, rules):
    return list(filter(lambda r: dep in r.dependencies, rules))


# A coords dim can be renamed if its node
#  1. has one incoming dim coord
#  2. has only one outgoing connection
#
# This functions traversed the graph in depth-first order
# and builds a dict of old->new names according to the conditions above.
def _dim_name_changes(rules: List[_Rule], dims: List[str]) -> Dict[str, str]:
    dim_coords = tuple(name for name in _rule_output_names(rules, _FetchRule)
                       if name in dims)
    pending = list(dim_coords)
    incoming_dim_coords = {name: [name] for name in pending}
    name_changes = {}
    while pending:
        name = pending.pop(0)
        if len(incoming_dim_coords[name]) != 1:
            continue  # Condition 1.
        dim = incoming_dim_coords[name][0]
        name_changes[dim] = name
        outgoing = _rules_with_dep(name, rules)
        if len(outgoing) == 1 and len(outgoing[0].out_names) == 1:
            # Potential candidate according to condition 2.
            pending.append(outgoing[0].out_names[0])
        for rule in filter(lambda r: len(r.out_names) == 1, outgoing):
            # Condition 2. is not satisfied for these children but we
            # still need to take the current node into account for 1.
            incoming_dim_coords.setdefault(rule.out_names[0], []).append(dim)
    return name_changes


def _transform_data_array(original: DataArray, coords: Union[str, List[str],
                                                             Tuple[str, ...]],
                          graph: GraphDict, options: _Options) -> DataArray:
    targets = tuple(coords)
    rules = _non_duplicate_rules(Graph(graph).subgraph(original, targets))
    dim_name_changes = _dim_name_changes(rules,
                                         original.dims) if options.rename_dims else {}
    _log_plan(rules, dim_name_changes)
    working_coords = {}
    for rule in rules:
        for name, coord in rule(working_coords).items():
            if name in working_coords and name not in rule.dependencies:
                raise RuntimeError(f"Coordinate '{name}' was produced multiple times.")
            working_coords[name] = coord
            if options.rename_dims:
                ren = list(filter(lambda xx: xx in rename_dims, rule.dependencies()))
                if len(ren) == 1:
                    rename_dims[ren[0]].append(name)
                    rename_dims[name] = []

    res = _store_results(x, working_coords, targets)
    return _rename_dims(res, x, rename_dims)


def _move_between_member_dicts(obj, name: str, src_name: str,
                               dst_name: str) -> Optional[Variable]:
    src = getattr(obj, src_name)
    dst = getattr(obj, dst_name)
    if name in src:
        dst[name] = src.pop(name)
    return dst.get(name, None)


def _move_between_coord_and_attr(obj, name: str, src_name: str,
                                 dst_name: str) -> _OptionalCoordTuple:
    return (_move_between_member_dicts(obj, name, src_name, dst_name),
            _move_between_member_dicts(obj.bins, name, src_name, dst_name)
            if obj.bins is not None else None)


def _consume_coord(obj, name: str) -> _OptionalCoordTuple:
    return _move_between_coord_and_attr(obj, name, 'coords', 'attrs')


def _produce_coord(obj, name: str) -> _OptionalCoordTuple:
    return _move_between_coord_and_attr(obj, name, 'attrs', 'coords')


def _store_event_coord(obj, name: str, coord: Variable) -> None:
    try:
        obj.bins.coords[name] = coord
    except VariableError:  # Thrown on mismatching bin indices, e.g. slice
        obj.data = obj.data.copy()
        obj.bins.coords[name] = coord
    if name in obj.bins.attrs:
        del obj.bins.attrs[name]


def _store_coord(obj, name: str, coord: _OptionalCoordTuple) -> None:
    dense_coord, event_coord = coord
    if dense_coord is not None:
        obj.coords[name] = dense_coord
    if name in obj.attrs:
        # If name is both an input and output to a function,
        # the input handling made it an attr, but since it is
        # an output, we want to store it as a coord (and only as a coord).
        del obj.attrs[name]
    if event_coord is not None:
        _store_event_coord(obj, name, event_coord)


def _call_function(func: Callable[..., Union[Variable, Dict[str, Variable]]],
                   args: Dict[str, Variable], out_name: str) -> Dict[str, Variable]:
    out = func(**args)
    if not isinstance(out, dict):
        return {out_name: out}
    for name in out:
        get_logger().info('  %s = %s(%s)', name, func.__name__, ', '.join(args.keys()))
    return out


class CoordTransform:
    def __init__(self, obj: DataArray, *, graph: Graph, outputs: Tuple[str]):
        self.obj = obj.copy(deep=False)
        # TODO We manually shallow-copy the buffer, until we have a better
        # solution for how shallow copies also shallow-copy event buffers.
        if self.obj.bins is not None:
            self.obj.data = bins(**self.obj.bins.constituents)
        self._original = obj
        self._events_copied = False
        self._rename: Dict[Tuple[str], List[str]] = {}
        self._memo: List[str] = []  # names of product for cycle detection
        self._aliases: List[str] = []  # names that alias other names
        self._consumed: List[str] = []  # names that have been consumed
        self._outputs: Tuple[str] = outputs  # names of outputs
        self._graph = graph

    def _add_coord(self, *, name: str):
        if self._exists(name):
            return _produce_coord(self.obj, name)
        if isinstance(self._graph[name], str):
            out, dim = self._rename_coord(name)
        else:
            out, dim = self._compute_coord(name)
        self._rename.setdefault(dim, []).extend(out.keys())
        for key, coord in out.items():
            _store_coord(self.obj, key, coord)

    def _rename_coord(self,
                      name: str) -> Tuple[Dict[str, _OptionalCoordTuple], Tuple[str]]:
        self._aliases.append(name)
        out = {name: self._get_coord(self._graph[name])}
        dim = (self._graph[name], )
        return out, dim

    def _compute_coord(self,
                       name: str) -> Tuple[Dict[str, _OptionalCoordTuple], Tuple[str]]:
        func = self._graph[name]
        argnames = _argnames(func)
        args = {arg: self._get_coord(arg) for arg in argnames}
        have_all_dense_inputs = all([v[0] is not None for v in args.values()])
        if have_all_dense_inputs:
            out = _call_function(func, {k: v[0] for k, v in args.items()}, name)
        else:
            out = {}
        have_event_inputs = any([v[1] is not None for v in args.values()])
        if have_event_inputs:
            event_args = {k: v[0] if v[1] is None else v[1] for k, v in args.items()}
            out_bins = _call_function(func, event_args, name)
            # Dense outputs may be produced as side effects of processing event
            # coords.
            for name in list(out_bins.keys()):
                if out_bins[name].bins is None:
                    coord = out_bins.pop(name)
                    if name in out:
                        assert identical(out[name], coord)
                    else:
                        out[name] = coord
        else:
            out_bins = {}
        out = {
            k: (out.get(k, None), out_bins.get(k, None))
            for k in list(out.keys()) + list(out_bins.keys())
        }
        dim = tuple(argnames)
        return out, dim

    def _exists(self, name: str):
        in_events = self.obj.bins is not None and name in self.obj.bins.meta
        return name in self.obj.meta or in_events

    def _get_existing(self, name: str):
        events = None if self.obj.bins is None else self.obj.bins.meta[name]
        return self.obj.meta.get(name, None), events

    def _get_coord(self, name: str):
        if self._exists(name):
            self._consumed.append(name)
            if name in self._outputs:
                return self._get_existing(name)
            else:
                return _consume_coord(self.obj, name)
        else:
            if name in self._memo:
                raise ValueError("Cycle detected in conversion graph.")
            self._memo.append(name)
            self._add_coord(name=name)
            return self._get_coord(name)

    def _del_attr(self, name: str):
        self.obj.attrs.pop(name, None)
        if self.obj.bins is not None:
            self.obj.bins.attrs.pop(name, None)

    res = _store_results(original, working_coords, targets,
                         _storage_blacklist(coords, rules, options))
    return res.rename_dims(dim_name_changes)


def _transform_dataset(obj: Dataset, coords: Union[str, List[str], Tuple[str, ...]],
                       graph: GraphDict, *, options: _Options) -> Dataset:
    # Note the inefficiency here in datasets with multiple items: Coord
    # transform is repeated for every item rather than sharing what is
    # possible. Implementing this would be tricky and likely error-prone,
    # since different items may have different attributes. Unless we have
    # clear performance requirements we therefore go with the safe and
    # simple solution
    return Dataset(
        data={
            name: _transform_data_array(
                obj[name], coords=coords, graph=graph, options=options)
            for name in obj
        })


def transform_coords(x: Union[DataArray, Dataset],
                     coords: Union[str, List[str], Tuple[str, ...]],
                     graph: GraphDict,
                     *,
                     rename_dims=True,
                     include_aliases=True,
                     keep_intermediate=True,
                     keep_inputs=True) -> Union[DataArray, Dataset]:
    """Compute new coords based on transformation of input coords.

    :param x: Input object with coords.
    :param coords: Name or list of names of desired output coords.
    :param graph: A graph defining how new coords can be computed from existing
                  coords. This may be done in multiple steps.
                  The graph is given by a `dict` where:

                  - Dict keys are `str` or `tuple` of `str`, defining the
                    names of outputs generated by a dict value.
                  - Dict values are `str` or a callable (function). If `str`,
                    this is a synonym for renaming a coord. If a callable,
                    it must either return a single variable or a dict of
                    variables.
    :param rename_dims: Rename dimensions if products of dimension coord are
                        fully consumed and consumer consumes exactly one
                        dimension coordinate. Default is True.
    :param include_aliases: If True, aliases for coords defined in graph are
                            included in the output. Default is False.
    :param keep_intermediate: Keep attributes created as intermediate results.
                              Default is True.
    :param keep_inputs: Keep consumed input coordinates or attributes.
                        Default is True.
    :return: New object with desired coords. Existing data and meta-data is
             shallow-copied.
    """
    options = _Options(rename_dims=rename_dims,
                       include_aliases=include_aliases,
                       keep_intermediate=keep_intermediate,
                       keep_inputs=keep_inputs)
    if isinstance(x, DataArray):
        return _transform_data_array(x, coords=coords, graph=graph, options=options)
    else:
        return _transform_dataset(x, coords=coords, graph=graph, options=options)


def show_graph(graph: GraphDict, size: str = None, simplified: bool = False):
    """
    Show graphical representation of a graph as required by
    :py:func:`transform_coords`

    Requires `python-graphviz` package.

    :param graph: Transformation graph to show.
    :param size: Size forwarded to graphviz, must be a string, "width,height"
                 or "size". In the latter case, the same value is used for
                 both width and height.
    :param simplified: If ``True``, do not show the conversion functions,
                       only the potential input and output coordinates.
    """
    return Graph(graph).show(size=size, simplified=simplified)
