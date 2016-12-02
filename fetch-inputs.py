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

import sys, os, subprocess, shutil

target = None
channel = None

for arg in sys.argv:
    if "--channel" in arg:
        channel = arg.split("=")[1]
    elif "--target" in arg:
        target = arg.split("=")[1]

print
print "target: " + str(target)
print "channel: " + str(channel)
print

if channel is None:
    print "specify --channel"
    sys.exit(1)
if target is None:
    print "specify --target"
    sys.exit(1)

SERVER_ADDRESS = os.getenv("RUST_DIST_SERVER", "https://static.rust-lang.org")
CARGO_SERVER_ADDRESS = os.getenv("CARGO_DIST_SERVER",
        "https://s3.amazonaws.com/rust-lang-ci/cargo-builds")
RUST_DIST_FOLDER = "dist"
TEMP_DIR = "./tmp"
IN_DIR = "./in"

# Create the temp directory
if os.path.isdir(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.mkdir(TEMP_DIR)

# Create the in directory
if os.path.isdir(IN_DIR):
    shutil.rmtree(IN_DIR)
os.mkdir(IN_DIR)

# Download rust manifest
rust_manifest_name = "channel-rustc-" + channel
remote_rust_dir = SERVER_ADDRESS + "/" + RUST_DIST_FOLDER
remote_rust_manifest = remote_rust_dir + "/" + rust_manifest_name
print "rust manifest: " + remote_rust_manifest
cwd = os.getcwd()
os.chdir(TEMP_DIR)
retval = subprocess.call(["curl", "-f", "-O", remote_rust_manifest])
if retval != 0:
    print "downlading rust manifest failed"
    sys.exit(1)
os.chdir(cwd)

# Get list of rust artifacts for target
rust_artifacts = []
rustc_installer = None
for line in open(os.path.join(TEMP_DIR, rust_manifest_name)):
    if target in line and ".tar.gz" in line:
        rust_artifacts.append(line.rstrip())
        if line.startswith("rustc-") and "-src" not in line:
            rustc_installer = line.rstrip()
assert len(rust_artifacts) > 0
print "rust artifacts: " + str(rust_artifacts)

assert rustc_installer is not None

# We'll use the source checksum as a fingerprint for synchronizing
# dist builds across platforms on the buildbot prior to uploading.
# FIXME: Would be nice to get this fingerprint from the 'version' file
# but that requires some buildbot changes.
rust_source = None
for line in open(os.path.join(TEMP_DIR, rust_manifest_name)):
    if "-src" in line:
        rust_source = line.rstrip()
        assert rust_source is not None
        print "rust source: " + rust_source

# Download the source
cwd = os.getcwd()
os.chdir(IN_DIR)
full_rust_source = remote_rust_dir + "/" + rust_source
retval = subprocess.call(["curl", "-f", "-O", full_rust_source])
if retval != 0:
    print "downloading source failed"
    sys.exit(1)
os.chdir(cwd)

# Download the rust artifacts
full_rust_artifacts = [remote_rust_dir + "/" + x for x in rust_artifacts]
for artifact in full_rust_artifacts:
    cwd = os.getcwd()
    os.chdir(IN_DIR)
    retval = subprocess.call(["curl", "-f", "-O", artifact])
    if retval != 0:
        print "downlading " + artifact + " failed"
        sys.exit(1)
    os.chdir(cwd)


cargo_branch = 'master'
if channel != "nightly":
    retval = subprocess.call(["tar", "xzf", IN_DIR + "/" + rustc_installer, "-C", TEMP_DIR])
    if retval != 0:
        print "untarring source failed"
        sys.exit(1)
    rustc_installer_dir = os.path.join(TEMP_DIR, rustc_installer.replace(".tar.gz", ""))

    # Pull the version number out of the version file
    version = None
    for line in open(os.path.join(rustc_installer_dir, "version")):
        print "reported version: " + line
        version = line.split(" ")[0].split("-")[0]

    assert version is not None
    print "cargo version key: " + version
    cargo_branch = 'rust-' + version

proc = subprocess.Popen(["curl",
                         "-H", "Accept: application/vnd.github.3.sha",
                         "-sSf",
                         "https://api.github.com/repos/rust-lang/cargo/commits/" + cargo_branch],
                        stdout=subprocess.PIPE)
(cargo_rev, err) = proc.communicate()
exit_code = proc.wait()
if exit_code != 0:
    print "failed to fetch most recent commit: " + err
print "cargo rev: " + str(cargo_rev)

# Download cargo
artifact_name = "cargo-nightly-" + target + ".tar.gz"
artifact = CARGO_SERVER_ADDRESS + "/" + cargo_rev + "/" + artifact_name
cwd = os.getcwd()
os.chdir(IN_DIR)
retval = subprocess.call(["curl", "-f", "-O", artifact])
if retval != 0:
    print "downlading " + artifact + " failed"
    sys.exit(1)
os.chdir(cwd)
