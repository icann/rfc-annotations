import json
import os
import sys
from typing import Optional
from urllib.request import urlopen

import util  # correct_path

''' Create errata for RFC repository tools '''


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
        print(f"\nFetching errata from source of truth {url}... ", end='')
        try:
            json_content = urlopen(url).read()
            if type(json_content) is bytes:
                print(f"Retrieved {len(json_content)} bytes of data. Parsing...", end='')
                with open(file_path, "wb") as f:
                    f.write(json_content)
                    document = json.loads(json_content)
            else:
                print(f"\n   Error: got unexpected fetching response data of type {type(json_content)}.",
                      file=sys.stderr)
        except Exception as e:
            print(f"\n   Error: returned with error: {e}.", file=sys.stderr)
    else:
        print("\nParsing cached errata.json...", end='')

    if type(document) is list:
        print(f" Finished. Got {len(document)} entries.")
        return document
    else:
        print(f"\n   Error: got unexpected parsing response type {type(document)}.", file=sys.stderr)
    return None


def filter_errata(rfc: str, errata_list: list, patches: dict) -> list:
    if errata_list is None:
        return []
    result = []
    for errata in errata_list:
        doc_id = errata["doc-id"]
        if doc_id == rfc.upper():
            if doc_id in patches:
                eid = str(errata["errata_id"])
                if eid in patches[doc_id]:
                    for k, v in patches[doc_id][eid].items():
                        errata[k] = v
            result.append(errata)
    return result


def errata_checksum(eid: int, errata_list: list, patches: dict) -> Optional[str]:
    if errata_list is not None:
        for errata in errata_list:
            if eid == errata["errata_id"]:
                doc_id = errata["doc-id"]
                if doc_id in patches:
                    if eid in patches[doc_id]:
                        for k, v in patches[doc_id][eid].items():
                            errata[k] = v
                return util.create_checksum(errata)
    return None


def get_patches(path: str = "errata.patch"):
    print("\nReading errata patch file... ", end="")
    total = 0
    with open(path, "r") as f:
        patches = json.loads(f.read())
        total += len(patches)
    print(f"Read {total} patches.")
    return patches


def write_errata(rfc_list: list, errata_list: list, patches, directory: str = "."):
    if errata_list is None:
        return
    directory = util.correct_path(directory)
    print(f"\nWriting errata for {len(rfc_list)} RFC documents to '{directory}':")
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        filename = directory + rfc + ".err"
        print(f"Calculating {rfc.ljust(7)} errata...", end='')
        with open(filename, "w") as f:
            result = filter_errata(rfc, errata_list, patches)
            f.write(json.dumps(result))
            print(f"wrote {len(result)} errata entries.")
