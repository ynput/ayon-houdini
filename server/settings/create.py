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
    ext: str = SettingsField(title="Extension")
    show_in_viewport_menu: bool = SettingsField(
        title="Show in Viewport Menu",
        default=False,
        description=(
            "When disabled the Arnold ROP will not be listed in the render"
            " view as a renderable candidate. Since this product is used for "
            " `.ass` exports most of the time it's often not needed as a"
            " renderable option."
        )
    )

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


def redshift_multi_layered_mode_enum():
    return [
        {"label": "No Multi-Layered EXR File", "value": "1"},
        {"label": "Full Multi-Layered EXR File", "value": "2"}
    ]


class CreateRedshiftROPModel(CreatorModel):
    multi_layered_mode: str = SettingsField(
        "1",
        title="Multi Layered Mode",
        description=(
            "Default Multi Layered Mode when creating a new Redshift ROP"
        ),
        enum_resolver=redshift_multi_layered_mode_enum,
    )


class CreateUSDRenderModel(CreatorModel):
    default_renderer: str = SettingsField(
        "Karma CPU",
        title="Default Renderer",
        description=(
            "Specify either the Hydra renderer plug-in nice name, like "
            "'Karma CPU', or the plug-in name, e.g. 'BRAY_HdKarma'"
        ))


class WorkfileModel(BaseSettingsModel):
    is_mandatory: bool = SettingsField(
        default=False,
        title="Mandatory workfile",
        description=(
            "Workfile cannot be disabled by user in UI."
            " Requires core addon 1.4.1 or newer."
        )
    )


class ROPOutputDirModel(BaseSettingsModel):
    """Set ROP Output Directory on Create

    When enabled, this setting defines output paths for ROP nodes,
    which can be overridden by custom staging directories.
    Disable it to completely turn off setting default values and
    custom staging directories defined in
    **ayon+settings://core/tools/publish/custom_staging_dir_profiles**.
    """

    enabled: bool = SettingsField(title="Enabled")

    expand_vars: bool = SettingsField(
        title="Expand Houdini Variables",
        description="When enabled, Houdini variables (e.g., `$HIP`) "
                    "will be expanded, but Houdini expressions "
                    r"(e.g., \`chs('AYON_productName')\`) will remain "
                    "unexpanded in the `Default Output Directory`."
    )

    default_output_dir: str = SettingsField(
        title="Default Output Directory",
        description="This is the initial output directory for newly created "
                    "AYON ROPs. It serves as a starting point when a new ROP "
                    "is generated using the AYON creator. Artists can modify "
                    "this directory after the ROP is created.\n\n"
                    "It supports Houdini vars (e.g., `$HIP`) and expressions "
                    "(e.g., `chs('AYON_productName')`)\n"
                    "Note: Houdini Expressions are expanded for HDA products."
    )


class CreatePluginsModel(BaseSettingsModel):
    render_rops_use_legacy_product_type: bool = SettingsField(
        False,
        title="Render ROPs use legacy product types",
        description=(
            "When enabled, it will use legacy product types like "
            "`arnold_rop`, `mantra_rop`, `usdrender` and so forth. "
            "When disabled, render ROPs will render to `render` product type. "
            "This setting is mostly for backward compatibility for existing "
            "projects and affects the Arnold, Karma, Mantra, Redshift, V-Ray "
            "and USD Render ROPs."
        ),
    )
    set_rop_output: ROPOutputDirModel = SettingsField(
        default_factory=ROPOutputDirModel,
        title="Set ROP Output Directory on Create"
    )

    CreateAlembicCamera: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Alembic Camera",
        section="Creators")
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
    CreateModelFBX: CreatorModel= SettingsField(
        default_factory=CreatorModel,
        title="Create Model FBX")
    CreatePointCache: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create PointCache (Abc)")
    CreateBGEO: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create PointCache (Bgeo)")
    CreatePRTPointCloud: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create PointCloud (PRT)")
    CreateRedshiftProxy: CreatorModel = SettingsField(
        default_factory=CreatorModel,
        title="Create Redshift Proxy")
    CreateRedshiftROP: CreateRedshiftROPModel = SettingsField(
        default_factory=CreateRedshiftROPModel,
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
    CreateWorkfile: WorkfileModel = SettingsField(
        default_factory=WorkfileModel,
        title="Create Workfile")


DEFAULT_HOUDINI_CREATE_SETTINGS = {
    "render_rops_use_legacy_product_type": False,
    "set_rop_output": {
        "enabled": True,
        "expand_vars": False,
        "default_output_dir": "$HIP/ayon/`chs(\"AYON_productName\")`"
    },
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
    "CreateModelFBX": {
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
    "CreatePRTPointCloud": {
        "enabled": False,
        "default_variants": ["Main"]
    },
    "CreateRedshiftProxy": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateRedshiftROP": {
        "enabled": True,
        "default_variants": ["Main"],
        "multi_layered_mode": "1"
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
