import os
import sys
from urllib.request import urlopen

from util import correct_path

''' Download the RFC files for RFC annotations tools '''


def download_rfcs(rfc_list: list, directory: str = "."):
    directory = correct_path(directory)
    print(f"\nDownloading {len(rfc_list)} RFC documents to '{directory}':")
    for rfc in rfc_list:
        rfc: str = rfc.lower().strip()
        rfc = rfc if rfc.startswith("rfc") else "rfc" + rfc
        filename = directory + rfc + ".txt"
        file_size = 0
        try:
            file_size = os.path.getsize(filename)
        except FileNotFoundError:
            pass
        if file_size > 0:
            print(f"Local file  {rfc.ljust(7)} with {str(file_size).rjust(6)} bytes seems ok.")
        else:
            print(f"Downloading {rfc.ljust(7)}... ", end='')
            try:
                content = urlopen(f"https://www.rfc-editor.org/rfc/{rfc}.txt").read()
                if type(content) is bytes:
                    print(f"Retrieved {str(len(content)).rjust(6)} bytes of data.")
                    with open(filename, "wb") as f:
                        f.write(content)
                else:
                    print(f"\n   Error: got unexpected fetching response data of type {type(content)}.", file=sys.stderr)
            except Exception as e:
                print(f"\n   Error: can't download text file for {rfc}: {e}.", file=sys.stderr)
