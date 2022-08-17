import os
import hashlib
import re
from typing import Optional

''' Utility functions for RFC annotations tools '''

_running_in_test = False


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


def create_anchor(href_target: str, text: str, suffix: str = "", prefix: str = "") -> str:
    return f"{prefix}<a target='_blank' href='{href_target}'>{text}</a>{suffix}"


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
                    line = line.replace(search_fragment, create_anchor(href, href))
    return line


def get_rfc_target(rfc: str, rfc_list: Optional[list] = None, target_id: Optional[str] = None) -> str:
    if rfc_list is not None and rfc in rfc_list:
        if target_id is None:
            return f"./rfc{rfc}.html"
        else:
            return f"./rfc{rfc}.html#{target_id}"
    else:
        if target_id is None:
            return f"https://datatracker.ietf.org/doc/rfc{rfc}/"
        else:
            return f"https://datatracker.ietf.org/doc/html/rfc{rfc}.html#{target_id}"


def rewrite_rfc_anchor(line: str, rfc_list: Optional[list]) -> str:
    def get_reference_type(entity: str) -> str:
        return "section" if entity.lower() == "appendix" else entity.lower()

    if "@@" in line:
        start = line.index("@@")
        split = line[start + 2:]
        if "@@" in split:
            end = split.index("@@")
            target_text = split[0:end].strip()

            # find RFC number (and line or section reference) inside {target_text}
            replacement = None
            result = re.split(r"((Section|Appendix|Line)\s*([0-9A-Z.]+))(\s*(of|in)\s*\[?)(RFC\s*([0-9]+))(]?)",
                              target_text, flags=re.IGNORECASE)
            if len(result) > 8:
                target_rfc = result[7]
                target_section = get_reference_type(result[2]) + "-" + result[3]
                a1 = create_anchor(get_rfc_target(target_rfc, rfc_list, target_section), result[1], result[4])
                a2 = create_anchor(get_rfc_target(target_rfc, rfc_list), result[6], result[8])
                replacement = f"{a1}{a2}"
            else:
                result = re.split(r"(\[?)(RFC\s*([0-9]+))(]?,\s*)((Section|Appendix|Line)\s*([0-9A-Z.]+))", target_text,
                                  flags=re.IGNORECASE)
                if len(result) > 7:
                    target_rfc = result[3]
                    target_section = get_reference_type(result[6]) + "-" + result[7]
                    a1 = create_anchor(get_rfc_target(target_rfc, rfc_list), result[2], result[4], result[1])
                    a2 = create_anchor(get_rfc_target(target_rfc, rfc_list, target_section), result[5])
                    replacement = f"{a1}{a2}"
                else:
                    result = re.split(r"(\[?)(RFC\s*([0-9]+))(]?)", target_text, flags=re.IGNORECASE)
                    if len(result) > 4:
                        target_rfc = result[3]
                        replacement = create_anchor(get_rfc_target(target_rfc, rfc_list),
                                                    result[2], result[4], result[1])
            if replacement is not None:
                line = line.replace(f"@@{target_text}@@", replacement)
                return rewrite_rfc_anchor(line, rfc_list)
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


def config_directories() -> [str]:
    return ["default-config"] if _running_in_test else ["local-config", "default-config"]
