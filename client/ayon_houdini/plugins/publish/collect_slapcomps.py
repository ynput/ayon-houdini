from __future__ import annotations
import hou
import pyblish.api

from ayon_houdini.api import plugin


class CollectSlapComps(plugin.HoudiniInstancePlugin):
    """Collect Slap Comps.

    It collects Slap Comps from the USD render rop node and
    save them as a list in `slapComp` key in `instance.data`.

    Each item in the list follows:
        slap_comp_path?option=value&option2=value2

    """

    order = pyblish.api.CollectorOrder
    label = "Collect Slap Comps"
    families = ["usdrender"]

    # Copernicus was introduced in Houdini 20.5 so we only enable this
    # Collect Slap Comps if the Houdini version is 20.5 or higher.
    enabled = hou.applicationVersion() >= (20, 5, 0)

    def process(self, instance):
        if not instance.data["farm"]:
            return

        node_path = instance.data.get("instance_node")
        if node_path is None:
            # Instance without instance node like a workfile instance
            self.log.debug(
                "No instance node found for instance: {}".format(instance)
            )
            return

        ropnode = hou.node(node_path)

        slapcomp_sources =  []

        comp_numbers = ropnode.evalParm("husk_slapcomp")
        for i in range(1, comp_numbers+1):

            if not ropnode.evalParm(f'husk_sc_enable{i}'):
                continue

            # slap comp cli expects a path to apex node.
            if ropnode.evalParm(f'husk_sc_source{i}') != "file":
                self.log.warning(
                    f"USD Render ROP '{node_path}' has Slap Comp {i}"
                    " enabled using a COP node. This is currently not"
                    " supported for farm rendering and will be skipped,"
                    " please use a file-based slap comp instead."
                )
                continue

            slapcomp_src = ropnode.evalParm(f'husk_sc_file{i}')
            name = ropnode.evalParm(f'husk_sc_label{i}')

            map_inputs: list[str] = []
            for j in range(1, ropnode.evalParm(f'husk_sc_mapinput{i}')+1):
                src_aov = ropnode.evalParm(f'husk_sc_in{i}_aov{j}')
                dst_cop = ropnode.evalParm(f'husk_sc_in{i}_cop{j}')
                if src_aov or dst_cop:
                    map_inputs.append(f"{src_aov}:{dst_cop}")

            map_outputs: list[str] = []
            for j in range(1, ropnode.evalParm(f'husk_sc_mapoutput{i}')+1):
                src_cop = ropnode.evalParm(f'husk_sc_out{i}_cop{j}')
                dst_aov = ropnode.evalParm(f'husk_sc_out{i}_aov{j}')
                if src_cop or dst_aov:
                    map_outputs.append(f"{src_cop}:{dst_aov}")

            options = {
                "name": name,
                "mapinput": ",".join(map_inputs),
                "mapoutput": ",".join(map_outputs),
            }

            options = "&".join(
                f"{option}={value}"
                for option, value in options.items() if value
            )

            if options:
                slapcomp_src += f"?{options}"

            self.log.debug(
                f"Found Slap Comp: {slapcomp_src}"
            )

            slapcomp_sources.append(slapcomp_src)

        instance.data["slapComp"] = slapcomp_sources
