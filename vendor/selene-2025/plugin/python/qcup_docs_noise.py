"""Python side of the docs-noise Selene error-model plugin (rust/lib.rs): its arguments and its shared library."""
from dataclasses import dataclass
from pathlib import Path

from selene_core import ErrorModel

PROBS = ("p1", "p1_emission_ratio", "p2", "p2_emission_ratio", "p_meas_0", "p_meas_1", "p_init", "p_crosstalk_meas", "p_crosstalk_init",
         "p_prep_leak_ratio", "p1_seepage_prob", "p2_seepage_prob", "memory_pz")
FIT = ("przz_a", "przz_b", "przz_c", "przz_d", "przz_power")
FLAGS = ("leakage_model", "leak2depolar")


@dataclass
class DocsNoise(ErrorModel):
    library: str = ""
    p1: float = 0.0
    p1_emission_ratio: float = 0.0
    p2: float = 0.0
    p2_emission_ratio: float = 0.0
    przz_a: float = 0.0
    przz_b: float = 1.0
    przz_c: float = 0.0
    przz_d: float = 1.0
    przz_power: float = 1.0
    p_meas_0: float = 0.0
    p_meas_1: float = 0.0
    p_init: float = 0.0
    p_crosstalk_meas: float = 0.0
    p_crosstalk_init: float = 0.0
    leakage_model: bool = False
    leak2depolar: bool = False
    p_prep_leak_ratio: float = 0.0
    p1_seepage_prob: float = 0.0
    p2_seepage_prob: float = 0.0
    memory_pz: float = 0.0
    unit_ns: int = 1

    def __post_init__(self):
        for k in PROBS:
            v = getattr(self, k)
            assert 0.0 <= v <= 1.0, f"{k} = {v} is not a probability"
        for k in FIT:
            assert getattr(self, k) >= 0.0, f"{k} is negative"
        assert self.unit_ns >= 1
        assert Path(self.library).is_file(), f"no plugin library at {self.library}"

    @property
    def library_file(self):
        return Path(self.library)

    def get_init_args(self):
        a = [f"--{k.replace('_', '-')}={getattr(self, k)!r}" for k in PROBS + FIT]
        a += [f"--{k.replace('_', '-')}={'true' if getattr(self, k) else 'false'}" for k in FLAGS]
        return a + [f"--unit-ns={self.unit_ns}"]
