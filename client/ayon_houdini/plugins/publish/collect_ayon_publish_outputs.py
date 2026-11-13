import os

import pyblish.api

from ayon_core.pipeline.publish import PublishError
from ayon_houdini.api import lib, plugin, ayon_publish

import hou


def _filter_existing_files(filepaths):
    """Split filepaths into existing files and missing files.

    Farm renders can produce fewer files than the ROP's frame range (e.g.
    Deadline node ranges), so only files that actually exist are published.

    Args:
        filepaths (list[str]): Expected output file paths.

    Returns:
        tuple[list[str], list[str]]: Existing file paths and missing paths.
    """
    existing = []
    missing = []
    for filepath in filepaths:
        if filepath and os.path.exists(filepath):
            existing.append(filepath)
        else:
            missing.append(filepath)
    return existing, missing


def _get_upstream_error_details(node):
    """Return formatted error details of upstream ROPs that failed.

    Houdini only reports ``Error rendering input: <node>`` when a ROP
    dependency fails to render. This collects the actual errors of the
    upstream ROPs so they can be shown on the AYON Publish ROP.

    Args:
        node (hou.RopNode): ROP node whose upstream errors are collected.

    Returns:
        list[str]: Formatted error messages of upstream nodes.
    """
    details = []
    for ancestor in node.inputAncestors():
        errors = ancestor.errors()
        if not errors:
            continue
        message = "; ".join(str(error) for error in errors)
        details.append(f"'{ancestor.path()}': {message}")
    return details


class CollectAYONPublishOutputs(plugin.HoudiniInstancePlugin):
    """Collect output representations for AYON Publish node"""

    order = pyblish.api.CollectorOrder
    label = "Collect AYON Publish ROP outputs"
    families = ["rop_publish"]

    multidot_extensions = [
        ".ass.gz",
        ".bgeo.sc",
        ".bgeo.gz",
        ".bgeo.lzma",
        ".bgeo.bz2",
    ]

    def process(self, instance):

        # Get the AYON Publish ROP node and the input ROPs we want to collect
        # as part of this instance.
        rop_node: hou.RopNode = hou.node(instance.data["instance_node"])

        # Clear a stale error state from a previous publish run, so a retry
        # from the Publisher UI does not keep showing the old failure.
        ayon_publish.clear_node_error(rop_node)

        # AYON Publish ROPs do not render files themselves, so a nested AYON
        # Publish ROP dependency would only cause the confusing Houdini
        # 'Error rendering input' failure.
        nested_publish_nodes = ayon_publish.get_nested_ayon_publish_nodes(
            rop_node)
        if nested_publish_nodes:
            raise PublishError(
                "The AYON Publish ROP depends on another AYON Publish ROP. "
                "AYON Publish ROPs do not write output files themselves, so "
                "they cannot be used as inputs or dependencies. Connect the "
                "native output ROP(s) directly instead.",
                title="Invalid AYON Publish ROP inputs",
                detail="Nested AYON Publish ROPs:\n{}".format(
                    "\n".join(
                        f" - {node.path()}" for node in nested_publish_nodes
                    )
                ),
            )

        if not instance.data.get("from_node", False):
            ayon_publish.set_ayon_publish_nodes_pre_render_script(
                rop_node,
                self.log,
                "",
            )
            try:
                self._rop_render(rop_node)

            finally:
                ayon_publish.set_ayon_publish_nodes_pre_render_script(
                    rop_node,
                    self.log,
                    "hou.phm().run()",
                )

        input_rops = rop_node.inputs()
        self.log.debug(f"Collecting AYON Publish ROP '{rop_node.path()}'")

        representations = instance.data.setdefault("representations", [])
        for input_rop in input_rops:
            self.log.debug(f"Processing: '{input_rop.path()}'")

            # Support fetch ROP by getting it source ROP and processing
            # that instead. This way we also support ROPs that are not inside
            # an ROPs network.
            if input_rop.type().name() == "fetch":
                fetched_rop = input_rop.parm("source").evalAsNode()
                if fetched_rop is None:
                    self.log.warning(
                        f"Skipping fetch ROP '{input_rop.path()}' as it has "
                        f"no valid source ROP set."
                    )
                    continue
                self.log.debug(f"Processing fetched ROP: {fetched_rop.path()}")
                input_rop = fetched_rop

            # TODO this does not work if first input is something like merge
            #  or switch
            try:
                filepaths = ayon_publish.get_rop_output(input_rop)
            except TypeError:
                self.log.warning(
                    f"Skipping unsupported ROP type '{input_rop.path()}' as "
                    "we can not detect its output files."
                )
                continue

            # "ip" and "md" are Houdini OpenGL output "targets" that do not
            # write files to disk; they cannot be published.
            first_file = filepaths[0] if filepaths else ""
            if not first_file or first_file in ("ip", "md"):
                raise PublishError(
                    f"The input ROP '{input_rop.path()}' has no output file "
                    "set. Set an output path on the ROP (for OpenGL ROPs set "
                    "an output image; 'ip'/'md' do not write files to disk)."
                )

            # Only publish files that actually exist on disk. A farm render
            # (e.g. Deadline node ranges) can render fewer files than the
            # ROP frame range suggests.
            filepaths, missing_files = _filter_existing_files(filepaths)
            if missing_files:
                self.log.warning(
                    "Skipping %d missing output file(s) of '%s': %s",
                    len(missing_files),
                    input_rop.path(),
                    ", ".join(missing_files),
                )
            if not filepaths:
                raise PublishError(
                    f"No output files were found for input ROP "
                    f"'{input_rop.path()}'. Render it first or check its "
                    "output path."
                )

            # Split extension, but allow for multi-dot extensions
            ext = lib.splitext(
                filepaths[0],
                allowed_multidot_extensions=self.multidot_extensions,
            )[-1].strip(".")

            # representation files must be single `str` if single file
            # and also must be the filename, not full path
            filenames = [os.path.basename(file) for file in filepaths]
            if len(filenames) == 1:
                filenames = filenames[0]

            representation = {
                "name": ext,
                "ext": ext,
                "files": filenames,
                "stagingDir": os.path.dirname(filepaths[0]),
            }
            self.log.debug(f"Collected representation: {representation}")
            representations.append(representation)

    def _rop_render(self, node: hou.RopNode):
        """Perform the render by node, it would raise Exception
        once there is error found.

        The error is also displayed on the node itself, see
        :func:`ayon_publish.set_node_error`.

        Args:
            node (hou.RopNode): rop node
        """
        try:
            node.render()

        except hou.Error as exc:
            message = f"Houdini error: {exc}"
            detail = None
            upstream_errors = _get_upstream_error_details(node)
            if upstream_errors:
                detail = "Upstream ROP errors:\n" + "\n".join(upstream_errors)
                message = f"{message}\n{detail}"
            ayon_publish.set_node_error(node, message)
            self.log.error(
                "Houdini error on '%s': %s", node.path(), exc,
                exc_info=True)
            raise PublishError(
                message,
                title="Failed to render AYON Publish ROP",
                detail=detail,
            ) from exc
        except Exception as exc:
            message = f"Unexpected error: {exc}"
            ayon_publish.set_node_error(node, message)
            self.log.error(
                "Unexpected error on '%s': %s", node.path(), exc,
                exc_info=True)
            raise PublishError(
                message,
                title="Failed to render AYON Publish ROP",
            ) from exc
