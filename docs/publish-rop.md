# AYON Publish ROP

The **AYON Publish ROP** (`/out` › `AYON Publish`) publishes the output files
of any ROPs connected to it as a single AYON product. It is a generic building
block: any ROP that writes files can be published as a product of your choice,
including custom studio ROPs and cache nodes such as a `FileCache`.

## Creating

1. Create the node from the AYON Publisher UI (recommended), or from the
   `/out` tab menu › **AYON Publish**.
2. Set the context (`Folder Path`, `Task Name`), `Variant` and `Product Type`.
   Use the picker buttons next to `Folder Path` and `Task Name` to select from
   the current AYON project's folders and the folder's tasks. Use the picker
   button next to `Variant` to choose from the creator's
   configured default variants and the variants already used by AYON Publish
   ROPs in the scene.
   The product type defaults to `rop_publish`; the ROP menu and the Publisher
   UI list the common AYON product types. Studio product types can be
   configured in the addon settings (`Create AYON Publish ROP` ›
   `Product Type Items`).
3. Connect one or more ROPs to the AYON Publish ROP. Each input ROP produces
   one representation; the representation name is the file extension of the
   ROP's output.

## Demo: publishing a cache with a FileCache node

The AYON Publish ROP does not care how the files were produced. This works with
native Houdini ROPs (Alembic, Geometry, …), the SideFX LABs FileCache, and
custom studio ROPs, as long as the ROP writes files and exposes its output path.

Example setup for a cache:

1. Build/update your cache ROP in `/out` (e.g. a FileCache-style ROP or an
   Alembic ROP exporting `$HIP/cache/asset.$F4.abc`).
2. Make sure the ROP's output path is set and points to a writable directory.
3. Create an **AYON Publish ROP** and set:
   - `Product Type`: e.g. `pointcache` (or `model` for a static asset),
   - `Variant`: e.g. `Main`.
4. Connect the cache ROP to the AYON Publish ROP.
5. Save the Houdini workfile (publishing requires a saved workfile).
6. Publish:
   - **Publisher UI**: publish the created instance; or
   - **Self-publish button**: `<AYON> Publish` (when
     `houdini.general.add_self_publish_button` is enabled); or
   - **Render**: rendering the AYON Publish ROP renders its connected
     dependencies and publishes their files.

The published product contains one representation per input ROP, e.g.
`abc`, `bgeo` or `vdb`, with the frames found on disk.

### Custom / studio ROPs

A custom ROP works when AYON can determine its output parameter. ROPs without a
`trange` / `f1`-`f3` frame range are treated as **single-output ROPs**: the
output file is evaluated once. This makes FileCache-style and studio ROPs work
without extra configuration. If a custom ROP type is not recognized at all,
connect a native ROP that writes the same files instead.

> **Do not chain AYON Publish ROPs.** An AYON Publish ROP does not write files
> itself; it only renders its input ROPs and publishes their output. Using one
> as an input/dependency of another causes Houdini's confusing
> `Error rendering input: <node>` message. The addon now rejects this with a
> clear validation error — connect the native output ROPs instead.

## Headless / farm publish

The ROP publishes headlessly through its pre-render script, which can be used
from a farm submitter (e.g. Deadline). A JSON publish report can be stored by
setting:

```text
AYON_PUBLISH_REPORT_PATH=/path/to/publish-report.json
```

The report (the same data the Publisher UI can export) is written even when
publishing fails, and `ayon_publish.publish()` returns the report data.

## Publish report on the node

The latest publish report is also stored on the AYON Publish ROP as **cached
user data** (not saved with the hip file). After a publish, use the buttons at
the bottom of the node parameters:

- **Save Publish Report...** — write the report to a JSON file.
- **Copy Publish Report** — copy the JSON report to the clipboard.

## Known issues / limitations

- **Unique extensions only:** two inputs exporting the same extension would
  create duplicate representations. This is rejected by a validator — give each
  input a unique extension (or publish them as separate products).
- **OpenGL ROPs:** the OpenGL "outputs" `ip` and `md` do not write files. Set a
  real output image, otherwise publishing fails with a clear error.
- **Saved workfile required:** AYON requires the workfile to be saved before
  publishing.
- **Frame range validators:** the generic frame range validators are skipped
  for AYON Publish ROPs because the publish ROP's own range does not describe
  its input ROPs. Set/validate the range on the connected ROPs instead.
- **Missing files:** expected files that are not on disk (e.g. when a farm
  render only covered a Deadline node range) are skipped with a warning; if no
  files exist, publishing fails. Stale files from older renders are not
  detected — the ROP's frame range remains the source of truth.
- **Workfile increment:** after a ROP-triggered publish finishes rendering in an
  interactive Houdini session, the workfile is incremented automatically (after
  the render, so downstream exports keep the old `$HIP` path during rendering).
  The increment is skipped for farm/batch renders and when the AYON Publish ROP
  still feeds downstream ROPs in the same network; use the Publisher UI publish
  if the workfile must be incremented in those cases.
- **Nested AYON Publish ROPs** are not supported (see above).

## Troubleshooting

| Message | Cause / fix |
| --- | --- |
| `Error rendering input: /out/<node>` | A dependency ROP failed to render. Check that node's own errors/comments. If it is another AYON Publish ROP, connect the native output ROP instead. |
| `has no output file set` | An input ROP has no output path, or uses `ip`/`md` (OpenGL). Set a real output file. |
| `No output files were found for input ROP` | The ROP did not render (yet), or writes elsewhere. Render it first / check its output path. |
| `Multiple input ROPs export the same file extension` | Give the inputs unique extensions or publish them separately. |
| `File not saved` | Save the Houdini workfile before publishing. |
| `Invalid Frame Range` on an AYON Publish ROP | This validator is skipped for AYON Publish ROPs; set the frame range on the input ROPs instead. |
| Node stays red with `AYON publish FAILED` after fixing the problem | Right-click the node → **Reset AYON Publish Error** (or run another publish; the stale state is cleared at the start of the next publish). |
| Workfile not incremented after a ROP render | Expected for farm/batch renders and when the AYON Publish ROP has downstream ROP dependencies; publish via the Publisher UI to increment the workfile. |
