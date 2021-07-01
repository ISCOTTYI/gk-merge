import logging
import os
import json
import progressbar
import numpy as np
from gkmerge.generators import erdos_renyi, fast_erdos_renyi
from gkmerge.network import Network

from time import time

logger = logging.getLogger(__name__)

__all__ = [
    "ContagionWindow"
]

class Simulation():
    def __init__(self, write_path=None, **attr):
        self.attr = dict(attr)
        self.data = dict()
        if write_path is not None:
            self.write_path = write_path
        else:
            self.write_path = os.path.expanduser("~")
    
    def run(self):
        raise NotImplementedError("Not implemented by Simulation base class!")

    def run_and_write(self, file_name):
        self.run()
        self.write(file_name)
    
    def setup_progressbar(self, maxval):
        return progressbar.ProgressBar(maxval=maxval, widgets=[
            progressbar.Timer(), " ",
            progressbar.Bar("=", "[", "]"), " ",
            progressbar.Percentage(),
        ])

    def add_data(self, key, data):
        new_data = {key: data}
        if key in self.data:
            raise KeyError(f"Key '{key}' is already in dataset!")
        self.data.update(new_data)
    
    def point_range(self, min_val, max_val, number_of_points, digits=4):
        nums = np.linspace(min_val, max_val, num=number_of_points)
        return [round(i, digits) for i in nums]
    
    def write_to(self, path):
        self.write_path = path

    def write(self, file_name):
        file_path = os.path.join(self.write_path, f"{file_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(dict(attributes=self.attr, data=self.data), f, ensure_ascii=False, indent=4)


class ContagionWindow(Simulation):
    """
    Contagion Window simulation. Returns data
    {
        p value 1: [
            data from run 1, data from run 2, . . .
        ]
        .
        .
        .
    }.
    """
    def __init__(
            self, number_of_banks, p_min, p_max, p_points,
            runs_per_p, alpha, kappa, contagion_mode="simultaneous", write_path=None
        ):
        attr = dict(
            n=number_of_banks, p_min=p_min, p_max=p_max, p_points=p_points,
            p_vals=self.point_range(p_min, p_max, p_points),
            runs=runs_per_p, kappa=kappa, alpha=alpha, mode=contagion_mode
        )
        super().__init__(write_path=write_path, **attr)
    
    def _setup_network(self, p):
        attr = self.attr
        return fast_erdos_renyi(attr["n"], p, attr["alpha"], attr["kappa"])
    
    def _fetch_rundata(self, network: Network):
        data = dict(df=network.defaulted_fraction(), z=network.z())
        steps = network.simultaneous_cascade_steps
        if steps is not None:
            data.update(steps=steps)
        return data
    
    def run(self):
        attr = self.attr
        progbar = self.setup_progressbar(attr["p_points"])
        progbar.start()
        for i, p in enumerate(attr["p_vals"]):
            progbar.update(i + 1)
            p_data = []
            for _ in range(attr["runs"]):
                progbar.update()
                network = self._setup_network(p)
                network.cascade(network.shock_random(), mode=attr["mode"])
                p_data.append(self._fetch_rundata(network))
            self.add_data(p, p_data)
        progbar.finish()
