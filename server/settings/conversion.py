from typing import Any


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


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    _convert_validate_subset_name(overrides)
    return overrides
