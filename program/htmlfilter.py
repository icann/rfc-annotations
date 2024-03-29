import json
import os
from html.parser import HTMLParser
from typing import Optional

import util         # replace_links_in_text, means_true, get_from_environment, warn, error


''' Parse HTML for RFC annotations tools '''

html_restrictions: Optional[dict] = None


# event based implementation of an HTMLParser filtering forbidden elements and attributes.
class __MyHTMLParser(HTMLParser):

    def __init__(self, restrictions: dict, path: str):
        super().__init__()
        self.skip_until: Optional[str] = None
        self.path = path
        self.result = ""
        self.removed = ""
        self.open_tags = []
        self.forbidden_attribute_names: [str] = []
        self.forbidden_attribute_prefixes: [str] = []
        self.allowed_tag_names: [str] = []
        self.tag_stack: [str] = []

        a: str
        for a in restrictions["forbidden-attributes"]:
            if a.endswith("*"):
                if a[:-1] not in self.forbidden_attribute_prefixes:
                    self.forbidden_attribute_prefixes.append(a[:-1])
            else:
                if a not in self.forbidden_attribute_names:
                    self.forbidden_attribute_names.append(a)
        for a in restrictions["allowed"]:
            self.allowed_tag_names.append(a)
        self.allowed_children_names = restrictions["allowed-children"] if "allowed-children" in restrictions else {}
        self.uri_filter: [dict] = restrictions["uri-filter"] if "uri-filter" in restrictions else []

    def handle_starttag(self, tag, attrs):
        current_attributes = {}
        self.tag_stack.append(tag)
        s = f"<{tag}"
        key: str
        for (key, value) in attrs:
            ok = key.lower() not in self.forbidden_attribute_names
            if ok:
                for a in self.forbidden_attribute_prefixes:
                    if key.startswith(a):
                        ok = False
                        break
            if ok:
                for entry in self.uri_filter:
                    if "attributes" in entry and (key in entry["attributes"] or f"{tag}:{key}" in entry["attributes"]):
                        if ":" in value:  # do we have a scheme?
                            scheme = value.split(":")[0]
                            if "allowed-schemes" in entry and len(entry["allowed-schemes"]) > 0:
                                if scheme.lower() not in entry["allowed-schemes"]:
                                    util.error(f"scheme {scheme} is not allowed for attribute {key} in element {tag}"
                                               f" in file {self.path}")
                                    ok = False
                            else:
                                util.error(f"no schemes allowed for attribute {key}={value} in element {tag}"
                                           f" in file {self.path}")
                                ok = False
                if ok:
                    s += f" {key}='{value}'"
                    current_attributes[key] = value
            else:
                util.error(f"removing forbidden attribute {key} with value {value} in file {self.path}")
        if tag == "a" and "target" not in current_attributes and not current_attributes["href"].startswith("#"):
            s += " target='_blank'"
        s += ">"
        if self.skip_until is None:
            ok = tag.lower() in self.allowed_tag_names
            if not ok:
                if len(self.open_tags) > 0:
                    current = self.open_tags[len(self.open_tags) - 1]
                    if current in self.allowed_children_names:
                        ok = tag.lower() in self.allowed_children_names[current]
            if ok:
                self.result += s
                self.open_tags.append(tag)
            else:
                self.skip_until = tag
                self.removed = s
        else:
            self.removed += s

    def handle_endtag(self, tag):
        if len(self.tag_stack) == 0:
            util.error(f"Got end tag {tag} without any opened tags in file {self.path}")
        else:
            expected = self.tag_stack[len(self.tag_stack) - 1]
            if expected != tag:
                util.error(f"Got end tag {tag} but did expect {expected} in file {self.path}")
            else:
                self.tag_stack = self.tag_stack[:-1]

        s = f"</{tag}>"
        if self.skip_until is None:
            if self.result.endswith(f"<{tag}>"):
                self.result = self.result[:-1]
                self.result += "/>"
            else:
                self.result += s
            if len(self.open_tags) > 0:
                self.open_tags.pop()
        else:
            self.removed += s
            if tag == self.skip_until:
                self.skip_until = None
                util.error(f"stripped '{self.removed}' due to invalid start tag: {tag} in hierarchy {self.open_tags}"
                           f" in file {self.path}")
                self.removed = ""

    def handle_data(self, data):
        if self.skip_until is None:
            self.result += data
        else:
            self.removed += data


# helper method for (un-)escaping angle brackets in <pre>-sections
def __replace_between(s: str, section_start: str, section_end: str, replacements: dict,
                      preserve_attrs: bool = False) -> str:

    def filter_section(area: str) -> str:
        if len(area) == 0:
            return ""

        close_tag = "&amp;gt;"
        for key, replacement in replacements.items():
            if preserve_attrs:
                # add special closing tag handling here preserving all attributes!
                to_be_handled = area
                area = ""
                while key in to_be_handled:
                    tag_start = to_be_handled.index(key)
                    split = to_be_handled[tag_start + len(key):]
                    if close_tag in split:
                        tag_end = split.index(close_tag)
                        attributes = split[0:tag_end]
                        area += to_be_handled[0:tag_start]
                        if len(attributes) == 0 or attributes.startswith(" "):
                            area += replacement + attributes + ">"
                        else:
                            area += key + attributes + close_tag
                        to_be_handled = split[tag_end + 8:]
                area += to_be_handled
            else:
                area = area.replace(key, replacement)
        return area

    ret = s
    if section_start in s:
        start = s.index(section_start) + len(section_start)
        ret = s[0:start]
        s = s[start:]
        if section_end in s:
            end = s.index(section_end)
            ret = ret + filter_section(s[0:end]) + section_end
            end = end + len(section_end)
            if end < len(s):
                ret = ret + __replace_between(s[end:], section_start, section_end, replacements,
                                              preserve_attrs=preserve_attrs)
        else:
            ret = ret + s
    return ret


# filters the html fragments stored in an annotation file. It ensures that the restrictions stored in the
# html-restrictions.json (white and black list of element and child names and attributes) are fulfilled and
# proper (x)html is used.
def filter_html(lines: [str], file: Optional[str] = None, path: str = None) -> [str]:
    show_warnings = util.means_true(util.get_from_environment("HTML_WARNINGS", "0"))
    s = ""
    for line in lines:
        s += util.replace_links_in_text(line, False)
    global html_restrictions
    if html_restrictions is None:
        if file is None:
            file = os.path.join(os.path.dirname(__file__), "html-restrictions.json")

        # noinspection PyBroadException
        try:
            with open(file, "rb") as f:
                html_restrictions = json.loads(f.read())
        except Exception:
            if show_warnings:
                util.warn(f"Can't read {file} file! Output will be unfiltered!")

    if html_restrictions is None:
        return s
    parser = __MyHTMLParser(html_restrictions, path)
    for tag in ["br", "hr"]:
        s = s.replace(f"<{tag}>", f"<{tag}/>").replace(f"</{tag}>", "")

    # replaces all < and > characters inside a <pre></pre> section with an escaped version so that the html parser
    # does not try to handle these as html tags
    s = __replace_between(s, "<pre>", "</pre>", {"<": "&amp;lt;", ">": "&amp;gt;"})

    # fix the opening and closing tags for allowed html element names inside the <pre>-sections
    if "allowed" in html_restrictions:
        for tag in html_restrictions["allowed"]:
            s = __replace_between(s, "<pre>", "</pre>", {f"&amp;lt;{tag}": f"<{tag}", f"&amp;lt;/{tag}": f"</{tag}"},
                                  preserve_attrs=True)

    parser.feed(s)
    result = parser.result
    if len(parser.open_tags) > 0:
        filtered = []
        for tag in parser.open_tags:
            if tag != "p":
                filtered.append(tag)
        if len(filtered) > 0:
            if show_warnings:
                util.warn(f"Invalid HTML. Some tags are not closed properly: {filtered}. "
                          f"Adding closing tags to {path}.")
            suffix = ""
            for tag in filtered:
                suffix = f"</{tag}>{suffix}"
            result += suffix
    return [result]
