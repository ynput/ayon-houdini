from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField
)


# Publish Plugins
class CollectAssetHandlesModel(BaseSettingsModel):
    """Collect Frame Range
    Disable this if you want the publisher to ignore start and end handles
    specified in the task or folder data for publish instances.
    """
    use_asset_handles: bool = SettingsField(
        title="Use asset handles")


class AOVFilterSubmodel(BaseSettingsModel):
    """You should use the same host name you are using for Houdini."""
    host_name: str = SettingsField("", title="Houdini Host name")
    value: list[str] = SettingsField(
        default_factory=list,
        title="AOV regex"
    )


class CollectLocalRenderInstancesModel(BaseSettingsModel):

    use_deadline_aov_filter: bool = SettingsField(
        False,
        title="Use Deadline AOV Filter"
    )

    aov_filter: AOVFilterSubmodel = SettingsField(
        default_factory=AOVFilterSubmodel,
        title="Reviewable products filter"
    )


def product_types_enum():
    return [
        {"value": "camera", "label": "Camera (Abc)"},
        {"value": "pointcache", "label": "PointCache (Abc)/PointCache (Bgeo)"},
        {"value": "review", "label": "Review"},
        {"value": "staticMesh", "label": "Static Mesh (FBX)"},
        {"value": "usd", "label": "USD (experimental)"},
        {"value": "vdbcache", "label": "VDB Cache"},
        {"value": "imagesequence", "label": "Composite (Image Sequence)"},
        {"value": "ass", "label": "Arnold ASS"},
        {"value": "arnold_rop", "label": "Arnold ROP"},
        {"value": "mantra_rop", "label": "Mantra ROP"},
        {"value": "redshiftproxy", "label": "Redshift Proxy"},
        {"value": "redshift_rop", "label": "Redshift ROP"},
        {"value": "karma_rop", "label": "Karma ROP"},
        {"value": "vray_rop", "label": "VRay ROP"},
        {"value": "model", "label": "Model"},
    ]


class CollectFilesForCleaningUpModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")

    families: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=product_types_enum,
        conditional_enum=True,
        title="Product Types"
    )


class CollectFramesFixDefHouModel(BaseSettingsModel):
    enabled: bool = SettingsField(True)
    rewrite_version_enable: bool = SettingsField(
        False,
        title="Show 'Rewrite latest version' toggle",
        description=(
            "When enabled the artist can enable 'rewrite latest version' in "
            "the publisher. When doing so the new frames to fix publish will "
            "update the frames in last version instead of creating a new "
            "version."
        )
    )
    families: list[str] = SettingsField(
        default_factory=list,
        title="Families"
    )


class ValidateWorkfilePathsModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    node_types: list[str] = SettingsField(
        default_factory=list,
        title="Node Types"
    )
    prohibited_vars: list[str] = SettingsField(
        default_factory=list,
        title="Prohibited Variables"
    )


class BasicEnabledStatesModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")


class ValidateUsdLookDisallowedTypesModel(BasicEnabledStatesModel):
    disallowed_types: list[str] = SettingsField(
        default_factory=list,
        title="Disallowed Types",
        description=(
            "Disallowed types for look product. "
            "This should be USD schema types like:\n"
            "- `UsdGeomBoundable` for Meshes/Lights/Procedurals\n"
            "- `UsdRenderSettingsBase` for Render Settings\n"
            "- `UsdRenderVar` for Render Var\n"
            "- `UsdGeomCamera` for Cameras"
        )
    )


class ExtractUsdModel(BaseSettingsModel):
    use_ayon_entity_uri: bool = SettingsField(
        False,
        title="Remap save layers to AYON Entity URI",
        description=(
            "Remap explicit save layers to AYON Entity URI on publish "
            "instead of the resolved publish filepaths."
        )
    )


class PublishPluginsModel(BaseSettingsModel):
    CollectAssetHandles: CollectAssetHandlesModel = SettingsField(
        default_factory=CollectAssetHandlesModel,
        title="Collect Asset Handles",
        section="Collectors"
    )
    CollectFilesForCleaningUp: CollectFilesForCleaningUpModel = SettingsField(
        default_factory=CollectFilesForCleaningUpModel,
        title="Collect Files For Cleaning Up."
    )
    CollectFramesFixDefHou: CollectFramesFixDefHouModel = SettingsField(
        default_factory=CollectFramesFixDefHouModel,
        title="Collect Frames to Fix",
    )
    CollectLocalRenderInstances: CollectLocalRenderInstancesModel = SettingsField(  # noqa: E501
        default_factory=CollectLocalRenderInstancesModel,
        title="Collect Local Render Instances"
    )
    ValidateInstanceInContextHoudini: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate Instance is in same Context",
        section="Validators")
    ValidateMeshIsStatic: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate Mesh is Static")
    ValidateReviewColorspace: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate Review Colorspace")
    ValidateProductName: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate Product Name")
    ValidateUnrealStaticMeshName: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate Unreal Static Mesh Name")
    ValidateWorkfilePaths: ValidateWorkfilePathsModel = SettingsField(
        default_factory=ValidateWorkfilePathsModel,
        title="Validate workfile paths settings")
    ValidateUsdLookAssignments: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate USD Look Assignments")
    ValidateUsdLookDisallowedTypes: ValidateUsdLookDisallowedTypesModel = (
        SettingsField(
            default_factory=ValidateUsdLookDisallowedTypesModel,
            title="Validate USD Look Disallowed Types"
        )
    )
    ValidateUSDRenderProductPaths: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate USD Render Product Paths")
    ValidateRenderResolution: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Validate USD Render Resolution",
        description=(
            "Validate render resolution and pixel aspect of USD render"
            " products match the context resolution.")
    )
    ExtractActiveViewThumbnail: BasicEnabledStatesModel = SettingsField(
        default_factory=BasicEnabledStatesModel,
        title="Extract Active View Thumbnail",
        section="Extractors"
    )
    ExtractUSD: ExtractUsdModel = SettingsField(
        default_factory=ExtractUsdModel,
        title="Extract USD"
    )


DEFAULT_HOUDINI_PUBLISH_SETTINGS = {
    "CollectAssetHandles": {
        "use_asset_handles": True
    },
    "CollectFilesForCleaningUp": {
        "enabled": False,
        "optional": True,
        "active": True,
        "families": []
    },
    "CollectFramesFixDefHou": {
        "enabled": True,
        "rewrite_version_enable": False,
        "families": [
            "*"
        ]
    },
    "CollectLocalRenderInstances": {
        "use_deadline_aov_filter": False,
        "aov_filter": {
            "host_name": "houdini",
            "value": [
                ".*([Bb]eauty).*"
            ]
        }
    },
    "ValidateInstanceInContextHoudini": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateMeshIsStatic": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateReviewColorspace": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateProductName": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateUnrealStaticMeshName": {
        "enabled": False,
        "optional": True,
        "active": True
    },
    "ValidateWorkfilePaths": {
        "enabled": True,
        "optional": True,
        "node_types": [
            "file",
            "alembic"
        ],
        "prohibited_vars": [
            "$HIP",
            "$JOB"
        ]
    },
    "ValidateUsdLookAssignments": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateUsdLookDisallowedTypes": {
        "enabled": True,
        "optional": False,
        "active": True,
        "disallowed_types": [
            "UsdGeomBoundable",
            "UsdRenderSettingsBase",
            "UsdRenderVar",
            "UsdGeomCamera"
        ]
    },
    "ValidateUSDRenderProductPaths": {
        "enabled": False,
        "optional": True,
        "active": True
    },
    "ValidateRenderResolution": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ExtractActiveViewThumbnail": {
        "enabled": True,
        "optional": False,
        "active": True
    },
    "ExtractUSD": {
        "use_ayon_entity_uri": False
    }
}
