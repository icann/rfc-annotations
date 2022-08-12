import json
import os
import subprocess
import sys
from typing import Optional
from urllib.request import urlopen
from xml.dom.minidom import Document, parseString, Element

import util  # filtered_files

''' Read and process Internet Drafts for RFC annotations tools '''


INDEX_FILE = "draft-index.json"


# ensures an up-to-date state of the locally stored internet-drafts. Needs to call rsync.
def download_drafts(target_dir: str = ".") -> Optional[dict]:
    drafts_dir = os.path.join(target_dir, "drafts")
    print("\nCalculating number of drafts to be fetched... ", end="")
    rsync_filter = '--include="draft*.xml" --include="draft-*.txt" --exclude="*" --delete'
    lines = subprocess.check_output(f'rsync -an --stats {rsync_filter} rsync.ietf.org::internet-drafts {drafts_dir}',
                                    shell=True).decode("utf-8").split("\n")
    nr = -1
    for line in lines:
        if line.startswith("Number of created files") or line.startswith("Number of deleted files") \
                or line.startswith("Number of regular files"):
            if nr < 0:
                nr = 0
            nr += int(line.split(": ")[1].split("(")[0].replace(",", "").replace(".", ""))
    if nr == 0:
        print("Already up to date")
        return get_draft_index(target_dir)
    if nr < 0:
        print("Retrieving unknown number of changes with rsync.")
    else:
        print(f"Retrieving {nr} changes with rsync.")
    subprocess.run(f'rsync -avz {rsync_filter} rsync.ietf.org::internet-drafts {drafts_dir}', shell=True)
    print("Finished rsync.")
    return __create_index(target_dir)


# returns (and creates automatically if not present) a local index file containing the current state of the
# downloaded drafts.
def get_draft_index(directory: str) -> Optional[dict]:
    try:
        with open(os.path.join(directory, INDEX_FILE), "r") as f:
            return json.loads(f.read())
    except Exception as e:
        print(f"   Error? {e} loading {INDEX_FILE}. Will create index again...", file=sys.stderr)
    return __create_index(directory)


# returns a dictionary containing status information for all drafts, will be automatically created, if absent
# and stored in the file system
def get_draft_status(directory: str, url: str = "https://www.ietf.org/id/all_id.txt") -> Optional[dict]:
    drafts_dir = os.path.join(directory, "drafts")
    file_path = os.path.join(drafts_dir, "status.json")
    document: Optional[dict] = None
    # noinspection PyBroadException
    try:
        with open(file_path, "r") as f:
            document = json.loads(f.read())
    except Exception:
        pass

    if document is None:
        print(f"\nFetching draft status from source of truth {url}... ", end='')
        try:
            text_content = urlopen(url).read().decode('utf-8')
            print(f"Retrieved {len(text_content)} chars of data. Parsing and converting...", end='')
            document = {}
            for entry in text_content.split("\n"):
                items = entry.rstrip().split("\t", maxsplit=2)
                if len(items) == 3 and len(items[0]) > 3:
                    document[items[0]] = items[2]
            with open(file_path, "w") as f:
                f.write(json.dumps(document))
        except Exception as e:
            print(f"\n   Error: returned with error: {e}.", file=sys.stderr)
    else:
        print("\nParsing cached status.json...", end='')
    return document


# recreates the index file used for faster access of draft details
def __create_index(directory: str) -> Optional[dict]:

    def add_to_list(d: dict, name: str, s: str):
        if len(s.strip()) > 0:
            for rfc in s.strip().split(","):
                rfc = rfc.strip()
                if rfc in d:
                    l: list = d[rfc]
                    l.append(name)
                    d[rfc] = l
                else:
                    d[rfc] = [name]

    def add_element_to_list(d: dict, name: str, attribute: str, element: Element):
        if attribute in element.attributes:
            add_to_list(d, name, element.attributes[attribute].firstChild.data)

    obsoleted_by = {}
    updated_by = {}
    handled = []
    drafts_dir = os.path.join(directory, "drafts")
    print("Creating index for drafts in xml format... ", end="")
    try:
        for file in util.filtered_files(drafts_dir, "draft-", ".xml"):
            with open(os.path.join(drafts_dir, file), "rb") as f:
                xml_content = f.read()
                document = parseString(xml_content)
                if type(document) is Document:
                    doc: Document = document
                    root = doc.getElementsByTagName("rfc")
                    if len(root) == 1:
                        draft_name = root[0].attributes["docName"].firstChild.data
                        handled.append(draft_name)
                        add_element_to_list(obsoleted_by, draft_name, "obsoletes", root[0])
                        add_element_to_list(updated_by, draft_name, "updates", root[0])
    except Exception as e:
        print(f"\n   Error reading xml in {drafts_dir}: {e}", file=sys.stderr)
    print("Done.")

    print("Creating index for drafts in txt format... ", end="")
    try:
        for file in util.filtered_files(drafts_dir, "draft-", ".txt"):
            if not file[:-4] in handled:
                with open(os.path.join(drafts_dir, file), "r") as f:
                    for line in f.readlines(2048):
                        if line.startswith("Updates: "):
                            add_to_list(updated_by, file[:-4], line[8:].split("  ")[0].split("(")[0].strip())
                        if line.startswith("Obsoletes: "):
                            add_to_list(obsoleted_by, file[:-4], line[11:].split("  ")[0].split("(")[0].strip())
    except Exception as e:
        print(f"\n   Error reading text in {drafts_dir}: {e}", file=sys.stderr)
    print("Done.\n")
    result = {"obsoleted": obsoleted_by, "updated": updated_by}
    with open(os.path.join(directory, INDEX_FILE), "w") as f:
        f.write(json.dumps(result))
    return result
