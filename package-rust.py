#!/usr/bin/env python2.7

import sys, os, subprocess, shutil, datetime

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
    print ' '.join(args)
    retval = subprocess.call(args)
    if retval != 0:
        print "call failed: " + str(args)
        sys.exit(1)

# Move file with target overwrite
def move_file(source, target):
    try: os.remove(target)
    except OSError: pass
    shutil.move(source, target)

INPUT_DIR = "./in"
OUTPUT_DIR = "./out"
TEMP_DIR = "./tmp"
RUSTC_PACKAGE_NAME = "rustc"
COMBINED_PACKAGE_NAME = "rust"

# Create the temp directory
if os.path.isdir(TEMP_DIR):
    print "Removing old temp..."
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
package_version = None
rustc_installer = None
cargo_installer = None
docs_installer = None
mingw_installer = None
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
    inputs.append(INPUT_DIR + "/" + component_installer)

    # Extract the version from the filename
    if component == RUSTC_PACKAGE_NAME:
        s = component_installer[len(RUSTC_PACKAGE_NAME) + 1:]
        p = s.find(target)
        package_version = s[:p - 1]
        rustc_installer = component_installer
    if component == "cargo":
        cargo_installer = component_installer
    if component == "rust-docs":
        docs_installer = component_installer
    if component == "rust-mingw":
        mingw_installer = component_installer


assert package_version is not None
assert rustc_installer is not None

# Set up the overlay of license info
run(["tar", "xzf", INPUT_DIR + "/" + rustc_installer, "-C", TEMP_DIR, ])

rustc_dir = TEMP_DIR + "/" + rustc_installer[:len(rustc_installer) - len(".tar.gz")]

overlay_dir = TEMP_DIR + "/overlay"
os.mkdir(overlay_dir)
shutil.copyfile(rustc_dir + "/COPYRIGHT", overlay_dir + "/COPYRIGHT")
shutil.copyfile(rustc_dir + "/LICENSE-APACHE", overlay_dir + "/LICENSE-APACHE")
shutil.copyfile(rustc_dir + "/LICENSE-MIT", overlay_dir + "/LICENSE-MIT")
shutil.copyfile(rustc_dir + "/README.md", overlay_dir + "/README.md")
shutil.copyfile(rustc_dir + "/version", overlay_dir + "/version")

# Combine the installers
tarball_list=",".join(inputs)
package_name=COMBINED_PACKAGE_NAME + "-" + package_version + "-" + target
run(["sh", "./rust-installer/combine-installers.sh",
     "--product-name=Rust",
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
cmd = "cat {0}/COPYRIGHT {0}/LICENSE-APACHE {0}/LICENSE-MIT > {1}".format(rustc_dir, license_file)
run(["sh", "-c", cmd])
if make_msi:
    license_rtf = TEMP_DIR + "/LICENSE.rtf"
    # Convert plain text to RTF
    with open(license_file, "rt") as input:
        with open(license_rtf, "wt") as output:
            output.write(r"{\rtf1\ansi\deff0{\fonttbl{\f0\fnil\fcharset0 Arial;}}\nowwrap\fs18"+"\n")
            for line in input.readlines():
                output.write(line)
                output.write(r"\line ")
            output.write("}")

# Reconstruct the following variables from the Rust makefile from the version number.
# Currently these are needed by the Windows installer.
CFG_RELEASE_NUM = None
CFG_PRERELEASE_VERSION = None
CFG_RELEASE = None
CFG_PACKAGE_NAME = None
CFG_BUILD = None
CFG_PACKAGE_VERS = None

# Pull the version number out of the version file
full_version = None
for line in open(os.path.join(rustc_dir, "version")):
    print "reported version: " + line
    full_version = line.split(" ")[0]

assert full_version is not None
version_number = full_version.split("-")[0]
prerelease_version = ""
if "beta." in full_version:
    prerelease_version = "." + full_version.split(".")[-1]

# Guess the channel from the version
channel = None
if "nightly" in full_version:
    channel = "nightly"
elif "beta" in full_version or "alpha" in full_version:
    channel = "beta"
elif "dev" in full_version:
    channel = "dev"
else:
    channel = "stable"

CFG_RELEASE_NUM=version_number
CFG_RELEASE=full_version
CFG_PRERELEASE_VERSION=prerelease_version

# Logic reproduced from main.mk
if channel == "stable":
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM
    # UpgradeCode shoud stay the same for all MSI versions in channel
    CFG_UPGRADE_CODE="1C7CADA5-D117-43F8-A356-DF15F9FBEFF6"
    CFG_MSI_VERSION=CFG_RELEASE_NUM
elif channel == "beta":
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM + "-beta" + CFG_PRERELEASE_VERSION
    CFG_UPGRADE_CODE="5229EAC1-AB7C-4A62-9881-6FAD2DE7D0F9"
    CFG_MSI_VERSION=CFG_RELEASE_NUM + "." + CFG_PRERELEASE_VERSION
elif channel == "nightly":
    CFG_PACKAGE_VERS="nightly"
    CFG_UPGRADE_CODE="B94FF1C2-2C7B-4859-A08B-546815516FDA"
    now=datetime.datetime.now()
    build=now.year*10+now.month*100+now.day
    CFG_MSI_VERSION=CFG_RELEASE_NUM+"."+str(build)
elif channel == "dev":
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM + "-dev"
    CFG_UPGRADE_CODE="7E6D1349-2773-4792-B8CD-EA2685D86A99"
    CFG_MSI_VERSION="255.255.65535.99999"
else:
    print "unknown release channel"
    sys.exit(1)

# This should be the same as the name on the tarballs
CFG_PACKAGE_NAME=COMBINED_PACKAGE_NAME + "-" + CFG_PACKAGE_VERS
CFG_BUILD=target
CFG_CHANNEL=channel

os.environ["CFG_CHANNEL"] = CFG_CHANNEL
os.environ["CFG_RELEASE_NUM"] = CFG_RELEASE_NUM
os.environ["CFG_RELEASE"] = CFG_RELEASE
os.environ["CFG_PACKAGE_NAME"] = CFG_PACKAGE_NAME
os.environ["CFG_UPGRADE_CODE"] = CFG_UPGRADE_CODE
os.environ["CFG_MSI_VERSION"] = CFG_MSI_VERSION
os.environ["CFG_BUILD"] = CFG_BUILD

print "CFG_CHANNEL: " + CFG_CHANNEL
print "CFG_RELEASE_NUM: " + CFG_RELEASE_NUM
print "CFG_RELEASE: " + CFG_RELEASE
print "CFG_PACKAGE_NAME: " + CFG_PACKAGE_NAME
print "CFG_UPGRADE_CODE: " + CFG_UPGRADE_CODE
print "CFG_MSI_VERSION: " + CFG_MSI_VERSION
print "CFG_BUILD: " + CFG_BUILD

if make_pkg:
    print "creating .pkg"
    os.mkdir(TEMP_DIR + "/pkg")
    shutil.copytree(TEMP_DIR + "/work/" + package_name, TEMP_DIR + "/pkg/root")
    # The package root, extracted from a tarball has entirely wrong permissions.
    # This goes over everything and fixes them.
    run(["chmod", "-R", "u+rwX,go+rX,go-w", TEMP_DIR + "/pkg/root"])
    for filename in os.listdir(TEMP_DIR + "/pkg/root/bin"):
        run(["chmod", "0755", TEMP_DIR + "/pkg/root/bin/" + filename])

    # Remove everything under the root. These all shouldn't be installed.
    for filename in os.listdir(TEMP_DIR + "/pkg/root"):
        if os.path.isfile(TEMP_DIR + "/pkg/root/" + filename):
            run(["rm", TEMP_DIR + "/pkg/root/" + filename])

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

if make_exe or make_msi:
    if make_exe:
        print "creating .exe"
    if make_msi:
        print "creating .msi"

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

    # Move these to locations needed by the iscc script and wix sources
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

    if make_exe:
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
        move_file(exe_temp_dir + "/" + exefile, OUTPUT_DIR + "/" + exefile)

    if make_msi:
        # Copy installer files, etc.
        for f in ("Makefile", "rust.wxs", "remove-duplicates.xsl", "squash-components.xsl"):
            shutil.copy("./msi/" + f, exe_temp_dir)
        shutil.copy("./gfx/rust-logo.ico", exe_temp_dir)
        shutil.copy(TEMP_DIR + "/LICENSE.rtf", exe_temp_dir)

        cwd=os.getcwd()
        os.chdir(exe_temp_dir)
        run(["make"])
        os.chdir(cwd)

        msifile = CFG_PACKAGE_NAME + "-" + CFG_BUILD + ".msi"
        move_file(exe_temp_dir + "/" + msifile, OUTPUT_DIR + "/" + msifile)
