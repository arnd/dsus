#!/usr/bin/python

""" Debian Smart Upload Server checks

@copyright: 2010  Petr Jasek <jasekpetr@gmail.com>
@license: GNU General Public License version 2 or later
"""

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

################################################################################

import re
import os.path
import hashlib
from time import time

import daklib.utils
from daklib.queue import Upload
from daklib.lintian import parse_lintian_output

# return codes
OK = 200

CHANGES_EMPTY = 431
ACTION_UNKNOWN = 432
FILENAME_EMPTY = 433
DESTINATION_ERROR = 434
CHANGES_NOT_FOUND = 435
SESSION_EXPIRED = 436
LENGTH_EMPTY = 437
LENGTH_ERROR = 438
FILE_UNEXPECTED = 439

CHECKSUM_ERROR = 451
BINARY_ERROR = 452
SIGNATURE_ERROR = 453

FILES_ERROR = 471

responses = {
    200: ('OK', 'OK'),
    
    431: ('Empty changes', 'Changes param not specified'),
    432: ('Unknown action', 'Unknown action'),
    433: ('Empty filename', 'Filename not specified'),
    434: ('Destination error', 'Destination directory not found'),
    435: ('Changes not found', 'Changes file not found'),
    436: ('Session expired', 'Upload session expired'),
    437: ('Length empty', 'Content-Length header not specified'),
    438: ('Length conflict', 'Length header not match .changes'),
    439: ('File unexpected', 'Send .changes file first'),
    
    451: ('Checksum error', 'Checksum not match .changes'),
    452: ('Binary error', 'Binary error'),
    453: ('Signature error', 'Key not found in the keyring'),

    471: ('Files error', 'Upload check_hashes error')
}

class CheckError(Exception):
    """ Check error exception """
    def __init__(self, code):
        self.code = code
    def __str__(self):
        return self.code


def check_filename(handle):
    """ Filename must be non-empty """
    if not handle.filename:
        raise CheckError(FILENAME_EMPTY)
    return True

def check_headers(handle):
    """ Content-Length header must be specified """
    if not handle.headers.has_key("Content-Length"):
        raise CheckError(LENGTH_EMPTY)
    else:
        handle.length = int(handle.headers["Content-Length"])
    return True

def check_dirname(handle):
    """ Directory must exists if dirname is set """
    if os.path.isabs(handle.dirname):
        handle.dirname = handle.dirname[1:]
    handle.dest = os.path.join(handle.cnf["DSUS::Path"], handle.dirname)
    if not os.path.isdir(handle.dest):
        raise CheckError(DESTINATION_NOT_FOUND)
    return True

def check_changes(handle):
    """ Changes file must exists """
    if not handle.changes:
        raise CheckError(CHANGES_EMPTY)

    handle.changes = os.path.join(handle.dest, handle.changes)
    if not os.path.isfile(handle.changes):
        raise CheckError(CHANGES_NOT_FOUND)

    handle.upload = Upload()
    if not handle.upload.load_changes(handle.changes):
        print handle.upload.rejects
        raise CheckError(CHANGES_BAD_FORMAT)

    if handle.type == 'done':
        return True

    if not handle.upload.pkg.files.has_key(handle.filename):
        raise CheckError(FILE_UNEXPECTED)
    else:
        handle.md5sum = handle.upload.pkg.files[handle.filename]['md5sum']
    return True

def check_size(handle):
    """ Size check """
    size = int(handle.upload.pkg.files[handle.filename]['size'])
    if size != handle.length:
        raise CheckError(LENGTH_ERROR)
    return True

def check_time(handle):
    """ Check if upload is within time window """
    window  = int(handle.cnf['DSUS::timeWindow'])
    if time() - os.path.getmtime(handle.changes) > window:
        raise CheckError(SESSION_EXPIRED)
    return True

def check_checksum(handle):
    """ Checksum check """
    if not handle.md5sum:
        raise CheckError(FILE_UNEXPECTED)
    md5 = hashlib.md5()
    content = open(handle.tempfile.name, 'r')
    md5.update(content.read(handle.length))
    content.close()
    if md5.hexdigest() != handle.md5sum:
        raise CheckError(CHECKSUM_ERROR)
    return True

def check_valid_deb(handle):
    """ Check Binary.valid_deb """
    binary = Binary(handle.tempfile.name, handle.log_error)
    if not binary.valid_deb():
        raise CheckError(BINARY_ERROR)
    return True

def check_lintian(handle):
    """ Check lintian """
    return True

def check_signature(handle):
    """ Check file signature """
    fingerprint, rejects = daklib.utils.check_signature(handle.tempfile.name)
    if not fingerprint:
        #print rejects.pop()
        raise CheckError(SIGNATURE_ERROR)
    return True

def check_files(handle):
    """ Check all uploaded files """
    if handle.upload.rejects:
        raise CheckError(FILES_ERROR)
    return True


