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


class GeneralSettingsModel(BaseSettingsModel):
    add_self_publish_button: bool = SettingsField(
        False,
        title="Add Self Publish Button"
    )
    default_output_dir: str = SettingsField(
        title="Default Output Directory",
        description="This is the initial output directory for newly created "
                    "AYON ROPs. It serves as a starting point when a new ROP "
                    "is generated using the AYON creator. Artists can modify "
                    "this directory after the ROP is created. "
                    "Note: AYON creator will expand any Houdini vars."
    )
    update_houdini_var_context: UpdateHoudiniVarcontextModel = SettingsField(
        default_factory=UpdateHoudiniVarcontextModel,
        title="Update Houdini Vars on context change"
    )


DEFAULT_GENERAL_SETTINGS = {
    "add_self_publish_button": False,
    "default_output_dir": "$HIP/ayon",
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
