import os
import hashlib
import re
import sys
from typing import Optional

''' Utility functions for RFC annotations tools '''

_running_in_test = False
verbose_output = False


def debug(s: str, end='\n'):
    if verbose_output:
        print(s, end=end)


def info(s: str, end='\n'):
    print(s, end=end)


def warn(s: str):
    print(f"\n   Warning: {s}", file=sys.stderr)


def error(s: str):
    print(f"\n   Error: {s}", file=sys.stderr)


def is_valid_date_string(s: str) -> bool:
    return len(s) == 10 and re.match(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", s) is not None


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


def create_anchor(href_target: str, text: str, suffix: str = "", prefix: str = "", attributes: Optional[dict] = None) \
        -> str:
    extra = "" if href_target.startswith("#") else "target='_blank' "
    if attributes is not None:
        for name, val in attributes.items():
            if name != "target":
                extra += f"{name}='{val}' "
    return f"{prefix}<a {extra}href='{href_target}'>{text}</a>{suffix}"


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
            fmt1 = r"^(?P<sectionstring>(?P<sectiontype>Section|Appendix|Line)\s*(?P<sectionno>[0-9A-Z\.]+))"\
                   "(?P<fill1>\s*(of|in)\s*\[?)(?P<docstring>RFC\s*(?P<docno>[0-9]+))(?P<fill2>\]?)$"
            fmt2 = r"^(?P<fill1>\[?)(?P<docstring>RFC\s*(?P<docno>[0-9]+))(?P<fill2>\]?,?\s*)(?P<sectionstring>"\
                   "(?P<sectiontype>Section|Appendix|Line)\s*(?P<sectionno>[0-9A-Z\.]+))$"
            fmt3 = r"^(?P<fill1>\[?)(?P<docstring>RFC\s*(?P<docno>[0-9]+))(?P<fill2>]?)$"
            fmt4 = r"^(?P<sectionstring>(?P<sectiontype>Section|Appendix|Line)\s*(?P<sectionno>[0-9A-Z\.]+))$"

            replacement = None
            match = re.search(fmt1, target_text, flags=re.IGNORECASE)
            if match is not None:
                target_rfc = match.group("docno")
                target_section = get_reference_type(match.group("sectiontype")) + "-" + match.group("sectionno")
                a1 = create_anchor(get_rfc_target(target_rfc, rfc_list, target_section), match.group("sectionstring"),
                                   match.group("fill1"))
                a2 = create_anchor(get_rfc_target(target_rfc, rfc_list), match.group("docstring"), match.group("fill2"))
                replacement = f"{a1}{a2}"
            else:
                match = re.search(fmt2, target_text, flags=re.IGNORECASE)
                if match is not None:
                    target_rfc = match.group("docno")
                    target_section = get_reference_type(match.group("sectiontype")) + "-" + match.group("sectionno")
                    a1 = create_anchor(get_rfc_target(target_rfc, rfc_list, target_section),
                                       match.group("sectionstring") )
                    a2 = create_anchor(get_rfc_target(target_rfc, rfc_list), match.group("docstring"),
                                       match.group("fill2"), match.group("fill1"))
                    replacement = f"{a2}{a1}"
                else:
                    match = re.search(fmt3, target_text, flags=re.IGNORECASE)
                    if match is not None:
                        target_rfc = match.group("docno")
                        replacement = create_anchor(get_rfc_target(target_rfc, rfc_list),
                                                    match.group("docstring"), match.group("fill2"),
                                                    match.group("fill1"))
                    else:
                        match = re.search(fmt4, target_text, flags=re.IGNORECASE)
                        if match is not None:
                            target_section = get_reference_type(match.group("sectiontype")) + "-" + \
                                             match.group("sectionno")
                            contents = match.group("sectionstring")
                            replacement = create_anchor("#" + target_section, contents)

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
