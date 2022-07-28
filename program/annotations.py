import os
import sys
import re
import textwrap
from typing import Optional, List
from xml.dom.minidom import Element

import drafts       # get_draft_index, get_draft_status
import errata       # filter_errata, errata_checksum
import htmlfilter   # filter_html
import rfcindex     # read_xml_document, fetch_element, referenced_document_ids
import util         # filtered_files, correct_path, replace_links_in_text, rewrite_rfc_anchor

''' Get and output the annotations for RFC annotations tools '''


def special_annotation_types() -> List[str]:
    return ["obsoleted", "potentially_obsoleted", "updated", "potentially_updated", "has_errata"]


def get_annotations(rfc: str, directories: str, errata_list: list, patches: dict, rfc_list: Optional[list]) -> list:

    def create_sort_key(d: dict) -> str:
        if "type" in d:
            order = special_annotation_types()
            s = d["type"]
            if s in order:
                return str(order.index(s))
            else:
                return s
        return "~"  # a key which will be added last

    ret = []
    for directory in directories.split(","):
        ret.extend(get_annotations_from_dir(rfc, directory.strip(), errata_list, patches, rfc_list))
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
    if len(edited_errata_ids) > 0 and len(candidates) > 0:
        for annotation in candidates:
            if annotation["errata_id"] in edited_errata_ids:
                annotation["eclipsed"] = True
    return ret


def get_annotation_from_file(path: str, errata_list: list, patches: dict, rfc_list: Optional[list] = None) -> [dict]:

    def check_errata_status(annotation: dict) -> dict:
        # check whether the current annotation is based on an outdated erratum version
        if "errata_id" in annotation:
            current_checksum: str = annotation["checksum"] if "checksum" in annotation else ""
            expected_checksum = errata.errata_checksum(int(annotation["errata_id"]), errata_list, patches)
            if current_checksum != expected_checksum:
                annotation["outdated"] = True
        return annotation

    ret = []
    with open(path, "r") as f:
        lines = f.readlines()
        notes = []
        entry = {"section": "global", "path": path}
        is_plain_text = False
        for line in lines:
            if line.strip() == "####################":
                # a new annotation entry starts here
                if is_plain_text:
                    notes.append("</pre>")
                else:
                    notes = htmlfilter.filter_html(notes, path=path)
                entry["notes"] = notes
                ret.append(check_errata_status(entry))
                notes = []
                entry = entry.copy()
                del entry["notes"]
                entry["section"] = "global"
                is_plain_text = False
            elif line.strip() == "#" or line.startswith("# "):
                # it's a comment
                pass
            elif line.startswith("#") and line[1].isalpha():
                # this line contains metadata
                tag = line[1].upper()
                s = None if len(line) <= 2 else line[2:].strip()
                if tag == "A":
                    entry["submitter_name"] = s
                elif tag == "C":
                    entry["caption"] = s
                elif tag == "D":
                    entry["date"] = s
                elif tag == "F":
                    entry["section"] = "fragment-" + s
                elif tag == "L":
                    entry["section"] = "line-" + s
                elif tag == "S":
                    entry["section"] = "global" if s == "99" or s.lower() == "none" else s.lower().strip()
                elif tag == "T":
                    entry["type"] = s
                elif tag == "X":
                    items = s.split(":", maxsplit=2)
                    if len(items) == 2:
                        entry[items[0]] = items[1]
            else:
                if len(notes) == 0:
                    # it's the first line, check whether we have plain text or a html fragment
                    search_result = re.search("<[a-z]*[a-z]+[ />]", line.strip())
                    pos = None if search_result is None else search_result.span()[0]
                    if pos is None or pos > 0:
                        is_plain_text = True
                        notes.append("<pre>")
                if is_plain_text:
                    line = util.replace_links_in_text(line, True)
                line = util.rewrite_rfc_anchor(line, rfc_list)
                notes.append(line)
        if is_plain_text:
            notes.append("\n</pre>")
        else:
            notes = htmlfilter.filter_html(notes, path=path)
        entry["notes"] = notes
        if len(notes) > 0:
            ret.append(check_errata_status(entry))
        else:
            print(f"\n   Error: {path} has invalid format.", file=sys.stderr)
    return ret


def get_annotations_from_dir(rfc: str, directory: str, errata_list: list, patches: dict,
                             rfc_list: Optional[list] = None) -> list:
    ret = []
    # Do not fetch annotations if the directory is called ".git"
    if os.path.basename(directory) == ".git":
        return ret
    # Do not fetch annotations if there is a file called ".ignore"
    if os.path.exists(os.path.join(directory, ".ignore")):
        return ret
    # Normal processing
    print(f"Fetching annotations for {rfc} in '{directory}'... ", end="")
    current = 0
    try:
        for file in util.filtered_files(directory, rfc + "."):
            path = os.path.join(directory, file)
            annotations_in_dir = get_annotation_from_file(path, errata_list, patches, rfc_list)
            ret.extend(annotations_in_dir)
            current += len(annotations_in_dir)
        print(f" Found {current}.")
        for subdir in os.scandir(directory):
            if subdir.is_dir():
                ret.extend(get_annotations_from_dir(rfc, subdir.path, errata_list, patches, rfc_list))
    except FileNotFoundError:
        print(f"\n   Error: Directory '{directory}' does not exist.", file=sys.stderr)
        pass
    return ret


def create_status_annotations(rfc_nr: str, rfc_list: list, root: Element, draft_index: Optional[dict],
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
                    status = draft_status[rfc.lower()].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    entry = f"{entry} ({status})"
            elif entry_type == "e":
                target = entry if count == 0 else f"https://www.rfc-editor.org/errata/eid{entry}"
                entry = "errata" if count == 0 else f"#{entry}"
            else:
                target = f"rfc{rfc}.html" if rfc in rfc_list else f"https://datatracker.ietf.org/doc/rfc{rfc}/"
                entry = f"RFC{rfc}"
            s += f'<a target="_blank" href="{target}">{entry}</a>'
            count += 1
        return caption, f"{prefix}{s}", line

    ret = []
    rfc_nr = rfc_nr.upper()
    if not rfc_nr.startswith("RFC"):
        rfc_nr = f"RFC{rfc_nr}"
    node = rfcindex.fetch_element(root, "rfc-entry", rfc_nr)
    if node is None:
        print(f"{rfc_nr} not found in index:-(", file=sys.stderr)
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
            ret.append(create_entry("POTENTIALLY OBSOLETED", "Potentially obsoleted by ",
                                    draft_index["obsoleted"][rfc_nr], 1, "d"))
        if "updated" in draft_index and rfc_nr in draft_index["updated"]:
            ret.append(create_entry("POTENTIALLY UPDATED", "Potentially updated by ",
                                    draft_index["updated"][rfc_nr], 2, "d"))
    return ret


def create_from_status(rfc_list: list, annotation_directory: str, read_directory: str = ".",
                       errata_list: Optional[list] = None, patches=None):
    read_directory = util.correct_path(read_directory)
    response = rfcindex.read_xml_document(read_directory)
    if response is None:
        print("   Error: can't read RFC index")
        return
    draft_index = drafts.get_draft_index(read_directory)
    draft_status = drafts.get_draft_status(read_directory)

    root: Optional[Element] = response.firstChild
    print("Creating status annotations... ", end="")
    has_skipped_files = False
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        for caption, notes, line in create_status_annotations(rfc, rfc_list, root, draft_index, errata_list, patches,
                                                              draft_status):
            annotation_type = caption.replace(' ', '_').lower()
            local_name = f"{rfc}.{annotation_type}"
            fn = os.path.join(annotation_directory, local_name)
            if os.path.exists(fn):
                if has_skipped_files:
                    print(f", {local_name}", end="")
                else:
                    print(f"\n   Files exist and will be skipped: {local_name}", end="")
                    has_skipped_files = True
            else:
                with open(fn, "w") as f:
                    f.write(f"#A\n#C {caption}\n#T {annotation_type}\n#\n#\n<div>{notes}</div>\n\n")
    print(".\n" if has_skipped_files else "Done.")


def create_from_errata(rfc_list: list, annotation_directory: str, errata_list: Optional[list] = None, patches=None):

    def patch_urls(text: str) -> str:
        return text.replace("<", "<&shy;")

    print("Creating errata annotations... ", end="")
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
                    print(f", {local_name}", end="")
                else:
                    print(f"\n   Files exist and will be skipped: {local_name}", end="")
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
    print(".\n" if has_skipped_files else "Done.")
