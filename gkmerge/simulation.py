import logging
import os
import json
import progressbar
import numpy as np
from gkmerge.generators import chung_lu, erdos_renyi, fast_erdos_renyi, directed_barabasi_albert
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
        if file_name[-5:] == ".json":
            file_name = file_name[:-5]
        file_path = os.path.join(self.write_path, f"{file_name}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(dict(attributes=self.attr, data=self.data), f, ensure_ascii=False, indent=4)
        print(f"--- Data successfully written to '{os.path.join(self.write_path, file_name)}'! ---")


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
    # def __init__(
    #         self, number_of_banks, p_min, p_max, p_points,
    #         runs_per_p, alpha, kappa, contagion_mode="simultaneous", write_path=None
    #     ):
    #     attr = dict(
    #         n=number_of_banks, p_min=p_min, p_max=p_max, p_points=p_points,
    #         p_vals=self.point_range(p_min, p_max, p_points),
    #         runs=runs_per_p, kappa=kappa, alpha=alpha, mode=contagion_mode
    #     )
    #     super().__init__(write_path=write_path, **attr)
    
    def __init__(self, write_path=None, **attr):
        super().__init__(write_path=write_path, **attr)
        self._network_gen = None
        self._progbar_max = 0
        self._z_modifiers = []
    
    def use_erdos_renyi(
        self, n=1000, p_min=0, p_max=0.01, p_points=25,
        runs=1000, alpha=0.2, kappa=0.04, shock_mode="random",
        contagion_mode="simultaneous", recovery_rate=0,
        deprecation_factor=0.0, c=0.0
    ):
        p_vals = self.point_range(p_min, p_max, p_points)
        self.attr.update(
            gen="erdos_renyi", n=n, p_min=p_min, p_max=p_max, p_points=p_points,
            p_vals=p_vals, runs=runs, alpha=alpha, kappa=kappa, shock_mode=shock_mode,
            contagion_mode=contagion_mode, recovery_rate=recovery_rate,
            deprecation_factor=deprecation_factor, c=c
        )
        self._network_gen = "er"
        self._progbar_max = p_points
        self._z_modifiers = p_vals
    
    def use_chung_lu(
        self, n=1000, z_min=0, z_max=12, z_points=25,
        gamma=3, runs=1000, alpha=0.2, kappa=0.04, shock_mode="random", 
        contagion_mode="simultaneous", recovery_rate=0,
        deprecation_factor=0.0, c=0.0
    ):
        z_vals = self.point_range(z_min, z_max, z_points)
        self.attr.update(
            gen="chung_lu", n=n, z_min=z_min, z_max=z_max, z_points=z_points, gamma=gamma,
            z_vals=z_vals, runs=runs, alpha=alpha, kappa=kappa, shock_mode=shock_mode, 
            contagion_mode=contagion_mode, recovery_rate=recovery_rate,
            deprecation_factor=deprecation_factor, c=c
        )
        self._network_gen = "cl"
        self._progbar_max = z_points
        self._z_modifiers = z_vals
    
    def _setup_network(self, x):
        if self._network_gen == "er":
            return fast_erdos_renyi(
                self.attr["n"], x, alpha=self.attr["alpha"], kappa=self.attr["kappa"],
                c=self.attr["c"]
            )
        if self._network_gen == "cl":
            return chung_lu(
                self.attr["n"], x, gamma=self.attr["gamma"],
                alpha=self.attr["alpha"], kappa=self.attr["kappa"],
                c=self.attr["c"]
            )
        else:
            raise SystemError("Network generator not yet set up.")
    
    def _fetch_rundata(self, network: Network):
        data = dict(
            df=network.defaulted_fraction(),
            z=network.z(),
            af=network.defaulted_asset_fraction()
        )
        steps = network.simultaneous_cascade_steps
        if steps is not None:
            data.update(steps=steps)
        return data
    
    def run(self):
        if self._network_gen is None:
            raise SystemError("Network generator not yet set up.")
        progbar = self.setup_progressbar(self._progbar_max)
        progbar.start()
        for i, x in enumerate(self._z_modifiers):
            progbar.update(i + 1)
            x_data = []
            for _ in range(self.attr["runs"]):
                progbar.update()
                network = self._setup_network(x)
                sm = self.attr["shock_mode"]
                if sm == "random":
                    sb = network.shock_random()
                elif sm == "max_in_deg":
                    sb = network.shock_max_in_deg()
                else:
                    raise SystemError("Unknown shock mode!")
                network.cascade(
                    sb,
                    mode=self.attr["contagion_mode"],
                    recovery_rate=self.attr["recovery_rate"],
                    deprecation_factor=self.attr["deprecation_factor"]
                )
                x_data.append(self._fetch_rundata(network))
            self.add_data(x, x_data)
        progbar.finish()


class ContinousMergers(Simulation):
    """
    ContinousMergers simulation. Tracks stability measures over merge rounds
    for given z_modifier. Returns data:
    {
        merge round 0: [
            data from realization 1 at mr=0, data from realization 2 at mr=0, . . .
        ]
        .
        . 
        .
    }
    """
    def __init__(self, write_path=None, **attr):
        super().__init__(write_path=write_path, **attr)
        self._network_gen = None
        self._progbar_max = 0
    
    def _append_to_mr_data(self, mr, realization_data_set):
        self.data[mr].append(realization_data_set)
    
    def _setup_data_dict(self):
        self.data = {mr: [] for mr in self.attr["mr_vals"]}
    
    def use_erdos_renyi(
        self, n=1000, p=0.005, mr_min=0, mr_max=500, mr_points=20,
        runs=1000, alpha=0.2, kappa=0.04, shock_mode="random",
        contagion_mode="simultaneous", merge_rule="random",
        deprecation_factor=0.0, c=0.0
    ):
        mr_vals = range(mr_min, mr_max + 1, int(mr_max / mr_points))
        self.attr.update(
            gen="erdos_renyi", n=n, p=p, mr_min=mr_min, mr_max=mr_max, mr_points=mr_points,
            mr_vals=list(mr_vals), runs=runs, alpha=alpha, kappa=kappa,
            shock_mode=shock_mode, contagion_mode=contagion_mode, merge_rule=merge_rule,
            deprecation_factor=deprecation_factor, c=c

        )
        self._network_gen = "er"
        self._progbar_max = runs
        self._z_modifier = p
        self._setup_data_dict()
    
    def use_chung_lu(
        self, n=1000, z=5, gamma=3, mr_min=0, mr_max=500, mr_points=20,
        runs=1000, alpha=0.2, kappa=0.04, shock_mode="random",
        contagion_mode="simultaneous", merge_rule="random",
        deprecation_factor=0.0, c=0.0
    ):
        mr_vals = range(mr_min, mr_max + 1, int(mr_max / mr_points))
        self.attr.update(
            gen="chung_lu", n=n, z=z, mr_min=mr_min, mr_max=mr_max, mr_points=mr_points,
            gamma=gamma, mr_vals=list(mr_vals), runs=runs, alpha=alpha, kappa=kappa,
            shock_mode=shock_mode, contagion_mode=contagion_mode, merge_rule=merge_rule,
            deprecation_factor=deprecation_factor, c=c

        )
        self._network_gen = "cl"
        self._progbar_max = runs
        self._z_modifier = z
        self._setup_data_dict()
    
    def contagion_analysis(self, net: Network, mr):
        sm = self.attr["shock_mode"]
        if sm == "random":
            sb = net.shock_random()
        else:
            raise SystemError("Unknown shock mode!")
        net.cascade(
            sb,
            self.attr["contagion_mode"],
            deprecation_factor=self.attr["deprecation_factor"]
        )
        lb = net.get_largest()
        data_set = dict(
            df=net.defaulted_fraction(),
            af=net.defaulted_asset_fraction(),
            steps=net.simultaneous_cascade_steps,
            z=net.z(),
            lb_def=int(lb.defaulted)
        )
        self._append_to_mr_data(mr, data_set)
        net.reset_cascade()
    
    def _setup_network(self):
        if self._network_gen == "er":
            return fast_erdos_renyi(
                self.attr["n"], self._z_modifier,
                alpha=self.attr["alpha"], kappa=self.attr["kappa"], c=self.attr["c"]
            )
        if self._network_gen == "cl":
            return chung_lu(
                self.attr["n"], self._z_modifier, gamma=self.attr["gamma"],
                alpha=self.attr["alpha"], kappa=self.attr["kappa"], c=self.attr["c"]
            )
        else:
            raise SystemError("Network generator not yet set up.")
    
    def run(self):
        if self._network_gen is None:
            raise SystemError("Network generator not yet set up.")
        progbar = self.setup_progressbar(self._progbar_max)
        progbar.start()
        for i in range(self.attr["runs"]):
            # print(i)
            progbar.update(i + 1)
            mr_vals = list(self.attr["mr_vals"])
            net = self._setup_network()
            while mr_vals:
                progbar.update()
                next_mr = mr_vals.pop(0)
                # print(next_mr)
                while net.merge_round < next_mr:
                    net.random_merge(self.attr["merge_rule"])
                self.contagion_analysis(net, next_mr)
        progbar.finish()
