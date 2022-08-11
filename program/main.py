import os
import subprocess
import sys
from typing import Optional

import annotations  # create_from_status, create_from_errata
import drafts       # download_drafts
import errata       # read_errata, get_patches
import output       # create_index, create_files
import rfcfile      # download_rfcs
import util         # get_from_environment

''' Main creator for RFC annotations tools '''


def process_rfc_list(rfc_list: [str], index: Optional[str], prefix: Optional[str] = None):
    if util.means_true(util.get_from_environment("FETCH_FILES", "YES")):
        # download desired RFC text files, if not already done
        rfcfile.download_rfcs(rfc_list, TXT_DIR)
        # create additional annotation files
        annotations.create_from_status(rfc_list, ANN_DIR_GENERATED, TXT_DIR, errata_list, patches)
        annotations.create_from_errata(rfc_list, ANN_DIR_GENERATED, errata_list, patches)

    # create html files
    rfcs_last_updated = output.create_files(rfc_list, errata_list, patches, TXT_DIR, ANN_DIR, GEN_DIR)

    # create index.html if necessary
    if util.means_true(util.get_from_environment("INDEX", "NO")):
        output.create_index(prefix, rfc_list, GEN_DIR, TXT_DIR, index, rfcs_last_updated)


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

if util.means_true(util.get_from_environment("FETCH_FILES", "YES")):
    drafts.download_drafts(TXT_DIR)  # sync *all* internet draft files (in XML and TXT format)

# read errata and patches
errata_list = errata.read_errata(TXT_DIR)
patches = errata.get_patches()

# determine list of RFCs to use
INDEX_TEXT = util.get_from_environment("INDEX_TEXT", "")
RFC_LIST = util.get_from_environment("LIST", None)
if isinstance(RFC_LIST, str):
    RFC_LIST = RFC_LIST.strip().replace(",", " ").split()

if isinstance(RFC_LIST, list) and len(RFC_LIST) > 0:
    process_rfc_list(RFC_LIST, INDEX_TEXT)
else:
    filenames = []
    for directory in ["local-config", "default-config"]:
        for file_name in util.filtered_files(directory, "", "-rfcs.txt"):
            if file_name in filenames:
                print(f"RFC list {file_name} already handled. Ignoring file in {directory}.")
            else:
                filenames.append(file_name)
                defaults = []
                index_text = ""
                with open(os.path.join(directory, file_name), "r") as file:
                    for line in file.readlines():
                        if not line.startswith("#"):
                            if len(line) > 0 and line[0] in "0123456789":
                                defaults.append(line.strip())
                            else:
                                index_text += line
                if len(defaults) > 0:
                    process_rfc_list(defaults, INDEX_TEXT if len(INDEX_TEXT) > 0 else index_text, file_name[0:-9])
