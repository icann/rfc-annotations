import os
import hashlib
import re
from typing import Optional


''' Utility functions for RFC annotations tools '''


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
    if os.path.exists(directory):
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

    def get_target(rfc: str) -> str:
        return f"./rfc{rfc}" if rfc_list is not None and rfc in rfc_list \
            else f"https://datatracker.ietf.org/doc/rfc{rfc}/"

    def get_target_with_id(dest: str, typ: str, entry: str) -> str:
        parts = dest[len(typ):].strip().split(" ")
        if len(parts) > 1:
            s = parts[0]
            for item in parts:
                if item.startswith("RFC"):
                    h = get_target(item[3:])
                    conv = entry.replace(f"@@{dest}@@", f"<a target='_blank' href='{h}.html#{typ}-{s}'>{dest}</a>")
                    return rewrite_rfc_anchor(conv, rfc_list)
        return entry

    if "@@" in line:
        start = line.index("@@")
        split = line[start + 2:]
        if "@@" in split:
            end = split.index("@@")
            target = split[0:end]
            if target.startswith("RFC"):
                nr = target[3:]
                items = nr.split(":", maxsplit=2)
                href_suffix = ""
                if len(items) == 1:
                    href = get_target(nr)
                else:
                    href = get_target(items[0])
                    href_suffix = "#" + items[1]
                line = line.replace(f"@@RFC{nr}@@", f"<a target='_blank' href='{href}.html{href_suffix}'>RFC{nr}</a>")
                return rewrite_rfc_anchor(line, rfc_list)
            elif target.lower().startswith("section"):
                return get_target_with_id(target, "section", line)
            elif target.lower().startswith("line"):
                return get_target_with_id(target, "line", line)
        return line[0:start + 2] + rewrite_rfc_anchor(split, rfc_list)
    return line


def rewrite_rfc_anchors(lines: [str], rfc_list: Optional[list]) -> [str]:
    ret = []
    for line in lines:
        ret.append(rewrite_rfc_anchor(line, rfc_list))
    return ret


def means_false(s: str) -> bool:
    return s.lower() in ["0", "no", "false", "off", "disabled", "never"]


def means_true(s: str) -> bool:
    return not means_false(s)
