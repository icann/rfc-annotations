import json
import os
import subprocess
from typing import Optional
from xml.dom.minidom import Document, parseString, Element

import util  # filtered_files, debug, info, error, urlopen

''' Read and process Internet Drafts for RFC annotations tools '''


INDEX_FILE = "draft-index.json"


# ensures an up-to-date state of the locally stored internet-drafts. Needs to call rsync.
def download_drafts(target_dir: str = ".") -> Optional[dict]:
    drafts_dir = os.path.join(target_dir, "drafts")
    util.info("\nCalculating number of drafts to be fetched... ", end="")
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
        util.info("Already up to date")
        return get_draft_index(target_dir)
    if nr < 0:
        util.info("Retrieving unknown number of changes with rsync.")
    else:
        util.info(f"Retrieving {nr} changes with rsync.")
    subprocess.run(f'rsync -avz {rsync_filter} rsync.ietf.org::internet-drafts {drafts_dir}', shell=True)
    util.info("Finished rsync.")

    # remove cached status information, if present
    file_path = os.path.join(drafts_dir, "status.json")
    if os.path.exists(file_path):
        os.remove(file_path)

    return __create_index(target_dir)


# returns (and creates automatically if not present) a local index file containing the current state of the
# downloaded drafts.
def get_draft_index(directory: str) -> Optional[dict]:
    try:
        with open(os.path.join(directory, INDEX_FILE), "r") as f:
            return json.loads(f.read())
    except Exception as e:
        util.error(f"{e} loading {INDEX_FILE}. Will create index again...")
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
            key = list(document.keys())[0]
            val = document[key]
            if type(val) == str:
                util.info(f"Converting 'status.json' to new format.")
                document = None
    except Exception:
        pass

    if document is None:
        util.info(f"\nFetching draft status from source of truth {url}... ", end='')
        try:
            text_content = util.urlopen(url).read().decode('utf-8')
            util.info(f"Retrieved {len(text_content)} chars of data. Parsing and converting...", end='')
            document = {}
            for entry in text_content.split("\n"):
                items = entry.rstrip().split("\t", maxsplit=2)
                if len(items) == 3 and len(items[0]) > 3:
                    draft_name = items[0]
                    date = items[1]
                    state = items[2].replace("\t", "")
                    if not util.is_valid_date_string(date):
                        util.warn(f"can't analyze date '{date}' of draft {draft_name}")
                    document[draft_name] = {"state": state, "date": date}
            with open(file_path, "w") as f:
                f.write(json.dumps(document))
            util.info(" Done.")
        except Exception as e:
            util.error(f"returned with error: {e}.")
    else:
        util.debug("\nUsing cached status.json.")
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
    util.debug("Creating index for drafts in xml format... ", end="")
    for file in util.filtered_files(drafts_dir, "draft-", ".xml"):
        file_name = os.path.join(drafts_dir, file)
        try:
            with open(file_name, "rb") as f:
                xml_content = f.read()
                document = parseString(xml_content)
                if type(document) is Document:
                    doc: Document = document
                    root = doc.getElementsByTagName("rfc")
                    if len(root) == 1:
                        draft_name = root[0].attributes["docName"].firstChild.data
                        add_element_to_list(obsoleted_by, draft_name, "obsoletes", root[0])
                        add_element_to_list(updated_by, draft_name, "updates", root[0])
                        handled.append(draft_name)
        except Exception as e:
            util.warn(f"reading xml file {file_name}: {e}. The corresponding txt file be used instead.")
        util.debug("Done.")

    util.debug("Creating index for drafts in txt format... ", end="")
    try:
        for file in util.filtered_files(drafts_dir, "draft-", ".txt"):
            if not file[:-4] in handled:
                with open(os.path.join(drafts_dir, file), "r") as f:
                    for line in f.readlines(2048):
                        if line.startswith("Updates: "):
                            add_to_list(updated_by, file[:-4], line[8:].split("  ")[0].split("(")[0].strip())
                        if line.startswith("Obsoletes: "):
                            add_to_list(obsoleted_by, file[:-4], line[11:].split("  ")[0].split("(")[0].strip())
        util.debug("Done.")
    except Exception as e:
        util.error(f"reading text in {drafts_dir}: {e}")

    result = {"obsoleted": obsoleted_by, "updated": updated_by}
    with open(os.path.join(directory, INDEX_FILE), "w") as f:
        f.write(json.dumps(result))
    return result
