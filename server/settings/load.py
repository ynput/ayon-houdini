from ayon_server.settings import BaseSettingsModel, SettingsField



def camera_aperture_expression_enum_options():
    return [
        {"label": "Houdini Default", "value": "default"},
        {"label": "Match Maya render mask", "value": "match_maya"}
    ]


class CameraLoaderModel(BaseSettingsModel):
    camera_aperture_expression: str = SettingsField(
        "default",
        title="Camera Aperture Expression on load",
        enum_resolver=camera_aperture_expression_enum_options,
        description=(
            "Allows to override the Houdini default expression on loaded "
            "Alembic cameras by one that should better match the Maya Render "
            "Mask. The alternative Match Maya Render mask expression is based "
            "on Houdini's own expression it applies on FBX import of cameras."
        )
    )


# Load Plugins
class LoadUseAYONEntityURIModel(BaseSettingsModel):
    use_ayon_entity_uri: bool = SettingsField(
        False,
        title="Use AYON Entity URI",
        description=(
            "Use the AYON Entity URI on load instead of the resolved filepath "
            "so that the AYON USD Resolver will resovle the paths at runtime. "
            "This should be enabled when using the AYON USD Resolver."
        )
    )


class LoadPluginsModel(BaseSettingsModel):
    CameraLoader: CameraLoaderModel = SettingsField(
        default_factory=CameraLoaderModel,
        title="Load Camera (abc)")
    LOPLoadAssetLoader: LoadUseAYONEntityURIModel = SettingsField(
        default_factory=LoadUseAYONEntityURIModel,
        title="LOP Load Asset")
    LOPLoadShotLoader: LoadUseAYONEntityURIModel = SettingsField(
        default_factory=LoadUseAYONEntityURIModel,
        title="LOP Load Shot")
    USDSublayerLoader: LoadUseAYONEntityURIModel = SettingsField(
        default_factory=LoadUseAYONEntityURIModel,
        title="USD Sublayer Loader")
    USDReferenceLoader: LoadUseAYONEntityURIModel = SettingsField(
        default_factory=LoadUseAYONEntityURIModel,
        title="USD Reference Loader")
    SopUsdImportLoader: LoadUseAYONEntityURIModel = SettingsField(
        default_factory=LoadUseAYONEntityURIModel,
        title="USD SOP Import Loader")
