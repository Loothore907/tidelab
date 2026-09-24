"""Engine-independent identity for a single research trial.

This is a small export contract, not the TL-003 experiment registry. It records
identifiers and hashes only; raw data, results, credentials, and local paths do
not belong in this document.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Mapping

from tidelab.domain import canonical_json


IDENTITY_SCHEMA_VERSION = 1
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "engine": ("name", "version", "source_revision"),
    "code": ("repository", "revision"),
    "configuration": ("id", "sha256"),
    "data": ("source_id", "revision", "sha256", "kind", "rights_reference"),
    "cost": ("model_id", "revision", "sha256"),
    "trial": ("strategy_id", "strategy_version", "trial_id", "sequence", "origin", "parent_trial_id"),
}


def _section(name: str, source: Mapping[str, str | int | None]) -> dict[str, str | int | None]:
    expected = set(_FIELDS[name])
    if set(source) != expected:
        raise ValueError(f"{name} must have exactly {', '.join(_FIELDS[name])}")
    result = dict(source)
    for key, value in result.items():
        if name == "trial" and key == "sequence":
            if type(value) is not int or value < 1:
                raise ValueError("trial.sequence must be a positive integer")
        elif name == "trial" and key == "parent_trial_id" and value is None:
            continue
        elif not isinstance(value, str) or not _TOKEN.fullmatch(value):
            raise ValueError(f"{name}.{key} must be a nonempty portable identifier")
        if key == "sha256" and not _DIGEST.fullmatch(value):
            raise ValueError(f"{name}.{key} must be a lowercase SHA-256 digest")
    if name == "data" and result["kind"] not in ("synthetic", "third_party"):
        raise ValueError("data.kind must be synthetic or third_party")
    if name == "trial" and result["origin"] not in ("human", "model", "published"):
        raise ValueError("trial.origin must be human, model, or published")
    return result


def build_experiment_identity(
    *,
    engine: Mapping[str, str],
    code: Mapping[str, str],
    configuration: Mapping[str, str],
    data: Mapping[str, str],
    cost: Mapping[str, str],
    trial: Mapping[str, str | int | None],
) -> dict[str, object]:
    """Return a deterministic identity; changing any declared input changes it.

    The supplied hashes identify *bytes*; callers must compute them from the
    actual fixture/configuration/cost policy and retain those inputs lawfully.
    This function cannot establish data or artifact publication rights.
    """
    body: dict[str, object] = {"schema_version": IDENTITY_SCHEMA_VERSION}
    for name, source in (
        ("engine", engine),
        ("code", code),
        ("configuration", configuration),
        ("data", data),
        ("cost", cost),
        ("trial", trial),
    ):
        body[name] = _section(name, source)
    body["identity_sha256"] = sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return body


def export_experiment_identity(
    identity: Mapping[str, object], path: Path, *, public_synthetic: bool = False
) -> None:
    """Create one manifest without overwriting another trial's evidence.

    Public export is limited to TideLab-authored synthetic inputs. Real-data
    public release requires the separate TL-001B review, not this switch.
    """
    if set(identity) != {*_FIELDS, "schema_version", "identity_sha256"}:
        raise ValueError("experiment identity has missing or unexpected fields")
    if identity["schema_version"] != IDENTITY_SCHEMA_VERSION:
        raise ValueError("unsupported experiment identity schema")
    expected = build_experiment_identity(**{name: identity[name] for name in _FIELDS})
    if identity != expected:
        raise ValueError("experiment identity digest does not match its contents")
    data = identity["data"]
    if public_synthetic and (
        not isinstance(data, dict)
        or data.get("kind") != "synthetic"
        or data.get("rights_reference") != "TideLab-authored"
    ):
        raise ValueError("public export requires TideLab-authored synthetic data")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(canonical_json(identity) + "\n")
