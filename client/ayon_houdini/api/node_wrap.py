import dataclasses
from typing import Dict, List, Optional
import hou

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext


@dataclasses.dataclass
class NodeTypeProductTypes:
    """Product type settings for a node type.

    Define the available product types the user can set on a ROP based on
    node type.

    When 'strict' an enum attribute is created and the user can not type a
    custom product type, otherwise a string attribute is
    created with a menu right hand side to help pick a type but allow custom
    types.
    """
    product_types: List[str]
    default: Optional[str] = None
    strict: bool = True


# Re-usable defaults
GEO_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["pointcache", "model"],
    default="pointcache"
)
FBX_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["fbx", "pointcache", "model"],
    default="fbx"
)
FBX_ONLY_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["fbx"],
    default="fbx"
)
USD_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["usd", "pointcache"],
    default="usd"
)
COMP_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["imagesequence", "render"],
    default="imagesequence"
)
REVIEW_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["review"],
    default="review"
)
RENDER_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["render", "prerender"],
    default="render"
)
GLTF_PRODUCT_TYPES = NodeTypeProductTypes(
    product_types=["gltf"],
    default="gltf"
)

# TODO: Move this to project settings
NODE_TYPE_PRODUCT_TYPES: Dict[str, NodeTypeProductTypes] = {
    "alembic": GEO_PRODUCT_TYPES,
    "rop_alembic": GEO_PRODUCT_TYPES,
    "geometry": GEO_PRODUCT_TYPES,
    "rop_geometry": GEO_PRODUCT_TYPES,
    "filmboxfbx": FBX_PRODUCT_TYPES,
    "rop_fbx": FBX_PRODUCT_TYPES,
    "usd": USD_PRODUCT_TYPES,
    "usd_rop": USD_PRODUCT_TYPES,
    "usdexport": USD_PRODUCT_TYPES,
    "comp": COMP_PRODUCT_TYPES,
    "opengl": REVIEW_PRODUCT_TYPES,
    "arnold": RENDER_PRODUCT_TYPES,
    "karma": RENDER_PRODUCT_TYPES,
    "ifd": RENDER_PRODUCT_TYPES,
    "usdrender": RENDER_PRODUCT_TYPES,
    "usdrender_rop": RENDER_PRODUCT_TYPES,
    "vray_renderer": RENDER_PRODUCT_TYPES,
    "labs::karma::2.0": RENDER_PRODUCT_TYPES,
    "kinefx::rop_fbxanimoutput": FBX_ONLY_PRODUCT_TYPES,
    "kinefx::rop_fbxcharacteroutput": FBX_ONLY_PRODUCT_TYPES,
    "kinefx::rop_gltfcharacteroutput": GLTF_PRODUCT_TYPES,
    "rop_gltf": GLTF_PRODUCT_TYPES
}

NODE_TYPE_PRODUCT_TYPES_DEFAULT = NodeTypeProductTypes(
    product_types=list(sorted(
        {
            "ass", "pointcache", "model", "render", "camera",
            "imagesequence", "review", "vdbcache", "fbx"
        })),
    default="pointcache",
    strict=False
)
AUTO_CREATE_NODE_TYPES = set(NODE_TYPE_PRODUCT_TYPES.keys())


def make_publishable(node):
    # TODO: Can we make this imprinting much faster? Unfortunately
    #  CreateContext initialization is very slow.
    host = registered_host()
    context = CreateContext(host)

    # Apply the instance creation to the node
    context.create(
        creator_identifier="io.ayon.creators.houdini.publish",
        variant="__use_node_name__",
        pre_create_data={
            "node": node
        }
    )


def autocreate_publishable(node):
    # For now only consider RopNode
    if not isinstance(node, hou.RopNode):
        return

    node_type = node.type().name()
    if node_type in AUTO_CREATE_NODE_TYPES:
        make_publishable(node)
