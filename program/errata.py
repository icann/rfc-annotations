import json
import os
from typing import Optional

import util  # correct_path, create_checksum, config_directories, debug, info, error, urlopen

''' Create errata for RFC annotations tools '''


# returns a cached version of https://www.rfc-editor.org/errata.json (will be created if absent)
def read_errata(path: str = ".", url: str = "https://www.rfc-editor.org/errata.json") -> Optional[list]:
    file_path = os.path.join(path, "errata.json")
    document = None
    # noinspection PyBroadException
    try:
        with open(file_path, "rb") as f:
            document = json.loads(f.read())
    except Exception:
        pass

    if document is None:
        util.info(f"\nFetching errata from source of truth {url}... ", end='')
        try:
            json_content = util.urlopen(url).read()
            util.info("Done")
            if type(json_content) is bytes:
                util.debug(f"Retrieved {len(json_content)} bytes of data. Parsing... ", end='')
                with open(file_path, "wb") as f:
                    f.write(json_content)
                    document = json.loads(json_content)
            else:
                util.error(f"got unexpected fetching response data of type {type(json_content)}.")
        except Exception as e:
            util.error(f"returned with error: {e}.")
    else:
        util.debug("\nParsing cached errata.json...", end='')

    if type(document) is list:
        util.debug(f" Finished. Got {len(document)} entries.")
        return document
    else:
        util.debug("")
        util.error(f"got unexpected parsing response type {type(document)}.")
    return None


# returns all errata for a specific RFC
def filter_errata(rfc: str, errata_list: list, patches: Optional[dict]) -> list:
    if errata_list is None:
        return []
    result = []
    for errata in errata_list:
        doc_id = errata["doc-id"]
        if doc_id == rfc.upper():
            if patches is not None:
                if doc_id in patches:
                    eid = str(errata["errata_id"])
                    if eid in patches[doc_id]:
                        for k, v in patches[doc_id][eid].items():
                            errata[k] = v
            result.append(errata)
    return result


# calculates a checksum for a given erratum. This will be used to determine if a manually created erratum
# annotation file is based on the same version of the very erratum.
def errata_checksum(eid: int, errata_list: list, patches: Optional[dict]) -> Optional[str]:
    if errata_list is not None:
        for errata in errata_list:
            if eid == errata["errata_id"]:
                doc_id = errata["doc-id"]
                if patches is not None:
                    if doc_id in patches:
                        if eid in patches[doc_id]:
                            for k, v in patches[doc_id][eid].items():
                                errata[k] = v
                return util.create_checksum(errata)
    return None


# returns an object of errata patches (if present in the filesystem).
# This will be used to fix obvious wrong data in errata data.
# If no errata.patch is used it can be necessary to eclipse the original erratum annotation file
# with a manually fixed version.
def get_patches(file_name: Optional[str] = "errata.patch") -> Optional[list]:
    total = 0
    patches = None
    if file_name is not None:
        for directory in util.config_directories():
            path = os.path.join(directory, file_name)
            if os.path.exists(path):
                util.debug("\nReading errata patch file... ", end="")
                with open(path, "r") as f:
                    patches = json.loads(f.read())
                    total += len(patches)
                util.debug(f"Read {total} patches.")
                return patches
    return patches
