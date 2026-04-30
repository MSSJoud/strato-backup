from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RuntimePaths:
    raw_data_root: Path
    derived_data_root: Path
    output_root: Path


@dataclass
class StudyArea:
    name: str
    region: str
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float


@dataclass
class ProjectConfig:
    project_name: str
    description: str
    study_area: StudyArea
    runtime_paths: RuntimePaths


def _require(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise KeyError(f"Missing required config key: {key}")
    return mapping[key]


def load_config(path: str | Path) -> ProjectConfig:
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f)

    study_area_raw = _require(raw, "study_area")
    paths_raw = _require(raw, "runtime_paths")

    study_area = StudyArea(
        name=_require(study_area_raw, "name"),
        region=_require(study_area_raw, "region"),
        lon_min=float(_require(study_area_raw, "lon_min")),
        lon_max=float(_require(study_area_raw, "lon_max")),
        lat_min=float(_require(study_area_raw, "lat_min")),
        lat_max=float(_require(study_area_raw, "lat_max")),
    )
    runtime_paths = RuntimePaths(
        raw_data_root=Path(_require(paths_raw, "raw_data_root")),
        derived_data_root=Path(_require(paths_raw, "derived_data_root")),
        output_root=Path(_require(paths_raw, "output_root")),
    )
    return ProjectConfig(
        project_name=_require(raw, "project_name"),
        description=_require(raw, "description"),
        study_area=study_area,
        runtime_paths=runtime_paths,
    )

