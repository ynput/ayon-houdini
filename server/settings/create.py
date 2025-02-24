from ayon_server.settings import BaseSettingsModel, SettingsField


# Creator Plugins
class CreatorModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    default_variants: list[str] = SettingsField(
        title="Default Products",
        default_factory=list,
    )

def review_node_types_enum():
    return [
        {"label": "OpenGL", "value": "opengl"},
        {"label": "Flipbook", "value": "flipbook"}
    ]

class CreateReviewModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    default_variants: list[str] = SettingsField(
        title="Default Products",
        default_factory=list,
    )
    node_type: str = SettingsField(
        title="Default Node Type",
        enum_resolver=review_node_types_enum,
    )

class CreateArnoldAssModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    default_variants: list[str] = SettingsField(
        title="Default Products",
        default_factory=list,
    )
    ext: str = SettingsField(Title="Extension")


class CreateStaticMeshModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    default_variants: list[str] = SettingsField(
        default_factory=list,
        title="Default Products"
    )
    static_mesh_prefix: str = SettingsField("S", title="Static Mesh Prefix")
    collision_prefixes: list[str] = SettingsField(
        default_factory=list,
        title="Collision Prefixes"
    )


class CreateUSDRenderModel(CreatorModel):
    default_renderer: str = SettingsField(
        "Karma CPU",
        title="Default Renderer",
        description=(
            "Specify either the Hydra renderer plug-in nice name, like "
            "'Karma CPU', or the plug-in name, e.g. 'BRAY_HdKarma'"
        ))


class CreatePluginsModel(BaseSettingsModel):
    CreateAlembicCamera: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Alembic Camera")
    CreateArnoldAss: CreateArnoldAssModel = SettingsField(
        default_factory=CreateArnoldAssModel,
        title="Create Arnold Ass")
    CreateArnoldRop: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Arnold ROP")
    CreateCompositeSequence: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Composite (Image Sequence)")
    CreateHDA: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Houdini Digital Asset")
    CreateKarmaROP: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Karma ROP")
    CreateUSDLook: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Look")
    CreateMantraROP: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Mantra ROP")
    CreateModel: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Model")
    CreatePointCache: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create PointCache (Abc)")
    CreateBGEO: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create PointCache (Bgeo)")
    CreateRedshiftProxy: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Redshift Proxy")
    CreateRedshiftROP: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Redshift ROP")
    CreateReview: CreateReviewModel = SettingsField(
        default_factory=CreateReviewModel,
        title="Create Review")
    # "-" is not compatible in the new model
    CreateStaticMesh: CreateStaticMeshModel = SettingsField(
        default_factory=CreateStaticMeshModel,
        title="Create Static Mesh")
    CreateUSD: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create USD")
    CreateUSDRender: CreateUSDRenderModel = SettingsField(
        default_factory=CreateUSDRenderModel,
        title="Create USD render")
    CreateVDBCache: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create VDB Cache")
    CreateVrayROP: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create VRay ROP")


DEFAULT_HOUDINI_CREATE_SETTINGS = {
    "CreateAlembicCamera": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateArnoldAss": {
        "enabled": True,
        "default_variants": ["Main"],
        "ext": ".ass"
    },
    "CreateArnoldRop": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateCompositeSequence": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateHDA": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateKarmaROP": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateUSDLook": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateMantraROP": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateModel": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreatePointCache": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateBGEO": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateRedshiftProxy": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateRedshiftROP": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateReview": {
        "enabled": True,
        "default_variants": ["Main"],
        "node_type": "opengl"
    },
    "CreateStaticMesh": {
        "enabled": True,
        "default_variants": [
            "Main"
        ],
        "static_mesh_prefix": "S",
        "collision_prefixes": [
            "UBX",
            "UCP",
            "USP",
            "UCX"
        ]
    },
    "CreateUSD": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateUSDRender": {
        "enabled": True,
        "default_variants": ["Main"],
        "default_renderer": "Karma CPU"
    },
    "CreateVDBCache": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateVrayROP": {
        "enabled": True,
        "default_variants": ["Main"]
    },
}
