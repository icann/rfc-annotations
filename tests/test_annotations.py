import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '../program'))

import annotations
import errata
import util

''' Test class checking the correct generation of annotations '''


def remove_volatile_data(entries: [dict]) -> [dict]:
    for entry in entries:
        if "path" in entry:
            del entry["path"]
    return entries


def test_annotation_conversion():
    my_dir = os.path.dirname(__file__)
    os.chdir(os.path.join(my_dir, ".."))
    errata_list = errata.read_errata(util.get_from_environment("TXT_DIR", "raw-originals"))
    patches = errata.get_patches()

    created_results = []
    ann_dir = os.path.join(my_dir, "annotations")
    for file in util.filtered_files(ann_dir):
        if not file.startswith("."):
            created = remove_volatile_data(annotations.get_annotation_from_file(os.path.join(ann_dir, file),
                                                                                errata_list, patches))
            persisted_file_name = os.path.join(os.path.join(my_dir, "expected-results"), file)
            if os.path.exists(persisted_file_name):
                with open(persisted_file_name, "r") as f:
                    expected = json.loads(f.read())
                    assert created == expected
            else:
                with open(persisted_file_name, "w") as f:
                    f.write(json.dumps(created))
                    created_results.append(file)
    assert created_results == [], "all expected result files should already be present"
