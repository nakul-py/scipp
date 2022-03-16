# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

from ..units import one
from .pipeline import Pipeline
import numpy as np
from dataclasses import dataclass
from typing import Callable
from functools import partial


@dataclass
class DataProcessor:
    """
    """
    func: Callable
    values: dict


class Controller:
    """
    Controller class plots.
    """
    def __init__(
        self,
        # dims,
        # vmin=None,
        # vmax=None,
        # norm=None,
        # scale=None,
        # widgets=None,
        models,
        view,
        # preprocessors=None
    ):
        # self._dims = dims
        # self.widgets = widgets
        self._models = models
        self._view = view
        # self.preprocessors = preprocessors
        self._pipelines = {key: Pipeline() for key in self._models}

        # self.vmin = vmin
        # self.vmax = vmax
        # self.norm = norm if norm is not None else "linear"

        # # self.scale = {dim: "linear" for dim in self._dims}
        # if scale is not None:
        #     for dim, item in scale.items():
        #         self.scale[dim] = item

    def add_pipeline_step(self, step, key=None):
        if key is None:
            keys = self._pipelines.keys()
        else:
            keys = [key]
        for k in keys:
            self._pipelines[k].append(step)
            step.register_callback(partial(self._run_pipeline, key=k))

    def render(self):
        """
        Update axes (and data) to render the figure once all components
        have been created.
        """
        # self.widgets.connect(controller=self)
        # self.view.connect(controller=self)
        # if self.panel is not None:
        #     self.panel.controller = self
        self._run_all_pipelines()

    # def _make_data_processors(self):
    #     return [
    #         DataProcessor(func=p.func, values=p.widget.values())
    #         for p in self.preprocessors
    #     ]

    def _run_all_pipelines(self):
        for key in self._pipelines:
            self._run_pipeline(key, draw=False)
        self._view.draw()

    def _run_pipeline(self, key, draw=True):
        new_values = self._pipelines[key].run(self._models[key])
        new_values.name = key
        self._view.update(new_values, draw=draw)

    # # def update(self, *, slices=None):
    # def update(self):
    #     """
    #     This function is called when the data in the displayed 1D plot or 2D
    #     image is to be updated. This happens for instance when we move a slider
    #     which is navigating an additional dimension. It is also always
    #     called when update_axes is called since the displayed data needs to be
    #     updated when the axes have changed.
    #     """
    #     # if slices is None:
    #     #     slices = self.widgets.slices
    #     # else:
    #     #     slices.update(self.widgets.slices)

    #     data_processors = self._make_data_processors()

    #     # slices = self.widgets.slices
    #     new_values = self.model.update(data_processors=data_processors)
    #     print(new_values)
    #     # change to: new_values = self.model[slices]
    #     # Model could just be a data array

    #     # INSERT additional post-processing here
    #     # - a generic function to do, for example, some custom resampling

    #     # self.widgets.update_slider_readout(new_values.meta)

    #     self.view.update(new_values)  #, mask_info=self.get_masks_info())
    #     # if self.panel is not None:
    #     #     self.panel.update_data(new_values)
    #     # if self.profile is not None:
    #     #     self._update_slice_area()

    def toggle_mask(self):
        pass