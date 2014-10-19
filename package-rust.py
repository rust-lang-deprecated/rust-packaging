#!/usr/bin/python

import sys, os, subprocess, shutil

# Parse configuration

make_exe = False
make_pkg = False
make_msi = False
target = None

for arg in sys.argv:
    if arg == "--exe":
        make_exe = True
    elif arg == "--pkg":
        make_pkg = True
    elif arg == "--msi":
        make_msi = True
    elif "--target" in arg:
        target = arg.split("=")[1]

print
print "target: " + str(target)
print "exe: " + str(make_exe)
print "pkg: " + str(make_pkg)
print "msi: " + str(make_msi)
print

if target == None:
    print "specify --target"
    sys.exit(1)

INPUT_DIR = "./in"
OUTPUT_DIR = "./out"
TEMP_DIR = "./tmp"
RUSTC_PACKAGE_NAME = "rust"
COMBINED_PACKAGE_NAME = "rust-combined"

# Create the temp directory
if os.path.isdir(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.mkdir(TEMP_DIR)

# The names of the packages that need to be combined via rust-installer
components = [RUSTC_PACKAGE_NAME, "cargo", "rust-docs"]
if "pc-windows-gnu" in target:
    components += ["rust-mingw"]

# Now find the names of the tarballs that belong to those components
inputs = []
version = None
rustc_installer = None
for component in components:
    component_installer = None
    for filename in os.listdir(INPUT_DIR):
        if target in filename and component in filename:
            # Hack: several components contain 'rust' in the name
            if not (component == "rust" and ("rust-docs" in filename or "rust-mingw" in filename)):
                component_installer = filename
    if not component_installer:
        print "unable to find installer for component " + component + ", target " + target
        sys.exit(1)
    inputs += [INPUT_DIR + "/" + component_installer]

    # Extract the version from the filename
    if component == RUSTC_PACKAGE_NAME:
        s = component_installer[len(RUSTC_PACKAGE_NAME) + 1:]
        p = s.find(target)
        version = s[:p - 1]
        rustc_installer = component_installer

assert version != None
assert rustc_installer != None

# Set up the overlay of license info
retval = subprocess.call(["tar", "xzf", INPUT_DIR + "/" + rustc_installer, "-C", TEMP_DIR, ])
if retval != 0:
    print "tar failed"
    sys.exit(1)

rustc_dir = TEMP_DIR + "/" + rustc_installer[:len(rustc_installer) - len(".tar.gz")]

overlay_dir = TEMP_DIR + "/overlay"
os.mkdir(overlay_dir)
shutil.copyfile(rustc_dir + "/COPYRIGHT", overlay_dir + "/COPYRIGHT")
shutil.copyfile(rustc_dir + "/LICENSE-APACHE", overlay_dir + "/LICENSE-APACHE")
shutil.copyfile(rustc_dir + "/LICENSE-MIT", overlay_dir + "/LICENSE-MIT")
shutil.copyfile(rustc_dir + "/README.md", overlay_dir + "/README.md")

# Combine the installers
tarball_list=",".join(inputs)
package_name=COMBINED_PACKAGE_NAME + "-" + version + "-" + target
retval = subprocess.call(["sh", "./rust-installer/combine-installers.sh",
                          "--product-name=Rust",
                          "--verify-bin=rustc",
                          "--rel-manifest-dir=rustlib",
                          "--success-message=Rust-is-ready-to-roll",
                          "--work-dir=" + TEMP_DIR + "/work",
                          "--output-dir=" + OUTPUT_DIR,
                          "--package-name=" + package_name,
                          "--legacy-manifest-dirs=rustlib,cargo",
                          "--input-tarballs=" + tarball_list,
                          "--non-installed-overlay=" + overlay_dir
                      ])
if retval != 0:
    print "combine-installer failed"
    sys.exit(1)

# TODO Produce .pkg

# TODO Produce .exe

# TODO Produce .msi
