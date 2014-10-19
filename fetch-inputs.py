#!/usr/bin/python

import sys, os, subprocess, shutil

target = None
channel = None

for arg in sys.argv:
    if arg == "--nightly":
        channel = "nightly"
    elif arg == "--beta":
        channel = "beta"
    elif arg == "--stable":
        channel = "stable"
    elif "--target" in arg:
        target = arg.split("=")[1]

print
print "target: " + str(target)
print

if channel == None:
    print "specify either --nightly, --beta, or --stable"
    sys.exit(1)
if target == None:
    print "specify --target"
    sys.exit(1)

SERVER_ADDRESS = "https://static.rust-lang.org"
RUST_DIST_FOLDER = "dist"
CARGO_DIST_FOLDER = "cargo-dist"
TEMP_DIR = "./tmp"

# Create the temp directory
if os.path.isdir(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.mkdir(TEMP_DIR)

# Download rust manifest
rust_manifest_name = "channel-rustc-" + channel
remote_rust_manifest = SERVER_ADDRESS + "/" + RUST_DIST_FOLDER + "/" + rust_manifest_name
print "rust manifest: " + remote_rust_manifest
cwd = os.getcwd()
os.chdir(TEMP_DIR)
retval = subprocess.call(["curl", "-f", "-O", remote_rust_manifest])
os.chdir(cwd)
if retval != 0:
    print "downlading rust manifest failed"
    sys.exit(1)

# Get list of artifacts for target
rust_artifacts = []
for line in open(TEMP_DIR + "/" + rust_manifest_name):
    if target in line:
        rust_artifacts += [line]

# Figure out corresponding cargo nightly. If the channel is nightly, then it's just the cargo nightly.
# If it's beta or stable then it's paired with a specific revision from the cargo-snap.txt file.
cargo_archive_date = None
if channel != "nightly":
    # Get the source artifact from which we'll dig out the version number
    # in order to figure out which cargo to pair with
    source = None
    for line in open(TEMP_DIR + "/" + rust_manifest_name):
        # Hack: should be looking for -src, but currently source tarballs are named somewhat ambiguously
        if "x86" not in line and "i686" not in line:
            source = line

    assert source != None
    assert False

# Download cargo manifest
cargo_manifest_name = "channel-cargo-" + channel
if cargo_archive_dir == None:
    remote_cargo_manifest = SERVER_ADDRESS + "/" + CARGO_DIST_FOLDER + "/" + cargo_manifest_name
else:
    remote_cargo_manifest = SERVER_ADDRESS + "/" + CARGO_DIST_FOLDER + "/" + cargo_archive_date + \
                            "/" + cargo_manifest_name

# Get artifacts for target

# Download all the artifacts
