import pyblish.api
from ayon_houdini.api import plugin


class CollectFarmInstances(plugin.HoudiniInstancePlugin):
    """Collect instances for farm render."""

    order = pyblish.api.CollectorOrder - 0.49
    families = ["mantra_rop",
                "karma_rop",
                "redshift_rop",
                "arnold_rop",
                "vray_rop",
                "usdrender",
                "ass","pointcache", "redshiftproxy",
                "vdbcache", "model", "staticMesh",
                "rop.opengl", "usdrop", "camera"]

    targets = ["local", "remote"]
    label = "Collect farm instances"

    def process(self, instance):

        creator_attribute = instance.data["creator_attributes"]

        # Collect Render Target
        if creator_attribute.get("render_target") not in {
            "farm_split", "farm","farm_no_render"
        }:
            instance.data["farm"] = False
            instance.data["splitRender"] = False
            self.log.debug("Render on farm is disabled. "
                           "Skipping farm collecting.")
            return

        instance.data["farm"] = True

        if creator_attribute.get("render_target") == "farm_no_render":
            instance.data["farm_no_render"] = True
            self.log.debug("Skipping farm render job, using existing frames.")            
        else:
            instance.data["farm_no_render"] = False
            
        instance.data["splitRender"] = (
            creator_attribute.get("render_target") == "farm_split"
        )
