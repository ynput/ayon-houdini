from ayon_houdini.api.lib import insert_ayon_load_button_after_file_parm
    
node = kwargs["node"] # noqa: F821
insert_ayon_load_button_after_file_parm(node.parm("fileName"))