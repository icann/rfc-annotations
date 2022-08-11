import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../program'))

import output
import util
import errata
import rfcfile
import annotations

''' Test class checking the correct generation of html output '''

my_dir = os.path.dirname(__file__)
RFC_LIST = ["1034", "1035", "9220"]
TXT_DIR = util.get_from_environment("TXT_DIR", "raw-originals")
GEN_DIR = util.get_from_environment("OUTPUT", "generated-html")
ANN_DIR_GENERATED = os.path.join(util.get_from_environment("ANNOTATIONS", "annotations"), "_generated")
RESULT_DIR = os.path.join(my_dir, "expected-results")
os.chdir(os.path.join(my_dir, ".."))


def compare_file(file_name: str, gen_dir: str, expected_dir: str):
    contents = []
    for d in [gen_dir, expected_dir]:
        file = os.path.join(d, file_name)
        if os.path.exists(file):
            with open(file, "rt") as f:
                contents.append(f.read())
    assert len(contents) == 2, f"file {file_name} must be present in {gen_dir} and {expected_dir}"
    if len(contents) == 2:
        assert contents[0] == contents[1]


def prepare_files() -> tuple:
    rfcfile.download_rfcs(RFC_LIST, TXT_DIR)
    errata_list = errata.read_errata(TXT_DIR)
    patches = errata.get_patches()
    annotations.create_from_status(RFC_LIST, ANN_DIR_GENERATED, TXT_DIR, errata_list, patches)
    annotations.create_from_errata(RFC_LIST, ANN_DIR_GENERATED, errata_list, patches)
    return errata_list, patches


def test_index_creation():
    output.create_index("tmp", RFC_LIST, GEN_DIR, TXT_DIR, "Test")
    compare_file("tmp-index.html", GEN_DIR, RESULT_DIR)


def test_html_output_plain():
    errata_list, patches = prepare_files()
    output.create_files(RFC_LIST, errata_list, patches, TXT_DIR, None, GEN_DIR)
    for rfc in RFC_LIST:
        compare_file(f"rfc{rfc}.html", GEN_DIR, os.path.join(RESULT_DIR, "plain"))


def test_html_output_annotated():
    errata_list, patches = prepare_files()
    output.create_files(RFC_LIST, errata_list, patches, TXT_DIR, os.path.join(my_dir, "rfc-annotations"), GEN_DIR)
    for rfc in RFC_LIST:
        compare_file(f"rfc{rfc}.html", GEN_DIR, os.path.join(RESULT_DIR, "annotated"))
