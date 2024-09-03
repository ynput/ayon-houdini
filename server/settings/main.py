from ayon_server.settings import BaseSettingsModel, SettingsField
from .general import (
    GeneralSettingsModel,
    DEFAULT_GENERAL_SETTINGS
)
from .imageio import (
    HoudiniImageIOModel,
    DEFAULT_IMAGEIO_SETTINGS
)
from .shelves import ShelvesModel
from .create import (
    CreatePluginsModel,
    DEFAULT_HOUDINI_CREATE_SETTINGS
)
from .publish import (
    PublishPluginsModel,
    DEFAULT_HOUDINI_PUBLISH_SETTINGS,
)
from .load import (
    LoadPluginsModel,
)
from .templated_workfile_build import (
    TemplatedWorkfileBuildModel
)


class HoudiniSettings(BaseSettingsModel):
    general: GeneralSettingsModel = SettingsField(
        default_factory=GeneralSettingsModel,
        title="General"
    )
    imageio: HoudiniImageIOModel = SettingsField(
        default_factory=HoudiniImageIOModel,
        title="Color Management (ImageIO)"
    )
    shelves: list[ShelvesModel] = SettingsField(
        default_factory=list,
        title="Shelves Manager",
    )
    create: CreatePluginsModel = SettingsField(
        default_factory=CreatePluginsModel,
        title="Creator Plugins",
    )
    publish: PublishPluginsModel = SettingsField(
        default_factory=PublishPluginsModel,
        title="Publish Plugins",
    )
    load: LoadPluginsModel = SettingsField(
        default_factory=LoadPluginsModel,
        title="Loader Plugins",
    )
    templated_workfile_build: TemplatedWorkfileBuildModel = SettingsField(
        title="Templated Workfile Build",
        default_factory=TemplatedWorkfileBuildModel
    )


DEFAULT_VALUES = {
    "general": DEFAULT_GENERAL_SETTINGS,
    "imageio": DEFAULT_IMAGEIO_SETTINGS,
    "shelves": [],
    "create": DEFAULT_HOUDINI_CREATE_SETTINGS,
    "publish": DEFAULT_HOUDINI_PUBLISH_SETTINGS,
    "templated_workfile_build": {
        "profiles": []
    }
}
