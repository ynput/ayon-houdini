from ayon_server.settings import BaseSettingsModel, SettingsField


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
