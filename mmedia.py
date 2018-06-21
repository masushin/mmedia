import argparse
import os
import sys
import json
from pathlib import Path
import subprocess
import filecmp
import tempfile
import re
import shutil
from tqdm import tqdm
from time import sleep
import datetime

#
all_debug_flag = False

class TargetFile:
    def __init__(self, tags, debug=False):
        self.tags = tags
        self.debug = debug
        self.date = self._getDate(tags)
        self.src_path = None
        self.dest_path = None
        self.skip = True

    def _getDate(self, tags):
        if "SubSecDateTimeOriginal" in tags:
            creation_date_value = tags["SubSecDateTimeOriginal"]
        elif "DateTimeOriginal" in tags:
            creation_date_value = tags["DateTimeOriginal"] + ".000"
        elif "CreateDate" in tags:
            creation_date_value = tags["CreateDate"] + ".000"
        else:
            dt = datetime.datetime.fromtimestamp(os.stat(self.tags['SourceFile']).st_mtime)
            return {'year':"{0:04d}".format(dt.year), 'month':"{0:02d}".format(dt.month),
                    'day':"{0:02d}".format(dt.day),
                    'hour':"{0:02d}".format(dt.hour),
                    'minute':"{0:02d}".format(dt.minute),'second':"{0:02d}".format(dt.second),
                    'msec':"000"}

        if self.debug == True:
            print("{}".format(creation_date_value))

        creation_date_re = re.search("(?P<year>[0-9]{4}):(?P<month>[0-9]{2}):(?P<day>[0-9]{2}) "
                                        "(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})\.(?P<msec>[0-9]{,6})",
                                    creation_date_value, re.MULTILINE)

        return {'year':creation_date_re.group("year"), 'month':creation_date_re.group("month"), 'day':creation_date_re.group("day"),
                'hour':creation_date_re.group("hour"), 'minute':creation_date_re.group("minute"), 'second':creation_date_re.group("second"),
                'msec':creation_date_re.group("msec")}


    def execArrange(self, dest):
        if 'SourceFile' in self.tags:
            src_path = Path(self.tags['SourceFile'])
        else:
            return False

        if not 'Model' in self.tags:
            self.tags['Model'] = "Unknown"

        modelname = re.sub("[ /]", "", self.tags['Model'], re.MULTILINE)

        dest_path = Path(dest).resolve().joinpath('{}'.format(self.date['year']),'{}'.format(modelname))
        dest_path.mkdir(parents=True, exist_ok=True)

        for i in range(0,999):
            if i == 0:
                filename = Path("{}_{}{}_{}{}{}_{}_{}{}".format(self.date['year'],self.date['month'],self.date['day'],
                                                    self.date['hour'],self.date['minute'],self.date['second'],
                                                    self.date['msec'],modelname,src_path.suffix))
            else:
                filename = Path("{}_{}{}_{}{}{}_{}_{}_{:03d}{}".format(self.date['year'],self.date['month'],self.date['day'],
                                                    self.date['hour'],self.date['minute'],self.date['second'],
                                                    self.date['msec'],modelname,i,src_path.suffix))

            if dest_path.joinpath(filename).exists():
                if filecmp.cmp(str(src_path), str(dest_path.joinpath(filename))):
                    print("Dupricated : {}".format(src_path))
                    return True

                with tempfile.TemporaryDirectory() as tempdir:
                    file = Path(tempdir).joinpath(filename)
                    shutil.copy2(str(src_path), str(file))
                    if filecmp.cmp(str(file), str(dest_path.joinpath(filename))):
                        print("Dupricated : {}".format(src_path))
                        return True

                continue
            else:
                break

        else:
            print("Can't rename target file..")
            return False
        
        self.src_path = src_path
        self.dest_path = dest_path/filename
        self.skip = False
        return True

    def execMove(self, test=True):
        if test == False and self.skip == False:
            shutil.move(str(self.src_path), str(self.dest_path))


class FileScan:
    def __init__(self, target_path, recursive, debug=False):
        self.target_path = target_path
        self.is_recursive = recursive
        self.debug = debug
        return

    def exec(self):
        print("Running Exiftool ...")
        command = "exiftool -j -fast2 -SourceFile -FileType -CreateDate -DateTimeOriginal -SubSecDateTimeOriginal -Model {} {}".format("-r" if self.is_recursive else "", self.target_path)
        completed_process = subprocess.run(command.split(),stdout=subprocess.PIPE)
        with open("jsondata.txt",mode="w") as fp:
            fp.write(completed_process.stdout.decode('utf-8'))

        data = json.loads(completed_process.stdout.decode('utf-8'))
        target_files = []
        for file in data:
            target_files.append(TargetFile(file, self.debug))

        return target_files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--test", action="store_true", default=False)
    parser.add_argument("-r", "--recursive", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("target_path")
    parser.add_argument("dest_path")
    args = parser.parse_args()
    if False in [Path(args.target_path).is_dir(),Path(args.dest_path).is_dir()]:
        sys.stderr.write("Target/Destination path is not found.")
        sys.exit()

    filescan = FileScan(Path(args.target_path).resolve(), args.recursive, args.debug)
    target_files = filescan.exec()
    with tqdm(total=len(target_files)) as pbar:
        tqdm.write("Moving files ..")
        for target in target_files:
            pbar.set_description(desc=Path(target.tags['SourceFile']).name)
            target.execArrange(Path(args.dest_path).resolve())
            target.execMove(test=args.test)
            pbar.update(1)

if __name__ == '__main__':
    main()
