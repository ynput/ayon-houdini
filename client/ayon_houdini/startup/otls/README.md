## How to create expanded HDAs

In order to be able to see the contents of HDAs and store them in version control (i.e. git) is really useful to expand them using the `hotl` binary that ships with Houdini (https://www.sidefx.com/docs/houdini/ref/utils/hotl.html), that way we can do small tweaks to the HDAs without needing to use Houdini and we can version control the changes done over time.

### How to

We run the following command, delete the original hda file and then rename the directory to match the hdafile name.
```
hotl -t directory hdafile
```

Example:
```
hotl -t ayon_lop_import ayon_lop_import.hda
rm ayon_lop_import.hda
mv ayon_lop_import ayon_lop_import.hda
```

### Where to find `hotl`

The `hotl` command ships with any of the Houdini install binaries, like for example:
```
./houdini/20.5.320/bin/hotl
```

Or using the `terminal` from AYON launcher in Houdini context. You should be
able to call just:
```
hotl 
```
