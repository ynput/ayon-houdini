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
        
            if ropnode.evalParm(f'husk_sc_enable{i}'):

                # slap comp cli expects a path to apex node.
                if ropnode.evalParm(f'husk_sc_source{i}') != "file":
                    self.log.warning(
                        "Slap Comp on farm only works with slap files!"
                    )
                    continue
                
                slapcomp_src = ropnode.evalParm(f'husk_sc_file{i}')
                
                name = ropnode.evalParm(f'husk_sc_label{i}')
               
                mapinput = []

                for j in range(1, ropnode.evalParm(f'husk_sc_mapinput{i}')+1):
                    src_aov = ropnode.evalParm(f'husk_sc_in{i}_aov{j}')
                    dst_cop = ropnode.evalParm(f'husk_sc_in{i}_cop{j}')
                    if src_aov or dst_cop:
                        mapinput.append(f"{src_aov}:{dst_cop}")

                mapinput = ",".join(mapinput)

                mapoutput = []
                for j in range(1, ropnode.evalParm(f'husk_sc_mapoutput{i}')+1):
                    src_cop = ropnode.evalParm(f'husk_sc_out{i}_cop{j}')
                    dst_aov = ropnode.evalParm(f'husk_sc_out{i}_aov{j}')
                    if src_cop or dst_aov:
                        mapoutput.append(f"{src_cop}:{dst_aov}")

                mapoutput = ",".join(mapoutput)
                
                options = {
                    "name": name,
                    "mapinput": mapinput,
                    "mapoutput": mapoutput,
                }

                options = "&".join(
                    f"{option}={value}" for option, value in options.items() if value
                )

                if options: 
                    slapcomp_src += f"?{options}"

                self.log.debug(
                    f"Found Slap Comp: {slapcomp_src}"
                )
                
                slapcomp_sources.append(slapcomp_src)

        instance.data["slapComp"] = slapcomp_sources