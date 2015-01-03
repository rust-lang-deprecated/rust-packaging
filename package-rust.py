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

if target is None:
    print "specify --target"
    sys.exit(1)

def run(args):
    retval = subprocess.call(args)
    if retval != 0:
        print "call failed: " + str(args)
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

if not os.path.isdir(OUTPUT_DIR):
    os.mkdir(OUTPUT_DIR)

# The names of the packages that need to be combined via rust-installer
components = [RUSTC_PACKAGE_NAME, "cargo", "rust-docs"]
if "pc-windows-gnu" in target:
    components.append("rust-mingw")

# Now find the names of the tarballs that belong to those components
inputs = []
version = None
rustc_installer = None
cargo_installer = None
docs_installer = None
mingw_installer = None
source_tarball = None
for component in components:
    component_installer = None
    for filename in os.listdir(INPUT_DIR):
        if target in filename and component in filename:
            # Hack: several components contain 'rust' in the name
            if not (component == "rust" and ("rust-docs" in filename or "rust-mingw" in filename)):
                component_installer = filename

        if "-src" in filename:
            source_tarball = filename

    if not component_installer:
        print "unable to find installer for component " + component + ", target " + target
        sys.exit(1)
    inputs.append(INPUT_DIR + "/" + component_installer)

    # Extract the version from the filename
    if component == RUSTC_PACKAGE_NAME:
        s = component_installer[len(RUSTC_PACKAGE_NAME) + 1:]
        p = s.find(target)
        version = s[:p - 1]
        rustc_installer = component_installer
    if component == "cargo":
        cargo_installer = component_installer
    if component == "rust-docs":
        docs_installer = component_installer
    if component == "rust-mingw":
        mingw_installer = component_installer


assert version is not None
assert rustc_installer is not None
assert source_tarball is not None

# Set up the overlay of license info
run(["tar", "xzf", INPUT_DIR + "/" + rustc_installer, "-C", TEMP_DIR, ])

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
run(["sh", "./rust-installer/combine-installers.sh",
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

# Everything below here is used for producing non-rust-installer packaging

# Create the LICENSE.txt file used in some GUI installers
license_file = TEMP_DIR + "/LICENSE.txt"
cmd = "cat " + \
    rustc_dir + "/COPYRIGHT " + rustc_dir + "/LICENSE-APACHE " + rustc_dir + "/LICENSE-MIT " + \
    "> " + license_file
run(["sh", "-c", cmd])

# Fish out the following Makefile variables from the source code or rebuild them somehow.
# Currently these are needed by the Windows installer.
CFG_RELEASE_NUM = None
CFG_BETA_CYCLE = None
CFG_RELEASE = None
CFG_PACKAGE_NAME = None
CFG_BUILD = None
CFG_PACKAGE_VERS = None

run(["tar", "xzf", INPUT_DIR + "/" + source_tarball, "-C", TEMP_DIR])
source_dir = os.path.join(TEMP_DIR, source_tarball.replace("-src.tar.gz", ""))

for line in open(source_dir + "/mk/main.mk"):
    if "CFG_RELEASE_NUM" in line and CFG_RELEASE_NUM is None:
        CFG_RELEASE_NUM = line.split("=")[1].strip()
        assert len(CFG_RELEASE_NUM) > 0
    if "CFG_BETA_CYCLE" in line and CFG_BETA_CYCLE is None:
        CFG_BETA_CYCLE = line.split("=")[1].strip()
        # NB: This can be an empty string

assert CFG_RELEASE_NUM is not None

# FIXME Temporary hack
if CFG_BETA_CYCLE is None:
    CFG_BETA_CYCLE = ""
assert CFG_BETA_CYCLE is not None

# Guess the channel from the source tarball
channel = None
if "nightly" in source_tarball:
    channel = "nightly"
elif "beta" in source_tarball:
    channel = "beta"
elif "dev" in source_tarball:
    channel = "dev"
else:
    channel = "stable"

# Logic reproduced from main.mk
if channel == "stable":
    CFG_RELEASE=CFG_RELEASE_NUM
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM
elif channel == "beta":
    CFG_RELEASE=CFG_RELEASE_NUM + "-beta" + CFG_BETA_CYCLE
    CFG_PACKAGE_VERS="beta"
elif channel == "nightly":
    CFG_RELEASE=CFG_RELEASE_NUM + "-nightly"
    CFG_PACKAGE_VERS="nightly"
elif channel == "dev":
    CFG_RELEASE=CFG_RELEASE_NUM + "-dev"
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM + "-dev"
else:
    print "unknown release channel"
    sys.exit(1)

# This should be the same as the name on the tarballs
CFG_PACKAGE_NAME=COMBINED_PACKAGE_NAME + "-" + CFG_PACKAGE_VERS
CFG_BUILD=target

os.environ["CFG_RELEASE_NUM"] = CFG_RELEASE_NUM
os.environ["CFG_RELEASE"] = CFG_RELEASE
os.environ["CFG_PACKAGE_NAME"] = CFG_PACKAGE_NAME
os.environ["CFG_BUILD"] = CFG_BUILD

if make_pkg:
    print "creating .pkg"
    os.mkdir(TEMP_DIR + "/pkg")
    shutil.copytree(TEMP_DIR + "/work/" + package_name, TEMP_DIR + "/pkg/root")
    os.mkdir(TEMP_DIR + "/pkg/res")
    shutil.copyfile(TEMP_DIR + "/LICENSE.txt", TEMP_DIR + "/pkg/res/LICENSE.txt")
    shutil.copyfile("./pkg/welcome.rtf", TEMP_DIR + "/pkg/res/welcome.rtf")
    shutil.copyfile("./gfx/rust-logo.png", TEMP_DIR + "/pkg/res/rust-logo.png")
    pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.rust " + \
        "--root " + TEMP_DIR + "/pkg/root " + TEMP_DIR + "/pkg/rust.pkg"
    run(["sh", "-c", pkgbuild_cmd])
    productbuild_cmd = "productbuild --distribution ./pkg/Distribution.xml " + \
        "--resources " + TEMP_DIR + "/pkg/res " + OUTPUT_DIR + "/" + package_name + ".pkg " + \
        "--package-path " + TEMP_DIR + "/pkg"
    run(["sh", "-c", productbuild_cmd])

if make_exe:
    print "creating .exe"
    assert docs_installer is not None
    assert mingw_installer is not None
    assert cargo_installer is not None
    exe_temp_dir = TEMP_DIR + "/exe"
    os.mkdir(exe_temp_dir)
    run(["tar", "xzf", INPUT_DIR + "/" + rustc_installer, "-C", exe_temp_dir])
    run(["tar", "xzf", INPUT_DIR + "/" + docs_installer, "-C", exe_temp_dir])
    run(["tar", "xzf", INPUT_DIR + "/" + mingw_installer, "-C", exe_temp_dir])
    run(["tar", "xzf", INPUT_DIR + "/" + cargo_installer, "-C", exe_temp_dir])
    orig_rustc_dir = exe_temp_dir + "/" + rustc_installer.replace(".tar.gz", "")
    orig_docs_dir = exe_temp_dir + "/" + docs_installer.replace(".tar.gz", "")
    orig_mingw_dir = exe_temp_dir + "/" + mingw_installer.replace(".tar.gz", "")
    orig_cargo_dir = exe_temp_dir + "/" + cargo_installer.replace(".tar.gz", "")

    # Move these to locations needed by the iscc script
    rustc_dir = exe_temp_dir + "/rustc"
    docs_dir = exe_temp_dir + "/rust-docs"
    mingw_dir = exe_temp_dir + "/rust-mingw"
    cargo_dir = exe_temp_dir + "/cargo"
    os.rename(orig_rustc_dir, rustc_dir)
    os.rename(orig_docs_dir, docs_dir)
    os.rename(orig_mingw_dir, mingw_dir)
    os.rename(orig_cargo_dir, cargo_dir)

    # Remove the installer files we don't need
    dir_comp_pairs = [(rustc_dir, "rustc"), (docs_dir, "rust-docs"),
                      (mingw_dir, "rust-mingw"), (cargo_dir, "cargo")]
    for dir_and_component in dir_comp_pairs:
        dir_ = dir_and_component[0]
        component = dir_and_component[1]
        for file_ in ["components", "install.sh", "rust-installer-version"]:
            os.remove(dir_ + "/" + file_)
        os.remove(dir_ + "/manifest-" + component + ".in")

    # Copy installer files, etc.
    shutil.copyfile("./exe/rust.iss", exe_temp_dir + "/rust.iss")
    shutil.copyfile("./exe/modpath.iss", exe_temp_dir + "/modpath.iss")
    shutil.copyfile("./exe/upgrade.iss", exe_temp_dir + "/upgrade.iss")
    shutil.copyfile("./gfx/rust-logo.ico", exe_temp_dir + "/rust-logo.ico")
    shutil.copyfile(TEMP_DIR + "/LICENSE.txt", exe_temp_dir + "/LICENSE.txt")

    cwd=os.getcwd()
    os.chdir(exe_temp_dir)
    run(["iscc", "rust.iss"])
    os.chdir(cwd)

    exefile = CFG_PACKAGE_NAME + "-" + CFG_BUILD + ".exe"
    shutil.move(exe_temp_dir + "/" + exefile, OUTPUT_DIR + "/" + exefile)

# TODO Produce .msi
