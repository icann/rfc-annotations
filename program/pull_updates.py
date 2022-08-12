#!/usr/bin/env python3
import os.path
import subprocess
import urllib.request
from pathlib import Path

''' Program to get updates to annotations from remote locations '''


def handle_git(this_url, target_dir):
    # Do a git clone, if necessary; do a git pull if not
    # If the directory does have a .git subdirectory, do a "git clone"
    if not (target_dir / ".git").exists():
        try:
            print(f"Cloning {this_url} into {str(target_dir)} for the first time.")
            subprocess.run(f"git clone {this_url} {str(target_dir)}", shell=True, check=True)
        except:
            print(f"** Running the initial 'git clone {this_url} {str(target_dir)}' failed. Skipping.")
            return
    # Pull the contents
    else:
        try:
            process = subprocess.run(f"cd {str(target_dir)} && git pull", shell=True, check=True, capture_output=True,
                                     text=True)
            if "Already up to date" in process.stdout:
                print(f"Already up to date: {this_url}")
            else:
                print(f"Got updates for {this_url}")
        except:
            print(f"** Running 'cd {str(target_dir)} && git pull' failed. Skipping.")


# noinspection PyBroadException
def process_config_content(config):
    # This is defined as a function so it can be called recursively
    # Go through line-by-line
    line_count = 0
    for this_line in config.splitlines():
        line_count += 1
        # Sanity checks for the config file
        if this_line.startswith("#"):
            continue
        if this_line.strip() == "":
            continue
        if "\t" not in this_line:
            exit(f"Line {line_count} in {str(config_location)} does not have a <tab> character. Exiting.")
        this_url = None
        this_dir = None
        try:
            this_url, this_dir = this_line.split("\t", maxsplit=1)
        except:
            exit(f"Line {line_count} in {str(config_location)} has more than one <tab> character. Exiting.")
        # Be sure it looks like a URL or at least has a : for SSH-like descriptors
        if ":" not in this_url:
            exit(f"There is no ';' in the first field in line {line_count}: \"{this_url}\". Exiting.")
        # Create the target directory if it is not already there
        target_dir = Path(f"annotations/{this_dir}")
        if not target_dir.exists():
            try:
                target_dir.mkdir()
                print(f"Made new directory {target_dir} for line {line_count} in {str(config_location)}")
            except:
                exit(f"Could not create {str(target_dir)} for line {line_count} in {str(config_location)}. Exiting.")
        # It might be an SSH-style git account, so there will be no "//"
        if "//" not in this_url:
            if not this_url.endswith(".git"):
                print(f"** There is an git-as-SSH URL in line {line_count}, \"{this_url}\", but it does not end "
                      "with \".git\". Skipping.")
                continue
            handle_git(this_url, target_dir)
            continue
        else:
            (this_scheme, _) = this_line.split(":", maxsplit=1)
            if this_scheme == "git":
                print(f"** Line {line_count} has a full git URL of \"{this_url}\", but this program doesn't handle "
                      "\"git://\" URLs.")
                print("** Instead, use an SSH-style URL for git, such as git@github.com:some_person/some_repo.git")
                print("** or an https URL such as https://github.com/some_person/some_repo.git. Skipping.")
                continue
            elif this_scheme == "rsync":
                if not has_rsync:
                    print(f"** There is an rsync URL in line {line_count}, \"{this_url}\", but there is no rsync "
                          "on in the path on this system. Skipping.")
                    continue

                # Do the rsync
                try:
                    subprocess.run(f"rsync -av {this_url} {str(target_dir)}", shell=True, check=True,
                                   capture_output=True, text=True)
                    print(f"Successful rsync for {this_url}")
                except Exception as e:
                    print(f"The rsync URL in line {line_count}, \"{this_url}\", failed with {e}. Skipping.")
                continue
            elif this_scheme in ("http", "https"):
                # Get the last part of the URL to see if it is .git
                if this_url.endswith(".git"):
                    handle_git(this_url, target_dir)
                    continue
                try:
                    with urllib.request.urlopen(this_url) as f:
                        web_contents = f.read().decode('latin-1')
                except Exception as e:
                    print(f"** Error reading {this_url}: {e}. Skipping.")
                    continue
                # See if it nees to be updated
                filename_part = this_url.split("/")[-1]
                out_name_path = Path(target_dir) / filename_part
                if out_name_path.exists():
                    with out_name_path.open(mode="rt") as in_f:
                        to_compare = in_f.read()
                    if to_compare == web_contents:
                        print(f"No need to update {this_url}")
                        continue
                # Do the update
                try:
                    with out_name_path.open(mode="wt") as out_f:
                        out_f.write(web_contents)
                    print(f"Wrote out new version of {this_url}")
                    continue
                except Exception as e:
                    print(f"** Error when writing {str(out_name_path)}: {e}. Skipping.")
                    continue
            else:
                print(f"** Line {line_count} has an unknown URL type: \"{this_url}\". Skipping.")
                continue


# Main program here
if __name__ == "__main__":
    # Determine if they have rsync
    p = subprocess.run("which rsync", capture_output=True, shell=True)
    if p.stdout:
        has_rsync = True  # It found a rsync
    else:
        has_rsync = False

    # Name of config file
    config_name = "annotation-sources.txt"
    directories = ["local-config", "default-config"]
    # Location of config file
    for directory in directories:
        config_location = os.path.join(directory, config_name)
        if os.path.exists(config_location):
            try:
                config_content = Path(config_location).open(mode="rt").read()
                process_config_content(config_content)
                exit()
            except UnicodeDecodeError:
                exit(f"{config_location} does not appear to be a text file. Exiting.")
    # Process the config content on the file from local
    exit(f"Could not find config file {config_name} in {str(directories)}. Exiting.")
