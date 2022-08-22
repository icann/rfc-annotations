import os.path
from typing import Optional

import annotations   # get_annotations, special_annotation_types
import htmlize_rfcs  # markup
import rfcindex      # read_xml_document, fetch_element
import util          # correct_path, get_from_environment, config_directories, create_anchor, debug, info, error

''' Create the new HTMLized RFCs for RFC annotations tools '''


# creates an index html page containing details and links to the given RFCs
def create_index(prefix: Optional[str], sections: [tuple], write_directory: str = ".", path: str = ".",
                 rfcs_last_updated: Optional[dict] = None):
    root = None
    response = rfcindex.read_xml_document(path)
    if response is not None:
        root = response.firstChild

    write_directory = util.correct_path(write_directory)
    file_name = "index.html" if prefix is None else f"{prefix}-index.html"
    util.info(f"Creating {file_name}...", end="")
    css = __read_html_fragments("css.html", util.get_from_environment("CSS", None))
    scripts = __read_html_fragments("index-scripts.html", util.get_from_environment("INDEX_SCRIPTS", None))
    try:
        with open(os.path.join(write_directory, file_name), "w") as f:
            title = 'Overview' if prefix is None else f'Overview of {prefix.upper()}-related RFCs'
            f.write(f'<!DOCTYPE html>\n<html lang="en" id="html">\n<head>\n<meta charset="UTF-8">'
                    f'<title>{title}</title>\n')
            if css is not None:
                f.write(f'{css}\n')
            if scripts is not None:
                f.write(f'{scripts}\n')
            f.write(f'</head>\n\n<body onload="makeTableSortable(\'table\', {len(sections)})">\n')
            if scripts is not None:
                f.write("<noscript>For full functionality of this page please enable JavaScript</noscript>\n")
            for nr, section in enumerate(sections):
                rfc_list, index_text = section
                f.write(f'{index_text}<table class="index" id="table{nr}">\n<thead><tr class="header">'
                        '<th class="rfc" data-type="int">RFC</th>')
                if root is not None:
                    f.write('<th class="title">Title</th>'
                            '<th class="date" data-type="month-year">Date</th>'
                            '<th class="status">Status</th>')
                if rfcs_last_updated is not None:
                    f.write('<th class="timestamp">Latest Ann.</th>')
                f.write("</tr></thead>\n<tbody>\n")
                odd = True
                for rfc in rfc_list:
                    rfc: str = rfc.lower().strip()
                    rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
                    node = None if root is None else rfcindex.fetch_element(root, rfc.upper())
                    f.write(f"<tr class='entry " + ("odd" if odd else "even") + "'>" +
                            util.create_anchor(rfc + ".html", rfc[3:], "</td>", "<td class='rfc'>"))
                    odd = not odd
                    if node is not None:
                        title = node.getElementsByTagName("title")[0].firstChild.data
                        status = node.getElementsByTagName("current-status")[0].firstChild.data.title()
                        month = node.getElementsByTagName("month")[0].firstChild.data
                        year = node.getElementsByTagName("year")[0].firstChild.data
                        date = f"{month} {year}".strip()
                        node_list = node.getElementsByTagName("obsoleted-by")
                        suffix = ""
                        if len(node_list) > 0:
                            for node in node_list[0].getElementsByTagName("doc-id"):
                                rfc = node.firstChild.data
                                suffix += "; Obsoleted by" if len(suffix) == 0 else ","
                                text = f"{rfc[0:3]} {rfc[3:]}" if len(rfc) > 3 else rfc
                                suffix += __rewrite_anchor(util.create_anchor(rfc.lower(), text, "", " "), rfc_list)
                        status = f"{status}{suffix}"
                        f.write(f"<td class='title'>{title}</td>"
                                f"<td class='date'>{date}</td>"
                                f"<td class='status'>{status}</td>")
                    if rfcs_last_updated is not None:
                        s = rfcs_last_updated[rfc] if rfc in rfcs_last_updated else ""
                        f.write(f'<td class="timestamp">{s}</td>')
                    f.write("</tr>\n")
                f.write("</tbody></table>\n")
            f.write("</body></html>")
            util.info(" Done.")
    except Exception as e:
        util.error(f"can't create index.html: {e}.")


def __rewrite_anchor(line: str, rfc_list: list) -> str:
    anchor_target = '<a href="./rfc'
    if anchor_target in line:
        fragments = line.split(anchor_target)
        for index in range(len(fragments)):
            if index == 0:
                line = fragments[index]
            else:
                s = fragments[index]
                rfc_nr = ""
                while s[0].isdigit():
                    rfc_nr += s[0]
                    s = s[1:]
                if rfc_nr in rfc_list:
                    line += anchor_target + rfc_nr + ".html"
                else:
                    line += '<a href="https://datatracker.ietf.org/doc/rfc' + rfc_nr + '/'
                line += s
    return line


# searches for a given filename in the different config directories and returns the first found version, if present
def __read_html_fragments(file: str, extra: Optional[str]) -> str:
    for directory in util.config_directories():
        file_name = os.path.join(directory, file)
        if os.path.exists(file_name):
            ret = None
            with open(file_name, "r") as f:
                content = f.read()
                ret = content if ret is None else f"{ret}\n{content}"
                if extra is not None and len(extra) > 0:
                    ret += "\n" + extra + "\n"
                return ret
    return ""


# iterates all annotations and unifies the different 'section' references
def __normalize_annotation_references(remark_list: list) -> list:
    ret = []
    for remark in remark_list:
        if "section" in remark:
            sections = remark["section"]
            if not isinstance(sections, list):
                sections = []
                for section in str(remark["section"]).split(","):
                    sections.append(section)
            corrected_section_list = []
            for section in sections:
                section = section.strip().lower()
                if "a" <= section[0] <= "z" and (len(section) == 1 or (section[1] > "z" or section[1] < "a")):
                    section = "appendix-" + section.upper()
                elif section.startswith("appendix"):
                    section = "appendix-" + section[9:].upper()
                elif section == "global" or section == "line-1":
                    section = "global"
                elif not section.startswith("line-") and section != "abstract":
                    section = "section-" + section
                if section.endswith("."):
                    section = section[:-1]
                if section not in ret:
                    ret.append(section)
                corrected_section_list.append(section)
            remark["section"] = corrected_section_list
    return ret


# searches for annotations with a 'fragment-' section reference and tries to determine the current line containing
# the desired text fragment.
def __handle_annotations_with_fragment_references(remark_list: list, lines: list) -> list:
    ret = []
    for remark in remark_list:
        if "section" in remark:
            target: str = remark["section"]
            if target.startswith("fragment-"):
                target = target[9:]
                found = False
                # find the target in the lines
                for nr, line in enumerate(lines):
                    line = line.replace("|", "")    # remove generated comment characters contained in newer RFCs
                    if target in line:
                        remark["section"] = f"line-{nr+1}"
                        found = True
                        break
                if not found and len(target) > 1:
                    # try to find the string by combining two lines
                    for nr, line in enumerate(lines):
                        combined = lines[nr - 1].replace("|", "") + " " + line.replace("|", "").strip()
                        if nr > 0 and target in combined:
                            remark["section"] = f"line-{nr}"
                            break
        ret.append(remark)
    return ret


# creates annotated html files for a given list of RFCs.
def create_files(rfc_list: list, errata_list: list, patches: Optional[dict], read_directory: str = ".",
                 annotation_directory: str = None, write_directory: str = ".") -> dict:

    def create_unique_erratum_ref(eid: str) -> str:
        if eid in erratum_references:
            ret = erratum_references[eid] + 1
        else:
            ret = 0
        erratum_references[eid] = ret
        return "rfc.erratum." + eid + ("" if ret == 0 else f".{ret}")

    def write_annotation(remarks_present: bool, annotation_text: str) -> (bool, str):
        erratum_id = str(rem["errata_id"]) if "errata_id" in rem else None
        caption = str(rem["caption"]) if "caption" in rem else None
        date = str(rem["date"]) if "date" in rem else ""
        if len(date) > 0:
            if rfc in rfcs_last_updated:
                old_entry = rfcs_last_updated[rfc]
                if old_entry < date:
                    rfcs_last_updated[rfc] = date
            else:
                rfcs_last_updated[rfc] = date
        annotation_type = str(rem["type"]) if "type" in rem else None
        title = rem["submitter_name"] if "submitter_name" in rem else "Unknown Author"
        author = rem["submitter_name"] if "submitter_name" in rem else None
        if author is not None:
            author = author.lower().replace("'", "").replace('"', '')

        if not remarks_present:
            f.write(f'</span></pre>\n<div class="annotation">{annotation_text}</div></div>'
                    f'\n\n<div class="area">\n<pre class="{rfc_class}">'
                    f'<span class="{rfc_class}">')
            remarks_present = True
            annotation_text = ""

        if erratum_id is None:
            entry_type = "entry"
            if annotation_type is not None:
                if annotation_type in annotations.built_in_annotation_types():
                    entry_type = f"status {annotation_type.replace('_', '')}"
                else:
                    entry_type += f" {annotation_type}"
        else:
            entry_type = "err"
            prefix = ""
            suffix = ""
            if annotation_type is not None:
                prefix = f'{annotation_type} '
                entry_type += f' {annotation_type.lower()}'
            if "errata_status_code" in rem:
                s = rem["errata_status_code"]
                suffix = f' [{s}]'
                entry_type += f' {s.lower().replace(" ", "")}'
            if "outdated" in rem:
                entry_type += ' outdated'
            # eclipsed annotations are not supported anymore...
            # if "eclipsed" in rem:
            #     entry_type += ' eclipsed'
            link_title = f'{author} ({rem["type"]})'
            link = "https://www.rfc-editor.org/errata/eid" + erratum_id
            if caption is None:
                caption = ""
            else:
                caption += " "
            caption = f'<span id="' + create_unique_erratum_ref(erratum_id) + f'">{caption}({prefix}Erratum #' + \
                      util.create_anchor(link, erratum_id, ")" + suffix + "</span>", "", {"title": link_title})

        if author is not None:
            entry_type += f' {author}'

        annotation_text += f'<div onclick="clicked(this)" class="{entry_type}">' \
                           '<div class="title"><span class="reference">'
        if section == "global":
            annotation_text += '<a href="">GLOBAL</a> '
        else:
            annotation_text += f'<a href="#{section}">{section}</a> '
        annotation_text += f'{title}</span>' \
                           f'<span class="caption">{caption}</span>' \
                           f'<span class="timestamp">{date}</span>' \
                           f'</div>'
        if "outdated" in rem:
            annotation_text += '<span class="info">based on outdated version</span>'
        annotation_text += f'<div class="notes">'

        if "notes" in rem and rem["notes"] is not None:
            if type(rem["notes"]) is list:
                for entry in rem["notes"]:
                    annotation_text += entry

        annotation_text += "</div></div>"
        return remarks_present, annotation_text

    rfcs_last_updated = {}
    read_directory = util.correct_path(read_directory)
    write_directory = util.correct_path(write_directory)
    css = __read_html_fragments("css.html", util.get_from_environment("CSS", None))
    scripts = __read_html_fragments("scripts.html", util.get_from_environment("SCRIPTS", None))
    util.info(f"Converting {len(rfc_list)} RFC text documents. Writing output to '{write_directory}'.")
    if not util.verbose_output:
        util.info("Did write:", end="")
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        rfc_nr = rfc[3:]
        read_filename = read_directory + rfc + ".txt"
        write_filename = write_directory + rfc + ".html"
        if util.verbose_output:
            util.debug(f"Writing {rfc}.html")
        else:
            util.info(f" {rfc}.html", end="")
        remarks = annotations.get_annotations(rfc, annotation_directory, errata_list, patches, rfc_list)
        try:
            with open(write_filename, "w") as f:
                rfc_class = "rfc"
                for r in remarks:
                    if "type" in r:
                        t = r["type"]
                        if t in annotations.built_in_annotation_types():
                            rfc_class += " " + t
                f.write(f'<!DOCTYPE html>\n<html lang="en" id="html">\n<head><meta charset="UTF-8">'
                        f'<title>RFC {rfc_nr}</title>')
                if css is not None:
                    f.write(f'\n{css}')
                if scripts is not None:
                    f.write(f'{scripts}\n')
                f.write('</head>\n')
                f.write('<body onload="adjustFontSize()">\n')
                if scripts is not None:
                    f.write("<noscript>For full functionality of this page please enable JavaScript</noscript>\n")
                f.write('<button class="floating" onclick="hideRFC()" id="hideBtn">Hide RFC</button>\n')
                f.write('<button class="floating" onclick="showRFC()" id="showBtn" hidden="hidden">Show RFC</button>\n')
                f.write(f'<div class="area">\n<pre class="{rfc_class}"><span class="{rfc_class}">')
                line_nr = 0
                annotation = ""
                lines = htmlize_rfcs.markup(open(read_filename).read()).splitlines()
                remarks = __handle_annotations_with_fragment_references(remarks, lines)
                remarks_sections = __normalize_annotation_references(remarks)
                erratum_references = {}
                for line in lines:
                    # cut leading and trailing <pre> elements
                    if line.endswith("</pre>"):
                        line = line[:-6]
                    elif line_nr == 0 and line.startswith("<pre>"):
                        line = line[5:]

                    skip_line_end = False
                    if line.startswith("<hr class='noprint'/>"):
                        line = line.replace("<pre class='newpage'>", "")
                        line = line.replace("<hr class='noprint'/>", "<span class='pagebreak'></span>\n")
                        skip_line_end = True
                    else:
                        line_nr += 1
                        aid = "line-" + str(line_nr)
                        text = str(line_nr).rjust(5)
                        line = f'<a class="line" id="{aid}" href="#{aid}">{text}</a> {line.ljust(73)}'
                    line = __rewrite_anchor(line, rfc_list)

                    rem_present = False
                    for section in remarks_sections:
                        if section == "global" or (f'id="{section}"' in line):
                            remark_written = False
                            for rem in remarks:
                                if section in rem["section"]:
                                    remark_written = True
                                    rem_present, annotation = write_annotation(rem_present, annotation)
                            if remark_written:
                                remarks_sections.remove(section)
                    f.write(line)
                    if not skip_line_end:
                        f.write("\n")

                # check whether we do have unhandled annotations
                if len(remarks_sections) > 0:
                    error = None
                    for section in remarks_sections:
                        files = None
                        for rem in remarks:
                            if section in rem["section"]:
                                rem_present, annotation = write_annotation(rem_present, annotation)
                                # do not add a warning for rejected errata
                                if "errata_id" not in rem or rem["errata_status_code"] != "Rejected":
                                    files = rem["path"] if files is None else files + ", " + rem["path"]
                        if files is not None:
                            if error is None:
                                error = f"annotations for {rfc.upper()} have {len(remarks_sections)} INVALID "\
                                        f"document references {remarks_sections}: "
                            else:
                                error += ", "
                            error += f"'{section}' referenced in {files}"
                    if error is not None:
                        util.warn(f"{error}. These annotations will appear at the end of the document!\n")

                f.write(f'</span></pre><div class="annotation">{annotation}</div></div>\n')
                f.write('\n</body></html>\n')
        except Exception as e:
            util.error(f"can't read {read_filename}: {e}.")
    if not util.verbose_output:
        util.info(". Done.")
    return rfcs_last_updated
