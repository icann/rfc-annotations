import os
import sys
from xml.dom.minidom import Element, Node, Document, parseString
from urllib.request import urlopen
from typing import Union, Optional

''' Create the RFC index for RFC annotations tools '''


def read_xml_document(path: str = ".", url: str = "https://www.rfc-editor.org/rfc-index.xml") -> Optional[Document]:
    file_path = os.path.join(path, "rfc-index.xml")
    xml_content = None
    # noinspection PyBroadException
    try:
        with open(file_path, "rb") as f:
            xml_content = f.read()
    except Exception:
        pass

    if xml_content is None:
        print(f"\nFetching data from source of truth {url}... ", end='')
        try:
            xml_content = urlopen(url).read()
            if type(xml_content) is bytes:
                print(f"Retrieved {len(xml_content)} bytes of data. Parsing... ", end='')
                with open(file_path, "wb") as f:
                    f.write(xml_content)
            else:
                print(f"\n   Error: got unexpected fetching response data of type {type(xml_content)}.", file=sys.stderr)
        except Exception as e:
            print(f"\n   Error: returned with error: {e}.", file=sys.stderr)
    else:
        print("\nParsing cached rfc-index... ", end='')

    document = parseString(xml_content)
    if type(document) is Document:
        doc: Document = document
        root: Node = doc.firstChild
        print(f"Got {len(root.childNodes)} entries.\n")
        return doc
    else:
        print(f"\n   Error: got unexpected parsing response type {type(document)}.", file=sys.stderr)
    return None


def fetch_element(parent: Union[Element, Document], element: str, value: str, attribute: str = "doc-id") \
        -> Optional[Element]:
    for candidate in parent.getElementsByTagName(element):
        for child in candidate.childNodes:
            if child.localName == attribute and child.firstChild.data == value:
                return candidate
    return None


def referenced_document_ids(node: Element, verb: str) -> list:
    ret: list = []
    for child in node.getElementsByTagName(verb):
        for reference in child.getElementsByTagName("doc-id"):
            ret.append(reference.firstChild.data)
    ret = sorted(ret, key=lambda s: int(s[3:]))
    return ret
