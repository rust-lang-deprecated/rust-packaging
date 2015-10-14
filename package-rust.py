#!/usr/bin/env python2.7
# Copyright 2015 The Rust Project Developers. See the COPYRIGHT
# file at the top-level directory of this distribution and at
# http://rust-lang.org/COPYRIGHT.
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import sys, os, subprocess, shutil, datetime, glob

# Parse configuration

make_comb = True
make_exe = False
make_pkg = False
make_msi = False
msi_sval = False # skip msi validation
target = None

for arg in sys.argv:
    if arg == "--no-combined":
        make_comb = False
    elif arg == "--exe":
        make_exe = True
    elif arg == "--pkg":
        make_pkg = True
    elif arg == "--msi":
        make_msi = True
    elif arg == "--msi-sval":
        msi_sval = True
    elif "--target" in arg:
        target = arg.split("=")[1]

print
print "target: " + str(target)
print "combined: " + str(make_comb)
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
# NB: rust-std was recently separated from rustc. Not all channels will actually have rust-std yet
components = [RUSTC_PACKAGE_NAME, "cargo", "rust-docs", "rust-std"]
if "pc-windows-gnu" in target:
    components.append("rust-mingw")

# Now find the names of the tarballs that belong to those components
inputs = []
package_version = None
rustc_installer = None
cargo_installer = None
docs_installer = None
mingw_installer = None
std_installer = None
for component in components:
    component_installer = None
    for filename in os.listdir(INPUT_DIR):
        if target in filename and component in filename:
            # Hack: several components contain 'rust' in the name
            # FIXME: Does this even do anything? 'rust' is not in the components list.
            if not (component == "rust" and ("rust-docs" in filename or "rust-mingw" in filename or "rust-std" in filename)):
                component_installer = filename

    # FIXME coping with missing rust-std
    if not component_installer and component != "rust-std":
        print "unable to find installer for component " + component + ", target " + target
        sys.exit(1)
    # FIXME coping with missing rust-std
    if component_installer:
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
    if component == "rust-std":
        std_installer = component_installer

# HACK: When the rust-std package split from rustc, we needed to ensure
# that during upgrades rustc was upgraded before rust-std, to avoid
# rustc clobbering the std files during uninstall. This sort serves
# to put rustc before rust-std in the component list.
inputs.sort(reverse = True)

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
shutil.copyfile(rustc_dir + "/version", overlay_dir + "/version")

# Use a custom README that explains how to install
shutil.copyfile("./etc/README.md", overlay_dir + "/README.md")

if make_comb:
    # Combine the installers
    tarball_list=",".join(inputs)
    package_name=COMBINED_PACKAGE_NAME + "-" + package_version + "-" + target
    run(["sh", "./rust-installer/combine-installers.sh",
         "--product-name=Rust",
         "--rel-manifest-dir=rustlib",
         "--success-message=Rust-is-ready-to-roll.",
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
# Examples:
# 1.0.0-alpha.2 (522d09dfe 2015-02-19) (built 2015-02-19)
# 1.0.0-nightly (b0746ff19 2015-03-05) (built 2015-03-06)

CFG_RELEASE_INFO = None
full_version = None
for line in open(os.path.join(rustc_dir, "version")):
    print "reported version: " + line
    full_version = line.split(" ")[0]
    CFG_RELEASE_INFO = line.strip()

assert full_version is not None
version_number = full_version.split("-")[0]
prerelease_version = ""
if "beta." in full_version or "alpha." in full_version:
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

CFG_VER_MAJOR, CFG_VER_MINOR, CFG_VER_PATCH = version_number.split('.')
CFG_VER_BUILD = str((datetime.date.today() - datetime.date(2000,1,1)).days) # days since Y2K

# Logic reproduced from main.mk
if channel == "stable":
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM
elif channel == "beta":
    CFG_PACKAGE_VERS="beta"
elif channel == "nightly":
    CFG_PACKAGE_VERS="nightly"
elif channel == "dev":
    CFG_PACKAGE_VERS=CFG_RELEASE_NUM + "-dev"
else:
    print "unknown release channel"
    sys.exit(1)

# This should be the same as the name on the tarballs
CFG_PACKAGE_NAME=COMBINED_PACKAGE_NAME + "-" + CFG_PACKAGE_VERS
CFG_BUILD=target
CFG_CHANNEL=channel

if "pc-windows-gnu" in target:
    CFG_MINGW="1"
else:
    CFG_MINGW="0"

if "x86_64" in target:
    CFG_PLATFORM = "x64"
elif "i686":
    CFG_PLATFORM = "x86"

# Export all vars starting with CFG_
cfgs = [pair for pair in locals().items() if pair[0].startswith("CFG_")]
cfgs.sort()
for k,v in cfgs:
    print k,"=",v
    os.environ[k] = v

if make_pkg:
    print "creating .pkg"

    assert docs_installer is not None
    assert cargo_installer is not None

    rustc_package_name = rustc_installer.replace(".tar.gz", "")
    docs_package_name = docs_installer.replace(".tar.gz", "")
    cargo_package_name = cargo_installer.replace(".tar.gz", "")
    if std_installer:
        std_package_name = std_installer.replace(".tar.gz", "") + "-" + target
    else:
        std_package_name = None

    os.mkdir(TEMP_DIR + "/pkg")

    shutil.copytree(TEMP_DIR + "/work/" + rustc_package_name, TEMP_DIR + "/pkg/rustc")
    shutil.copytree(TEMP_DIR + "/work/" + cargo_package_name, TEMP_DIR + "/pkg/cargo")
    shutil.copytree(TEMP_DIR + "/work/" + docs_package_name, TEMP_DIR + "/pkg/rust-docs")
    if std_installer:
        shutil.copytree(TEMP_DIR + "/work/" + std_package_name, TEMP_DIR + "/pkg/rust-std")

    # The package root, extracted from a tarball has entirely wrong permissions.
    # This goes over everything and fixes them.
    run(["chmod", "-R", "u+rwX,go+rX,go-w", TEMP_DIR + "/pkg"])
    for filename in os.listdir(TEMP_DIR + "/pkg/rustc/rustc/bin"):
        run(["chmod", "0755", TEMP_DIR + "/pkg/rustc/rustc/bin/" + filename])
    for filename in os.listdir(TEMP_DIR + "/pkg/cargo/cargo/bin"):
        run(["chmod", "0755", TEMP_DIR + "/pkg/cargo/cargo/bin/" + filename])

    # Copy the postinstall script that will execute install.sh
    shutil.copyfile("./pkg/postinstall", TEMP_DIR + "/pkg/rustc/postinstall")
    run(["chmod", "a+x", TEMP_DIR + "/pkg/rustc/postinstall"])
    shutil.copyfile("./pkg/postinstall", TEMP_DIR + "/pkg/cargo/postinstall")
    run(["chmod", "a+x", TEMP_DIR + "/pkg/cargo/postinstall"])
    shutil.copyfile("./pkg/postinstall", TEMP_DIR + "/pkg/rust-docs/postinstall")
    run(["chmod", "a+x", TEMP_DIR + "/pkg/rust-docs/postinstall"])
    if std_installer:
        shutil.copyfile("./pkg/postinstall", TEMP_DIR + "/pkg/rust-std/postinstall")
        run(["chmod", "a+x", TEMP_DIR + "/pkg/rust-std/postinstall"])

    pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.rustc " + \
        "--scripts " + TEMP_DIR + "/pkg/rustc --nopayload " + TEMP_DIR + "/pkg/rustc.pkg"
    run(["sh", "-c", pkgbuild_cmd])
    pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.cargo " + \
        "--scripts " + TEMP_DIR + "/pkg/cargo --nopayload " + TEMP_DIR + "/pkg/cargo.pkg"
    run(["sh", "-c", pkgbuild_cmd])
    pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.rust-docs " + \
        "--scripts " + TEMP_DIR + "/pkg/rust-docs --nopayload " + TEMP_DIR + "/pkg/rust-docs.pkg"
    run(["sh", "-c", pkgbuild_cmd])
    if std_installer:
        pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.rust-std " + \
            "--scripts " + TEMP_DIR + "/pkg/rust-std --nopayload " + TEMP_DIR + "/pkg/rust-std.pkg"
        run(["sh", "-c", pkgbuild_cmd])

    # Also create an 'uninstall' package
    os.mkdir(TEMP_DIR + "/pkg/uninstall")
    shutil.copyfile("./pkg/postinstall", TEMP_DIR + "/pkg/uninstall/postinstall")
    run(["chmod", "a+x", TEMP_DIR + "/pkg/uninstall/postinstall"])
    pkgbuild_cmd = "pkgbuild --identifier org.rust-lang.uninstall " + \
        "--scripts " + TEMP_DIR + "/pkg/uninstall --nopayload " + TEMP_DIR + "/pkg/uninstall.pkg"
    run(["sh", "-c", pkgbuild_cmd])

    os.mkdir(TEMP_DIR + "/pkg/res")
    shutil.copyfile(TEMP_DIR + "/LICENSE.txt", TEMP_DIR + "/pkg/res/LICENSE.txt")
    shutil.copyfile("./gfx/rust-logo.png", TEMP_DIR + "/pkg/res/rust-logo.png")
    if std_installer:
        productbuild_cmd = "productbuild --distribution ./pkg/Distribution.xml " + \
            "--resources " + TEMP_DIR + "/pkg/res " + OUTPUT_DIR + "/" + package_name + ".pkg " + \
            "--package-path " + TEMP_DIR + "/pkg"
    else:
        productbuild_cmd = "productbuild --distribution ./pkg/Distribution-old.xml " + \
            "--resources " + TEMP_DIR + "/pkg/res " + OUTPUT_DIR + "/" + package_name + ".pkg " + \
            "--package-path " + TEMP_DIR + "/pkg"
    run(["sh", "-c", productbuild_cmd])

if make_exe or make_msi:
    if make_exe:
        print "creating .exe"
    if make_msi:
        print "creating .msi"

    assert docs_installer is not None
    assert cargo_installer is not None

    exe_temp_dir = TEMP_DIR + "/exe"
    os.mkdir(exe_temp_dir)
    run(["tar", "xzf", INPUT_DIR + "/" + rustc_installer, "-C", exe_temp_dir])
    run(["tar", "xzf", INPUT_DIR + "/" + docs_installer, "-C", exe_temp_dir])
    run(["tar", "xzf", INPUT_DIR + "/" + cargo_installer, "-C", exe_temp_dir])
    if std_installer:
        run(["tar", "xzf", INPUT_DIR + "/" + std_installer, "-C", exe_temp_dir])
    orig_rustc_dir = exe_temp_dir + "/" + rustc_installer.replace(".tar.gz", "") + "/rustc"
    orig_docs_dir = exe_temp_dir + "/" + docs_installer.replace(".tar.gz", "") + "/rust-docs"
    orig_cargo_dir = exe_temp_dir + "/" + cargo_installer.replace(".tar.gz", "") + "/cargo"
    if std_installer:
        orig_std_dir = exe_temp_dir + "/" + std_installer.replace(".tar.gz", "") + "/rust-std-" + target
    else:
        orig_std_dir = None

    # Move these to locations needed by the iscc script and wix sources
    rustc_dir = exe_temp_dir + "/rustc"
    docs_dir = exe_temp_dir + "/rust-docs"
    cargo_dir = exe_temp_dir + "/cargo"
    std_dir = exe_temp_dir + "/rust-std"
    os.rename(orig_rustc_dir, rustc_dir)
    os.rename(orig_docs_dir, docs_dir)
    os.rename(orig_cargo_dir, cargo_dir)
    if std_installer:
        os.rename(orig_std_dir, std_dir)

    if mingw_installer is not None:
        run(["tar", "xzf", INPUT_DIR + "/" + mingw_installer, "-C", exe_temp_dir])
        orig_mingw_dir = exe_temp_dir + "/" + mingw_installer.replace(".tar.gz", "") + "/rust-mingw"
        mingw_dir = exe_temp_dir + "/rust-mingw"
        os.rename(orig_mingw_dir, mingw_dir)
    else:
        assert "pc-windows-gnu" not in target

    # Remove the installer files we don't need
    dir_comp_pairs = [(rustc_dir, "rustc"), (docs_dir, "rust-docs"),
                      (cargo_dir, "cargo")]
    if std_installer:
        dir_comp_pairs += [(std_dir, "rust-std")]
    if mingw_installer is not None:
        dir_comp_pairs += [(mingw_dir, "rust-mingw")]
    for dir_and_component in dir_comp_pairs:
        dir_ = dir_and_component[0]
        component = dir_and_component[1]
        os.remove(dir_ + "/manifest.in")

    if make_exe:
        # Copy installer files, etc.
        shutil.copyfile("./exe/rust.iss", exe_temp_dir + "/rust.iss")
        shutil.copyfile("./exe/rust-old.iss", exe_temp_dir + "/rust-old.iss")
        shutil.copyfile("./exe/modpath.iss", exe_temp_dir + "/modpath.iss")
        shutil.copyfile("./exe/upgrade.iss", exe_temp_dir + "/upgrade.iss")
        shutil.copyfile("./gfx/rust-logo.ico", exe_temp_dir + "/rust-logo.ico")
        shutil.copyfile(TEMP_DIR + "/LICENSE.txt", exe_temp_dir + "/LICENSE.txt")

        cwd=os.getcwd()
        os.chdir(exe_temp_dir)
        if std_installer:
            args = ["iscc", "rust.iss"]
        else:
            args = ["iscc", "rust-old.iss"]
        if "windows-gnu" in target:
            args += ["/dMINGW"]
        run(args)
        os.chdir(cwd)

        exefile = CFG_PACKAGE_NAME + "-" + CFG_BUILD + ".exe"
        move_file(exe_temp_dir + "/" + exefile, OUTPUT_DIR + "/" + exefile)

    if make_msi:
        # Copy installer files, etc.
        for f in glob.glob("./msi/*"):
            shutil.copy(f, exe_temp_dir)
        for f in glob.glob("./gfx/*"):
            shutil.copy(f, exe_temp_dir)
        shutil.copy(TEMP_DIR + "/LICENSE.rtf", exe_temp_dir)

        cwd=os.getcwd()
        os.chdir(exe_temp_dir)
        if std_installer:
            run(["make", "SVAL=%i" % msi_sval])
        else:
            run(["make", "SVAL=%i" % msi_sval, "-f", "Makefile-old"])
        os.chdir(cwd)

        msifile = CFG_PACKAGE_NAME + "-" + CFG_BUILD + ".msi"
        move_file(exe_temp_dir + "/" + msifile, OUTPUT_DIR + "/" + msifile)
