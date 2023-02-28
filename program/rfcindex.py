import os
from xml.dom.minidom import Element, Node, Document, parseString
from requests import get
from typing import Union, Optional, Tuple

import util  # debug, info, error

''' Create the RFC index for RFC annotations tools '''


# returns a cached version of https://www.rfc-editor.org/rfc-index.xml. Will be automatically created if absent.
def read_xml_document(path: str = ".", url: str = "https://www.rfc-editor.org/rfc-index.xml") \
        -> Tuple[Optional[Document], Optional[dict]]:
    file_path = os.path.join(path, "rfc-index.xml")
    xml_content = None

    # fetch cached version of rfc-index.xml
    # noinspection PyBroadException
    try:
        with open(file_path, "rb") as f:
            xml_content = f.read()
    except Exception:
        pass

    util.info(f"\nFetching data from source of truth {url}... ", end='')
    if xml_content is not None:
        # check whether the cached version is still up-to-date
        try:
            with open(file_path + ".etag", "r") as f:
                response = get(url, headers={"accept-encoding": "identity", "If-None-Match": f.read()})
                if response.status_code == 304:
                    util.info("cached version is still valid")
                else:
                    util.info("etag changed -> refetching file")
                    xml_content = None
        except Exception:
            util.info("no valid etag found -> refetching file")
            xml_content = None

    # fetch the file from the server
    if xml_content is None:
        response = get(url, headers={"accept-encoding": "identity"})
        xml_content = response.content
        # save the ETag
        if "ETag" in response.headers:
            with open(file_path + ".etag", "w") as f:
                f.write(response.headers["ETag"])
        # and the content
        if type(xml_content) is bytes:
            util.info(f"Retrieved {len(xml_content)} bytes of data. Parsing... ", end='')
            with open(file_path, "wb") as f:
                f.write(xml_content)
        else:
            util.info("")
            util.error(f"got unexpected fetching response data of type {type(xml_content)}.")

    if xml_content is not None:
        document = parseString(xml_content)
        if type(document) is Document:
            doc: Document = document
            root: Node = doc.firstChild
            util.debug(f"Got {len(root.childNodes)} entries.\n")
            return doc, __build_lookup_map(doc)
        else:
            util.debug("")
            util.error(f"got unexpected parsing response type {type(document)}.")
    return None, None


# creates a dictionary for faster lookup of desired elements
def __build_lookup_map(parent: Document, element: str = "rfc-entry", attribute: str = "doc-id") -> dict:
    ret = {}
    for candidate in parent.getElementsByTagName(element):
        for child in candidate.childNodes:
            if child.localName == attribute:
                ret[child.firstChild.data] = candidate
    return ret


# returns the details of a node (usually a 'rfc-entry' node defined by its RFC number)
def fetch_element(parent: Union[Element, Document, dict], value: str, element: str = "rfc-entry",
                  attribute: str = "doc-id") -> Optional[Element]:
    if type(parent) == dict:
        return parent[value]

    for candidate in parent.getElementsByTagName(element):
        for child in candidate.childNodes:
            if child.localName == attribute and child.firstChild.data == value:
                return candidate
    return None


# returns a list of RFCs which are connected (eg. by "updated-by" or "obsoleted-by") to a given RFC
def referenced_document_ids(node: Element, verb: str) -> list:
    ret: list = []
    for child in node.getElementsByTagName(verb):
        for reference in child.getElementsByTagName("doc-id"):
            ret.append(reference.firstChild.data)
    ret = sorted(ret, key=lambda s: int(s[3:]))
    return ret
