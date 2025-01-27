from ayon_server.settings import BaseSettingsModel, SettingsField


class HoudiniVarModel(BaseSettingsModel):
    _layout = "expanded"
    var: str = SettingsField("", title="Var")
    value: str = SettingsField("", title="Value")
    is_directory: bool = SettingsField(False, title="Treat as directory")


class UpdateHoudiniVarcontextModel(BaseSettingsModel):
    """Sync vars with context changes.

    If a value is treated as a directory on update
    it will be ensured the folder exists.
    """

    enabled: bool = SettingsField(title="Enabled")
    # TODO this was dynamic dictionary '{var: path}'
    houdini_vars: list[HoudiniVarModel] = SettingsField(
        default_factory=list,
        title="Houdini Vars"
    )


class ROPOutputDirModel(BaseSettingsModel):
    """Set ROP Output Directory on Create

    When enabled, this setting defines output paths for ROP nodes,
    which can be overridden by custom staging directories.
    Disable it to completely turn off setting default values and 
    custom staging directories defined in **ayon+settings://core/tools/publish/custom_staging_dir_profiles**.
    """

    enabled: bool = SettingsField(title="Enabled")

    expand_vars: bool = SettingsField(
        title="Expand Houdini Variables",
        description="When enabled, Houdini variables (e.g., `$HIP`) "
                    "will be expanded, but Houdini expressions "
                    "(e.g., \`chs('AYON_productName')\`) will remain "
                    "unexpanded in the `Default Output Directory`."
    )

    default_output_dir: str = SettingsField(
        title="Default Output Directory",
        description="This is the initial output directory for newly created "
                    "AYON ROPs. It serves as a starting point when a new ROP "
                    "is generated using the AYON creator. Artists can modify "
                    "this directory after the ROP is created. It Supports Houdini "
                    "vars (e.g., `$HIP`) and expressions (e.g., \`chs('AYON_productName')\`)"
                    " Note: Houdini Expressions will be expanded for HDA products."
    )


class GeneralSettingsModel(BaseSettingsModel):
    add_self_publish_button: bool = SettingsField(
        False,
        title="Add Self Publish Button"
    )
    set_rop_output: ROPOutputDirModel = SettingsField(
        default_factory=ROPOutputDirModel,
        title="Set ROP Output Directory on Create"
    )
    update_houdini_var_context: UpdateHoudiniVarcontextModel = SettingsField(
        default_factory=UpdateHoudiniVarcontextModel,
        title="Update Houdini Vars on context change"
    )


DEFAULT_GENERAL_SETTINGS = {
    "add_self_publish_button": False,
    "set_rop_output": {
        "enabled": True,
        "expand_vars": False,
        "default_output_dir": "$HIP/ayon/`chs('AYON_productName')`"
    },
    "update_houdini_var_context": {
        "enabled": True,
        "houdini_vars": [
            {
                "var": "JOB",
                "value": "{root[work]}/{project[name]}/{hierarchy}/{folder[name]}/work/{task[name]}",  # noqa
                "is_directory": True
            }
        ]
    }
}
