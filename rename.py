#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import sys
import tempfile
import textwrap

TEMPLATE_SNAKE = 'pulp_plugin_template'
TEMPLATE_CAMEL = 'PulpPluginTemplate'
TEMPLATE_CAMEL_SHORT = 'PluginTemplate'
TEMPLATE_DASH = 'pulp-plugin-template'
TEMPLATE_DASH_SHORT = 'plugin-template'
IGNORE_FILES = ('LICENSE', 'rename.py', 'flake8.cfg')
IGNORE_COPYTREE = ('.git*', '*.pyc', '*.egg-info', 'rename.py', '__pycache__')


def is_valid(name):
    """
    Check if specified name is compliant with requirements for it.

    The max length of the name is 16 characters. It seems reasonable to have this limitation
    because the plugin name is used for directory name on the file system and it is also used
    as a name of some Python objects, like class names, so it is expected to be relatively short.
    """
    return bool(re.match(r'^[a-z][0-9a-z_]{2,15}$', name))


def to_camel(name):
    """
    Convert plugin name from snake to camel case
    """
    return name.title().replace('_', '')


def to_dash(name):
    """
    Convert plugin name from snake case to dash representation
    """
    return name.replace('_', '-')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description='rename template data to a specified plugin name')
    parser.add_argument('plugin_name', type=str,
                        help=textwrap.dedent('''\
                            set plugin name to this one

                            Requirements for plugin name:
                             - specified in the snake form: your_new_plugin_name
                             - consists of 3-16 characters
                             - possible characters are letters [a-z], numbers [0-9], underscore [_]
                             - first character should be a letter [a-z]
                        '''))
    args = parser.parse_args()
    plugin_name = args.plugin_name

    if not is_valid(plugin_name):
        parser.print_help()
        return 2

    pulp_plugin_name = 'pulp_' + plugin_name
    replace_map = {TEMPLATE_SNAKE: pulp_plugin_name,
                   TEMPLATE_DASH_SHORT: to_dash(plugin_name),
                   TEMPLATE_DASH: to_dash(pulp_plugin_name),
                   TEMPLATE_CAMEL_SHORT: to_camel(plugin_name),
                   TEMPLATE_CAMEL: to_camel(pulp_plugin_name)}

    # copy template directory
    orig_root_dir = os.path.dirname(os.path.abspath(parser.prog))
    dst_root_dir = os.path.join(os.path.dirname(orig_root_dir), pulp_plugin_name)
    try:
        shutil.copytree(orig_root_dir, dst_root_dir,
                        ignore=shutil.ignore_patterns(*IGNORE_COPYTREE))
    except FileExistsError:
        print(textwrap.dedent('''
              It looks like plugin with such name already exists!
              Please, choose another name.
              '''))
        return 1

    # rename python package directory
    listed_dir = os.listdir(dst_root_dir)
    if TEMPLATE_SNAKE in listed_dir:
        os.rename(os.path.join(dst_root_dir, TEMPLATE_SNAKE),
                  os.path.join(dst_root_dir, pulp_plugin_name))

    # replace text
    for dir_path, dirs, files in os.walk(dst_root_dir):
        for file in files:
            # skip files which don't need any text replacement
            if file in IGNORE_FILES:
                continue

            file_path = os.path.join(dir_path, file)

            # write substituted text to temporary file
            with open(file_path) as fd_in, tempfile.NamedTemporaryFile(mode='w', dir=dir_path,
                                                                       delete=False) as fd_out:
                tempfile_path = fd_out.name
                text = fd_in.read()
                for old, new in replace_map.items():
                    text = text.replace(old, new)
                fd_out.write(text)

            # overwrite existing file by renaming the temporary one
            os.rename(tempfile_path, file_path)

    return 0

if __name__ == '__main__':
    sys.exit(main())
