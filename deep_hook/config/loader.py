"""Configuration loading utilities.

Config can be loaded from a YAML file, a dict, or constructed inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import ValidationError

from deep_hook.core.exceptions import ConfigError
from deep_hook.core.models import DeepConfig

CONFIG_FILENAMES = ("deep.yml", ".deep.yml")


def config_from_yml(path: Union[str, Path] = "deep.yml") -> DeepConfig:
    """Load DeepConfig from a deep.yml (or .deep.yml) file.

    Use the returned config with run_review(changes, config).

    Parameters
    ----------
    path
        Path to the YAML file. Default is ``"deep.yml"`` (resolved from cwd).

    Returns
    -------
    DeepConfig
        Validated config ready to pass to run_review().
    """
    return load_config(path)


def load_config(source: Union[str, Path, dict, None] = None) -> DeepConfig:
    """Load and validate configuration.

    Parameters
    ----------
    source
        - ``None`` → search for ``deep.yml`` / ``.deep.yml`` in cwd.
        - ``str`` or ``Path`` → path to a YAML file.
        - ``dict`` → raw config data to validate directly.

    Returns a ``DeepConfig`` with defaults for any missing fields.
    """
    if isinstance(source, dict):
        return _validate(source)

    if isinstance(source, (str, Path)):
        return _load_yaml(Path(source))

    found = _find_config_file()
    if found:
        return _load_yaml(found)

    return DeepConfig()


def _find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    current = (start or Path.cwd()).resolve()
    for name in CONFIG_FILENAMES:
        candidate = current / name
        if candidate.is_file():
            return candidate
    return None


def _load_yaml(path: Path) -> DeepConfig:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if raw is None:
        return DeepConfig()

    return _validate(raw)


def _validate(data: dict) -> DeepConfig:
    try:
        return DeepConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc
