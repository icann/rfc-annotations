import os
import hashlib
import re
from typing import Optional


''' Utility functions for RFC repository tools '''


def correct_path(directory: str) -> str:
    if directory is None or len(directory) == 0:
        directory = "."
    if not directory.endswith("/"):
        directory += "/"
    return directory


def get_from_environment(name: str, default):
    if not name.startswith("RFC_"):
        name = "RFC_" + name
    return os.environ[name] if name in os.environ else default


def filtered_files(directory: str, prefix: str = "", suffix: str = "") -> list:
    ret = []
    for file in os.listdir(directory):
        if file.startswith(prefix) and file.endswith(suffix):
            ret.append(file)
    return ret


def create_checksum(d: dict) -> str:
    s: str = ""
    for key in sorted(d.keys()):
        val = d[key]
        if len(s) > 0:
            s += "\n"
        s += f"{key}={val}"
    return hashlib.md5(bytes(s, "utf-8")).hexdigest()


def replace_links_in_text(line: str, replace_special_chars: bool) -> str:
    start = "<"
    end = ">"
    if replace_special_chars:
        start = "&lt;"
        end = "&gt;"
        line = line.replace("&", "&amp;").replace("<", start).replace(">", end)

    stop = False
    while not stop:
        candidates = re.finditer(start + "http(s*)://([^/?#]*)?([^?#]*)(\\?([^#]*))?(#(.*))?" + end, line)
        stop = True
        if candidates is not None:
            for search_result in candidates:
                groups = search_result.groups()
                if groups is not None and len(groups) >= 7 and groups[0] is not None:
                    href = search_result.group()[len(start):-len(end)]
                    if end in href:
                        #  if there are multiple links in the same line we have to split the result
                        href = href[0:href.index(end)]
                        stop = False
                    search_fragment = f"{start}{href}{end}"
                    line = line.replace(search_fragment, f'<a target="_blank" href="{href}">{href}</a>')
    return line


def rewrite_rfc_anchor(line: str, rfc_list: Optional[list]) -> str:
    candidates = re.finditer(r"@{2}RFC\d+@{2}", line)
    if candidates is not None:
        for search_result in candidates:
            groups = search_result.groups()
            if groups is not None:
                rfc_nr = search_result.group()[5:-2]
                target = f"./rfc{rfc_nr}" if rfc_list is not None and rfc_nr in rfc_list\
                    else f"https://datatracker.ietf.org/doc/rfc{rfc_nr}/"
                line = line.replace(f"@@RFC{rfc_nr}@@", f'<a target="_blank" href="{target}.html">RFC{rfc_nr}</a>')
    return line


def means_false(s: str) -> bool:
    return s.lower() in ["0", "no", "false", "off", "disabled", "never"]


def means_true(s: str) -> bool:
    return not means_false(s)
