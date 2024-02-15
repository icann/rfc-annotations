import os

import util  # correct_path, debug, info, error, urlopen

''' Download the RFC files for RFC annotations tools '''


# downloads the textual representation (https://www.rfc-editor.org/rfc/*.txt) of the given RFCs
def download_rfcs(rfc_list: list, directory: str = "."):
    directory = util.correct_path(directory)
    util.info(f"Scanning for {len(rfc_list)} RFC documents in '{directory}':")
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
            util.debug(f"Local file  {rfc.ljust(7)} with {str(file_size).rjust(6)} bytes seems ok.")
        else:
            util.info(f"Downloading {rfc.ljust(7)}... ", end='')
            try:
                content = util.urlopen(f"https://www.rfc-editor.org/rfc/{rfc}.txt").read()
                if type(content) is bytes:
                    util.info(f"Retrieved {str(len(content)).rjust(6)} bytes of data.")
                    with open(filename, "wb") as f:
                        f.write(content)
                else:
                    util.info("")
                    util.error(f"got unexpected fetching response data of type {type(content)}.")
            except Exception as e:
                util.error(f"can't download text file for {rfc}: {e}.")
    util.info(f"All RFC documents handled.")
