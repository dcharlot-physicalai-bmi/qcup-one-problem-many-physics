"""Python side of the published-noise Selene error-model plugin (rust/lib.rs): its arguments and its shared library."""
from dataclasses import dataclass, field
from pathlib import Path

from selene_core import ErrorModel


@dataclass
class PublishedNoise(ErrorModel):
    library: str = ""
    p1: float = 0.0
    p1_emission_ratio: float = 0.0
    p2: float = 0.0
    p2_emission_ratio: float = 0.0
    p_meas_0: float = 0.0
    p_meas_1: float = 0.0
    p_init: float = 0.0
    p_crosstalk_meas: float = 0.0
    p_crosstalk_init: float = 0.0
    memory_pz: float = 0.0
    unit_ns: int = 1

    def __post_init__(self):
        for k in ("p1", "p1_emission_ratio", "p2", "p2_emission_ratio", "p_meas_0", "p_meas_1", "p_init", "p_crosstalk_meas", "p_crosstalk_init", "memory_pz"):
            v = getattr(self, k)
            assert 0.0 <= v <= 1.0, f"{k} = {v} is not a probability"
        assert self.unit_ns >= 1
        assert Path(self.library).is_file(), f"no plugin library at {self.library}"

    @property
    def library_file(self):
        return Path(self.library)

    def get_init_args(self):
        return [f"--p1={self.p1!r}", f"--p1-emission-ratio={self.p1_emission_ratio!r}", f"--p2={self.p2!r}", f"--p2-emission-ratio={self.p2_emission_ratio!r}",
                f"--p-meas-0={self.p_meas_0!r}", f"--p-meas-1={self.p_meas_1!r}", f"--p-init={self.p_init!r}", f"--p-crosstalk-meas={self.p_crosstalk_meas!r}",
                f"--p-crosstalk-init={self.p_crosstalk_init!r}", f"--memory-pz={self.memory_pz!r}", f"--unit-ns={self.unit_ns}"]
