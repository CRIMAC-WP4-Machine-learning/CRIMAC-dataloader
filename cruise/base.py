from dataclasses import dataclass
from pathlib import Path
import xarray as xr
import pandas as pd
import numpy as np
import os
import warnings
from constants import *


@dataclass
class CruiseConfig:
    path: str
    require_annotations: bool
    require_bottom: bool
    require_school_boxes: bool


class Cruise:
    _config: CruiseConfig
    _data: xr.Dataset
    _bottom: xr.Dataset

    def __init__(self, config: CruiseConfig):
        self._config = config
        self.name = self._read_name()

        self._data = self._read_zarr_data(suffix=DATA_FILE_SUFFIX, required=True)
        self._annotations = self._read_zarr_data(suffix=ANNOTATION_FILE_SUFFIX, required=self._config.require_annotations)
        self._bottom = self._read_zarr_data(suffix=BOTTOM_FILE_SUFFIX, required=self._config.require_bottom)

        self._school_box_df = self._read_csv_data(suffix=SCHOOL_BOXES_FILE_SUFFIX, required=self._config.require_school_boxes)

    def _read_name(self):
        return os.path.split(self._config.path)[-1]

    def _read_zarr_data(self, suffix, required):
        filepath = os.path.join(*[self._config.path, 'ACOUSTIC', 'GRIDDED', f"{self.name}_{suffix}"])
        try:
            ds = xr.open_zarr(filepath, chunks={'frequency': 'auto'})
            return ds
        except FileNotFoundError:
            if required:
                raise FileNotFoundError(f"Required data for cruise `{self.name}` not found at `{filepath}`")
            else:
                warnings.warn(f"Optional data for cruise `{self.name}` not found at `{filepath}`")
                return None

    def _read_csv_data(self, suffix, required):
        filepath = os.path.join(*[self._config.path, 'ACOUSTIC', 'GRIDDED', f"{self.name}_{suffix}"])
        try:
            df = pd.read_csv(filepath)
            return df
        except FileNotFoundError:
            if required:
                raise FileNotFoundError(f"Required data for cruise `{self.name}` not found at `{filepath}`")
            else:
                warnings.warn(f"Optional data for cruise `{self.name}` not found at `{filepath}`")
                return None

    def frequencies(self):
        return self._data.frequency.values

    def num_pings(self):
        return int(self._data.sizes['ping_time'])

    def num_ranges(self):
        return int(self._data.sizes['range'])

    def annotations_available(self):
        return self._annotations is not None

    def bottom_available(self):
        return self._bottom is not None

    def school_boxes_available(self):
        return self._school_box_df is not None

    def annotations(self):
        pass

    def categories(self):
        if self._annotations is None:
            raise FileNotFoundError(f"Annotations are not available for cruise {self.name}")
        else:
            categories = self._annotations.category.values
            return sorted([cat for cat in categories if cat != -1])

    def get_seabed_vector(self):
        pass

    def get_sv_slice(self, start_ping: (int, None), end_ping: (int, None),
                     start_range: (int, None) = None, end_range: (int, None) = None,
                     frequencies: (int, list, None) = None):

        if start_range is None:
            start_range = 0
        if end_range is None:
            end_range = self.num_ranges() + 1

        if frequencies is None:
            frequencies = self.frequencies()

        data = self._data.sel(frequency=frequencies).isel(ping_time=slice(start_ping, end_ping),
                                                          range=slice(start_range, end_range))
        return data.sv

    def get_annotation_slice(self, start_ping: (int, None), end_ping: (int, None),
                        start_range: (int, None) = None, end_range: (int, None) = None,
                        categories: (int, list, None) = None):

        if start_range is None:
            start_range = 0
        if end_range is None:
            end_range = self.num_ranges()

        if categories is None:
            categories = self.categories()

        annotation = self._annotations.sel(category=categories).isel(ping_time=slice(start_ping, end_ping),
                                                                 range=slice(start_range, end_range))
        return annotation.annotation

    def get_school_boxes(self, start_ping: (int, None) = None, end_ping: (int, None) = None, start_range: (int, None) = None,
                         end_range: (int, None) = None, categories: (int, list, None) = None):
        df = self._school_box_df
        if start_ping is not None:
            df = df.loc[df.endpingindex >= start_ping]
        if end_ping is not None:
            df = df.loc[df.startpingindex < end_ping]
        if start_range is not None:
            df = df.loc[df.lowerdeptindex >= start_range]
        if end_range is not None:
            df = df.loc[df.upperdeptindex < end_range]

        if categories is None:
            categories = self.categories()
        if type(categories) == int:
            categories = [categories]

        df = df.loc[df.category.isin(categories)]

        return df
