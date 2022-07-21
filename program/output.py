import sys
from typing import Optional

import annotations   # get_annotations
import htmlize_rfcs  # markup
import rfcindex      # read_xml_document, fetch_element
import util          # correct_path, get_from_environment

''' Create the new HTMLized RFCs for RFC annotations tools '''


def create_index(rfc_list: list, write_directory: str = ".", path: str = "."):
    root = None
    response = rfcindex.read_xml_document(path)
    if response is not None:
        root = response.firstChild

    write_directory = util.correct_path(write_directory)
    print("\nCreating index.html...", end="")
    css = read_html_fragments(["css.html"])
    try:
        with open(write_directory + "index.html", "w") as f:
            f.write(f'<html>\n<head>\n<meta charset="UTF-8">\n{css}</head>\n'
                    f'<body><table class="index">\n<tr class="header"><th class="rfc">RFC</th>')
            if root is not None:
                f.write('<th class="title">Title</th><th class="date">Date</th><th class="status">Status</th>')
            f.write("</tr>\n")
            odd = True
            for rfc in rfc_list:
                rfc: str = rfc.lower().strip()
                rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
                node = None if root is None else rfcindex.fetch_element(root, "rfc-entry", rfc.upper())
                f.write(f"<tr class='entry " + ("odd" if odd else "even") + "'>" +
                        f"<td class='rfc'><a target='_blank' href='{rfc}.html'>{rfc[3:]}</a></td>")
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
                            suffix += rewrite_anchor(f' <a href="./{rfc.lower()}">{text}</a>', rfc_list)
                    status = f"{status}{suffix}"
                    f.write(f"<td class='title'>{title}</td>"
                            f"<td class='date'>{date}</td>"
                            f"<td class='status'>{status}</td>")
                f.write("</tr>\n")
            f.write("</table></body></html>")
            print(" Done.")
    except Exception as e:
        print(f"Error: can't create index.html: {e}.", file=sys.stderr)


def rewrite_anchor(line: str, rfc_list: list) -> str:
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
        line = line.replace('<a ', '<a target="_blank" ')
    return line


def read_html_fragments(files: Optional[list] = None) -> str:
    ret = ""
    if files is None:
        files = ["css.html", "scripts.html"]
    for file in files:
        # noinspection PyBroadException
        try:
            with open(file, "r") as f:
                content = f.read()
                ret = content if ret is None else f"{ret}\n{content}"
        except Exception:
            print(f"\nError: can't read {file} file! Output will be broken.", file=sys.stderr)

    extra_css = util.get_from_environment("CSS", None)
    if extra_css is not None and len(extra_css) > 0:
        ret += '\n<style type="text/css">'
        ret += extra_css
        ret += '</style>\n'
    return ret


def get_remark_sections(remark_list: list) -> list:
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
                elif not section.startswith("line-"):
                    section = "section-" + section
                if section.endswith("."):
                    section = section[:-1]
                if section not in ret:
                    ret.append(section)
                corrected_section_list.append(section)
            remark["section"] = corrected_section_list
    return ret


def create_files(rfc_list: list, errata_list: list, patches: dict, read_directory: str = ".",
                 annotation_directory: str = None, write_directory: str = "."):
    read_directory = util.correct_path(read_directory)
    write_directory = util.correct_path(write_directory)
    css = read_html_fragments()
    print(f"Converting {len(rfc_list)} RFC text documents. Writing output to '{write_directory}':")
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        read_filename = read_directory + rfc + ".txt"
        write_filename = write_directory + rfc + ".html"
        remarks = annotations.get_annotations(rfc, annotation_directory, errata_list, patches, rfc_list)
        remarks_sections = get_remark_sections(remarks)
        print(f"Writing {rfc}.html adding {str(len(remarks)).rjust(2)} annotations "
              f"in {str(len(remarks_sections)).rjust(2)} sections...", end="")
        try:
            with open(write_filename, "w") as f:
                f.write(f'<html>\n<head><meta charset="UTF-8">\n{css}</head>\n')
                f.write('<body>\n<div class="area">\n<pre><div class="rfc">')
                line_nr = 0
                annotation_text = ""
                for line in htmlize_rfcs.markup(open(read_filename).read()).splitlines():
                    # cut leading and trailing <pre> elements
                    if line.endswith("</pre>"):
                        line = line[:-6]
                    elif line_nr == 0 and line.startswith("<pre>"):
                        line = line[5:]

                    skip_line_end = False
                    if line.startswith("<hr class='noprint'/>"):
                        line = line.replace("<pre class='newpage'>", "")
                        skip_line_end = True
                    else:
                        line_nr += 1
                        aid = "line-" + str(line_nr)
                        text = str(line_nr).rjust(5)
                        line = f'<a class="line" id="{aid}" href="#{aid}">{text}</a> {line}'
                    line = rewrite_anchor(line, rfc_list)

                    remarks_present = False
                    for section in remarks_sections:
                        if section == "global" or (f'id="{section}"' in line):
                            remark_written = False
                            for rem in remarks:
                                if section in rem["section"]:
                                    remark_written = True
                                    erratum_id = str(rem["errata_id"]) if "errata_id" in rem else None
                                    caption = str(rem["caption"]) if "caption" in rem else None
                                    date = str(rem["date"]) if "date" in rem else ""
                                    annotation_type = str(rem["type"]) if "type" in rem else None
                                    title = rem["submitter_name"] if "submitter_name" in rem else "Unknown Author"

                                    if not remarks_present:
                                        f.write(f'</div></pre>\n<div class="annotation">{annotation_text}</div></div>'
                                                f'\n\n<div class="area">\n<pre><div class="rfc">')
                                        remarks_present = True
                                        annotation_text = ""

                                    if erratum_id is None:
                                        entry_type = "entry"
                                        if annotation_type is not None:
                                            if annotation_type in annotations.special_annotation_types():
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
                                        if "eclipsed" in rem:
                                            entry_type += ' eclipsed'
                                        link_title = f'{rem["submitter_name"]} ({rem["type"]})'
                                        link = "https://www.rfc-editor.org/errata/eid" + erratum_id
                                        if caption is None:
                                            caption = ""
                                        else:
                                            caption += " "
                                        caption = f'<span id="rfc.erratum.{erratum_id}">' \
                                                  f'{caption}({prefix}Erratum #<a target="_blank" '\
                                                  f'title="{link_title}" href="{link}">{erratum_id}</a>){suffix}</span>'

                                    if "submitter_name" in rem:
                                        s = rem["submitter_name"]
                                        entry_type += f' {s.lower().replace(" ", "_")}'

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
                                    annotation_text += f'<span class="notes">'

                                    if "notes" in rem and rem["notes"] is not None:
                                        if type(rem["notes"]) is list:
                                            for entry in rem["notes"]:
                                                annotation_text += entry

                                    annotation_text += "</span></div>"
                            if remark_written:
                                remarks_sections.remove(section)
                    f.write(line)
                    if not skip_line_end:
                        f.write("\n")

                f.write(f'</div></pre><div class="annotation">{annotation_text}</div></div>\n\n</body></html>\n')
                if len(remarks_sections) > 0:
                    print(f"Error: {len(remarks_sections)} sections NOT FOUND (", end="", file=sys.stderr)
                    first = True
                    for section in remarks_sections:
                        if first:
                            first = False
                        else:
                            print(", ", end="", file=sys.stderr)
                        print(f"'{section}'", end="", file=sys.stderr)
                    print(")! ", file=sys.stderr)
                print(" Done.")
        except Exception as e:
            print(f"Error: can't read {read_filename}: {e}.", file=sys.stderr)
