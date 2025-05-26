import semver
from typing import Any


def parse_version(version):
    try:
        return semver.VersionInfo.parse(version)
    except ValueError:
        return None


def _convert_validate_subset_name(overrides: dict[str, Any]) -> None:
    # Convert old "ValidateSubsetName" to new "ValidateProductName"
    if "publish" not in overrides:
        return

    publish_overrides = overrides["publish"]
    if (
            "ValidateSubsetName" in publish_overrides
            and "ValidateProductName" not in publish_overrides
    ):
        publish_overrides["ValidateProductName"] = publish_overrides.pop(
            "ValidateSubsetName"
        )

def _enable_create_render_rops_use_render_product_type(
        overrides: dict[str, Any]
) -> None:
    # Enforce render creators `render_rops_use_render_product_type` to True
    # to remain backwards compatible with older versions
    create = overrides.setdefault("create", {})
    create["render_rops_use_legacy_product_type"] = True


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    _convert_validate_subset_name(overrides)

    if parse_version(source_version) < (0, 5, 1):
        _enable_create_render_rops_use_render_product_type(overrides)

    return overrides
