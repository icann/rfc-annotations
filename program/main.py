import os
import subprocess
import sys

import annotations  # create_from_status, create_from_errata
import drafts       # download_drafts
import errata       # read_errata, get_patches
import output       # create_index, create_files
import rfcfile      # download_rfcs
import util         # get_from_environment

''' Main creator for RFC annotations tools '''

# check python version
python_version = sys.version_info
if python_version[0] < 3 or (python_version[0] == 3 and python_version[1] < 7):
    print(f"Error: the minimum python version is 3.7.\n\nYou're running: {sys.version}", file=sys.stderr)
    exit(-1)

# Determine if they have rsync
p = subprocess.run("which rsync", capture_output=True, shell=True)
if not p.stdout:
    exit('Did not find rsync on system. Exiting.')

# determine and create directories
TXT_DIR = util.get_from_environment("TXT_DIR", "raw-originals")
GEN_DIR = util.get_from_environment("OUTPUT", "generated-html")
ANN_DIR = util.get_from_environment("ANNOTATIONS", "annotations")
ANN_DIR_GENERATED = os.path.join(ANN_DIR, "_generated")
for directory in [TXT_DIR, GEN_DIR, ANN_DIR, ANN_DIR_GENERATED]:
    if not os.path.exists(directory):
        os.mkdir(directory)

# determine list of RFCs to use
defaults = []
with open("rfcs-to-use.txt", "r") as file:
    for line in file.readlines():
        if not line.startswith("#"):
            defaults.append(line.strip())
RFC_LIST = util.get_from_environment("LIST", defaults)
if isinstance(RFC_LIST, str):
    RFC_LIST = RFC_LIST.strip().replace(",", " ").split()

if util.means_true(util.get_from_environment("FETCH_FILES", "YES")):
    rfcfile.download_rfcs(RFC_LIST, TXT_DIR)  # download desired RFC text files, if not already done
    drafts.download_drafts(TXT_DIR)  # sync *all* internet draft files (in XML and TXT format)

# read errata and patches
errata_list = errata.read_errata(TXT_DIR)
patches = errata.get_patches()

if util.means_true(util.get_from_environment("FETCH_FILES", "YES")):
    # create additional annotation files
    annotations.create_from_status(RFC_LIST, ANN_DIR_GENERATED, TXT_DIR, errata_list, patches)
    annotations.create_from_errata(RFC_LIST, ANN_DIR_GENERATED, errata_list, patches)

# create html files
rfcs_last_updated = output.create_files(RFC_LIST, errata_list, patches, TXT_DIR, ANN_DIR, GEN_DIR)

# create index.html if necessary
if util.means_true(util.get_from_environment("INDEX", "NO")):
    output.create_index(RFC_LIST, GEN_DIR, TXT_DIR, rfcs_last_updated)
