import os
import re
import textwrap
from typing import Optional, List
from datetime import datetime

import drafts       # get_draft_index, get_draft_status
import errata       # filter_errata, errata_checksum
import htmlfilter   # filter_html
import rfcindex     # read_xml_document, fetch_element, referenced_document_ids
import util         # filtered_files, correct_path, replace_links_in_text, rewrite_rfc_anchor, create_anchor

''' Get and output the annotations for RFC annotations tools '''


# defines the built-in annotation types and their order
def built_in_annotation_types() -> List[str]:
    return ["obsoleted", "potentially_obsoleted", "updated", "potentially_updated", "has_errata"]


# retrieves a filtered and sorted list of annotations based on errata for the specified RFC
def get_annotations(rfc: str, directories: Optional[str], errata_list: list, patches: Optional[dict],
                    rfc_list: Optional[list]) -> list:

    def create_sort_key(d: dict) -> str:
        if "type" in d:
            order = built_in_annotation_types()
            s = d["type"]
            if s in order:
                return str(order.index(s))
            else:
                return s
        return "~"  # a key which will be added last

    ret = []
    # search for annotations in the specified directories
    if directories is not None:
        for directory in directories.split(","):
            ret.extend(__get_annotations_from_dir(rfc, directory.strip(), errata_list, patches, rfc_list))

    # sort the annotations
    ret = sorted(ret, key=lambda d: create_sort_key(d))

    # search for duplicate/edited errata_ids
    edited_errata_ids = []
    candidates = []
    for annotation in ret:
        if "errata_id" in annotation and "path" in annotation:
            if os.path.sep + "_generated" + os.path.sep not in annotation["path"]:
                edited_errata_ids.append(annotation["errata_id"])
            else:
                candidates.append(annotation)

    # handle eclipsed errata
    if len(edited_errata_ids) > 0 and len(candidates) > 0:
        for annotation in candidates:
            if annotation["errata_id"] in edited_errata_ids:
                # we do not support eclipsed annotations anymore, there will be removed!
                # annotation["eclipsed"] = True
                ret.remove(annotation)
    return ret


# converts an annotation text file into an array of dictionaries storing the annotation details
def get_annotation_from_file(path: str, errata_list: list, patches: Optional[dict],
                             rfc_list: Optional[list] = None) -> [dict]:

    def check_errata_status(annotation: dict) -> dict:
        # check whether the current annotation is based on an outdated erratum version
        if "errata_id" in annotation:
            current_checksum: str = annotation["checksum"] if "checksum" in annotation else ""
            expected_checksum = errata.errata_checksum(int(annotation["errata_id"]), errata_list, patches)
            if current_checksum != expected_checksum:
                annotation["outdated"] = True
        return annotation

    def apply(default_values: dict, to: dict) -> dict:
        for key in default_values.keys():
            if key not in to:
                to[key] = default_values[key]
        return to

    ret = []
    plain_text_enclosing_element = "p"
    with open(path, "r") as f:
        lines = f.readlines()
        notes = []
        entry = {}
        defaults = {"section": "global", "path": path}
        is_plain_text = False

        def save_current_annotation(ann_notes: list) -> list:
            if is_plain_text:
                ann_notes.append(f"</{plain_text_enclosing_element}>")
            else:
                ann_notes = util.rewrite_rfc_anchors(htmlfilter.filter_html(ann_notes, path=path), rfc_list)
            entry["notes"] = ann_notes
            return ann_notes

        for line in lines:
            if line.strip() == "####################":
                # a new annotation entry starts here
                save_current_annotation(notes)
                ret.append(check_errata_status(apply(default_values=defaults, to=entry)))
                notes = []
                defaults = entry.copy()
                del defaults["notes"]
                entry = {}
                is_plain_text = False
            elif line.strip() == "#" or line.startswith("# "):
                # it's a comment
                pass
            elif line.startswith("#") and line[1].isalpha():
                # this line contains metadata
                tag = line[1].upper()
                s = None if len(line) <= 2 else line[2:].strip()

                def set_in_dict(key: str, value: str, warn_if_present=True):
                    if warn_if_present and key in entry:
                        util.warn(f"a #{tag} line may exist only once per annotation ({path})")
                    else:
                        entry[key] = value

                if tag == "A":
                    set_in_dict(key="submitter_name", value=s)
                elif tag == "C":
                    set_in_dict(key="caption", value=s)
                elif tag == "D":
                    if util.is_valid_date_string(s):
                        set_in_dict(key="date", value=s)
                    else:
                        util.warn(f"File {path} contains invalid formatted date: {s}. Must use YYYY-MM-DD.")
                elif tag == "F":
                    set_in_dict(key="section", value=f"fragment-{s}", warn_if_present=False)
                elif tag == "L":
                    set_in_dict(key="section", value=f"line-{s}", warn_if_present=False)
                    # check whether the line reference may be unstable
                    try:
                        line_nr = int(s)
                        rfc_nr = int(os.path.basename(path).split(".")[0][3:])
                        if rfc_nr >= 8650 and line_nr > 1:
                            util.warn(f"File {path} contains reference to line#{s}. "
                                      "Line references for RFC8650 and newer may be unstable.")
                    except ValueError:
                        pass
                elif tag == "S":
                    set_in_dict(key="section", warn_if_present=False,
                                value="global" if s == "99" or s.lower() == "none" else s.lower().strip())
                elif tag == "T":
                    set_in_dict(key="type", value=s)
                elif tag == "X":
                    items = s.split(":", maxsplit=2)
                    if len(items) == 2:
                        set_in_dict(key=items[0], value=items[1])
            else:
                if len(notes) == 0:
                    # it's the first line, check whether we have plain text or a html fragment
                    search_result = re.search("<[a-z]*[a-z]+[ />]", line.strip())
                    pos = None if search_result is None else search_result.span()[0]
                    if pos is None or pos > 0:
                        is_plain_text = True
                        notes.append(f"<{plain_text_enclosing_element} class='plaintext'>")
                if is_plain_text:
                    line = util.rewrite_rfc_anchor(util.replace_links_in_text(line, True), rfc_list)
                notes.append(line)
        notes = save_current_annotation(notes)
        if len(notes) > 0:
            ret.append(check_errata_status(apply(default_values=defaults, to=entry)))
        else:
            util.error(f"{path} has invalid format.")
    return ret


# fetches recursively all annotation files for the desired RFC in the directory (and it's children)
def __get_annotations_from_dir(rfc: str, directory: str, errata_list: list, patches: Optional[dict],
                               rfc_list: Optional[list] = None) -> list:
    ret = []
    # Do not fetch annotations if the directory is called ".git"
    if os.path.basename(directory) == ".git":
        return ret
    # Do not fetch annotations if there is a file called ".ignore"
    if os.path.exists(os.path.join(directory, ".ignore")):
        return ret
    # Normal processing
    current = 0
    try:
        for file in util.filtered_files(directory, rfc + "."):
            path = os.path.join(directory, file)
            annotations_in_dir = get_annotation_from_file(path, errata_list, patches, rfc_list)
            ret.extend(annotations_in_dir)
            current += len(annotations_in_dir)
        if current > 0:
            util.debug(f"Found {str(current).rjust(2)} annotations {directory}. ")
        for subdir in os.scandir(directory):
            if subdir.is_dir():
                ret.extend(__get_annotations_from_dir(rfc, subdir.path, errata_list, patches, rfc_list))
    except FileNotFoundError:
        util.error(f"Directory '{directory}' does not exist.")
        pass
    return ret


# returns status information (like obsoleted, updated etc.) for a single RFC (based on the information of
# https://www.rfc-editor.org/rfc-index.xml). This information is used for the generation of annotation files.
def __create_status_annotations(rfc_nr: str, rfc_list: list, root: dict, draft_index: Optional[dict],
                                errata_list: Optional[list] = None, patches=None,
                                draft_status: Optional[dict] = None) -> list:

    def create_entry(caption: str, prefix: str, entries: list, line: int, entry_type: str = "") -> tuple:
        s: str = ""
        count = 0
        for entry in entries:
            rfc = entry.upper()
            if rfc.startswith("RFC"):
                rfc = rfc[3:]
            if len(s) > 0:
                if entry_type == "e" and count == 1:
                    s += ": \n"
                else:
                    s += ", \n"
            if entry_type == "d":
                if len(entry) > 3 and entry[-3] == "-":
                    entry = entry[:-3]
                else:
                    entry = f"search?sort=&rfcs=on&activedrafts=on&name={entry}"
                target = f"https://datatracker.ietf.org/doc/{entry}"
                if rfc.lower() in draft_status:
                    status = draft_status[rfc.lower()]["state"].replace("&", "&amp;")\
                        .replace("<", "&lt;").replace(">", "&gt;")
                    entry = f"{entry} ({status})"
            elif entry_type == "e":
                target = entry if count == 0 else f"https://www.rfc-editor.org/errata/eid{entry}"
                entry = "errata" if count == 0 else f"#{entry}"
            else:
                target = util.get_rfc_target(rfc, rfc_list)
                entry = f"RFC{rfc}"
            s += util.create_anchor(href=target, text=entry)
            count += 1
        return caption, f"{prefix}{s}", line

    def filter_valid_drafts(draft_names: [str]) -> []:
        filtered_drafts = []
        for draft_name in draft_names:
            if draft_name in draft_status:
                state = draft_status[draft_name]["state"].lower()
                if state.startswith("rfc") or state.startswith("replaced") or state.startswith("withdrawn"):
                    util.warn(f"ignoring draft '{draft_name}' with state {state}")
                else:
                    if state.startswith("in iesg processing"):
                        filtered_drafts.append(draft_name)
                    elif state in ["active", "expired"]:
                        s = draft_status[draft_name]["date"]
                        delta = datetime.today() - datetime.strptime(s, "%Y-%m-%d")
                        if delta.days > 365:
                            util.info(f"\nWill skip draft '{draft_name}' because current state '{state}' is"
                                      f" too old ({s}).")
                        else:
                            filtered_drafts.append(draft_name)
                    else:
                        util.warn(f"\nUnknown state '{state}'. Skipping draft '{draft_name}'.")
            else:
                util.warn(f"\nCan't check state of draft '{draft_name}'. Will be skipped.")
        return filtered_drafts

    ret = []
    rfc_nr = rfc_nr.upper()
    if not rfc_nr.startswith("RFC"):
        rfc_nr = f"RFC{rfc_nr}"
    node = rfcindex.fetch_element(root, rfc_nr)
    if node is None:
        util.error(f"{rfc_nr} not found in index:-(")
    else:
        obsoleted_by = rfcindex.referenced_document_ids(node, "obsoleted-by")
        if len(obsoleted_by) > 0:
            ret.append(create_entry("OBSOLETED", "Obsoleted by ", obsoleted_by, 1))
        else:
            updated_by = rfcindex.referenced_document_ids(node, "updated-by")
            for candidate in rfc_list:
                if candidate in updated_by:
                    updated_by.remove(candidate)
            if len(updated_by) > 0:
                ret.append(create_entry("UPDATED", "Updated by ", updated_by, 2))
        errata_url = node.getElementsByTagName("errata-url")
        if len(errata_url) > 0:
            urls = []
            if errata_list is not None:
                for erratum in errata.filter_errata(rfc_nr, errata_list, patches):
                    urls.append(str(erratum["errata_id"]))
            urls = sorted(urls, key=lambda s: int(s))
            urls.insert(0, errata_url[0].firstChild.data)
            ret.append(create_entry("HAS ERRATA", "Has ", urls, 3, "e"))
    if draft_index is not None:
        if rfc_nr.upper().startswith("RFC"):
            rfc_nr = rfc_nr[3:]
        if "obsoleted" in draft_index and rfc_nr in draft_index["obsoleted"]:
            valid_drafts = filter_valid_drafts(draft_index["obsoleted"][rfc_nr])
            if len(valid_drafts) > 0:
                ret.append(create_entry("POTENTIALLY OBSOLETED", "Potentially obsoleted by ",
                                        valid_drafts, 1, "d"))
        if "updated" in draft_index and rfc_nr in draft_index["updated"]:
            valid_drafts = filter_valid_drafts(draft_index["updated"][rfc_nr])
            if len(valid_drafts) > 0:
                ret.append(create_entry("POTENTIALLY UPDATED", "Potentially updated by ",
                                        valid_drafts, 2, "d"))
    return ret


# creates annotation files containing the status of the RFCs (based on the information of
# https://www.rfc-editor.org/rfc-index.xml)
def create_from_status(rfc_list: list, annotation_directory: str, read_directory: str = ".",
                       errata_list: Optional[list] = None, patches=None):
    read_directory = util.correct_path(read_directory)
    _, lookup_map = rfcindex.read_xml_document(read_directory)
    if lookup_map is None:
        util.error("can't read RFC index")
        return
    draft_index = drafts.get_draft_index(read_directory)
    draft_status = drafts.get_draft_status(read_directory)

    util.info("Creating status annotations... ", end="")
    has_skipped_files = False
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        for caption, notes, line in __create_status_annotations(rfc, rfc_list, lookup_map, draft_index, errata_list,
                                                                patches, draft_status):
            annotation_type = caption.replace(' ', '_').lower()
            local_name = f"{rfc}.{annotation_type}"
            fn = os.path.join(annotation_directory, local_name)
            if os.path.exists(fn):
                if has_skipped_files:
                    util.debug(f", {local_name}", end="")
                else:
                    util.debug(f"\n   Files exist and will be skipped: {local_name}", end="")
                    has_skipped_files = True
            else:
                with open(fn, "w") as f:
                    f.write(f"#A\n#C {caption}\n#T {annotation_type}\n#\n#\n<div>{notes}</div>\n\n")
    if has_skipped_files:
        util.debug("")
    util.info("Done.")


# create annotation files based on the errata stored (https://www.rfc-editor.org/errata.json) for the desired RFCs.
def create_from_errata(rfc_list: list, annotation_directory: str, errata_list: Optional[list] = None, patches=None):

    def patch_urls(text: str) -> str:
        return text.replace("<", "<&shy;")

    util.info("Creating errata annotations... ", end="")
    has_skipped_files = False
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        for erratum in errata.filter_errata(rfc, errata_list, patches):
            eid = erratum["errata_id"]
            checksum = errata.errata_checksum(eid, errata_list, patches)
            local_name = f"{rfc}.erratum.{eid}"
            fn = os.path.join(annotation_directory, local_name)
            if os.path.exists(fn):
                if has_skipped_files:
                    util.debug(f", {local_name}", end="")
                else:
                    util.debug(f"\n   Files exist and will be skipped: {local_name}", end="")
                    has_skipped_files = True
            else:
                with open(fn, "w") as f:
                    author = erratum["submitter_name"] if "submitter_name" in erratum else ""
                    f.write(f"#A {author}\n")
                    if "section" in erratum:
                        entry = erratum["section"]
                        if type(entry) is list:
                            entry = entry[0]
                        entry = f"{entry}".lower()
                        if entry.startswith("line-"):
                            f.write(f"#L {entry[5:]}\n")
                        elif entry.startswith("fragment-"):
                            f.write(f"#F {entry[9:]}\n")
                        else:
                            f.write(f"#S {entry}\n")
                    if "errata_type_code" in erratum:
                        f.write(f"#T {erratum['errata_type_code']}\n")
                    f.write(f'#X errata_id:{eid}\n')
                    f.write(f'#X checksum:{checksum}\n')
                    if "errata_status_code" in erratum:
                        f.write(f'#X errata_status_code:{erratum["errata_status_code"]}\n')
                    f.write('#\n#\n')
                    text_added = False
                    if "orig_text" in erratum and erratum["orig_text"] is not None:
                        text_added = True
                        s = patch_urls(str(erratum["orig_text"]))
                        f.write(f'<div class="original"><pre>\n{s}\n</pre></div>\n')
                    if "correct_text" in erratum and erratum["correct_text"] is not None:
                        if text_added:
                            f.write("#\n#\n")
                        text_added = True
                        s = patch_urls(str(erratum["correct_text"]))
                        f.write(f'<div class="correct">It should say:<pre>\n{s}\n</pre></div>\n')
                    if "notes" in erratum and erratum["notes"] is not None:
                        s = str(erratum["notes"]).strip()
                        if s.endswith("from pending"):
                            s = s[:-12].rstrip()
                        if len(s) > 0:
                            if text_added:
                                f.write('#\n#\n<hr/>\n')
                            f.write('<div class="note"><pre>')
                            for paragraph in s.split("\n"):
                                for note_line in textwrap.wrap(paragraph, width=72, drop_whitespace=False):
                                    note_line = util.replace_links_in_text(note_line, True)
                                    f.write(f"\n{note_line.strip()}")
                            f.write('\n</pre></div>\n\n')
    if has_skipped_files:
        util.debug("")
    util.info("Done.")
