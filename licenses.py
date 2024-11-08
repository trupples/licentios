import magic
from sys import argv
from collections import defaultdict
import os
import subprocess
import re
import yaml

source_files = [q.decode() for q in subprocess.check_output("git ls-files", shell=True, cwd='linuxmount/').splitlines()]

def firstcomment(filename):
    comment = ''
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()

            # Shortcut
            if 'SPDX-License-Identifier:' in line:
                return line

            if line.startswith('#include') or line.startswith('#if') or line.startswith('#!') or not line.strip(): 
                continue
            
            if line.startswith('# '):
                comment += (line[2:]).strip() + ' '
            elif line.startswith('// '):
                comment += (line[3:]).strip() + '\n'
            elif line.startswith('/*'):
                comment += '\n' + line[2:].split('*/')[0].strip()
                block = True
            elif '*/' in line:
                comment += line.split('*/')[0].strip() + '\n'
                block = False
            elif line.startswith('*'):
                line = line.strip("* ")
                if block:
                    if line == '':
                        comment += '\n'
                    else:
                        comment += line + ' '
                else:
                    break
            else:
                break

    comment = re.sub('\t', '    ', comment, flags=re.MULTILINE)
    comment = re.sub(' +$', '', comment, flags=re.MULTILINE)
    comment = re.sub(' +', ' ', comment, flags=re.MULTILINE)
    comment = re.sub('\n+', '\n', comment, flags=re.MULTILINE)
    
    return comment.strip()

def uniformlicense(license):
    license = license.replace('GPL-2.0+', 'GPL-2.0-or-later')
    return license

def licenseof(filename):
    comments = firstcomment(filename)

    if comments == '':
        return 'GPL-2.0 WITH Linux-syscall-note'
    
    if 'licen' not in comments.lower():
        return 'GPL-2.0 WITH Linux-syscall-note'

    # print(filename, comments)

    # Nice case, license already mentioned
    if spdx := re.search(r'SPDX.License.Identifier: ([^\n]+)', comments):
        license = spdx.group(1)
        license = license.replace('*/', '').strip()
        if license[0] == '(' and license[-1] == ')':
            license = license[1:-1]
        return uniformlicense(license)
    
    DUBIOUS_GPL_DEFAULT = 'GPL-2.0'

    patterns = {
        'under the terms of the GNU General Public License as published by the Free Software Foundation version 2': 'GPL-2.0',
        'under the terms of the GNU General Public License version 2': 'GPL-2.0',
        'This code is licensed under the GPL.': DUBIOUS_GPL_DEFAULT,
        'subject to the terms and conditions of the GNU General Public License.': DUBIOUS_GPL_DEFAULT,
        'under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.': 'GPL-2.0-or-later',
        'permitted under the GNU General Public License.': DUBIOUS_GPL_DEFAULT,
        'under the terms of the GNU Lesser General Public License as published by the Free Software Foundation; either version 2.1 of the license, or (at your option) any later version.': 'LGPL-2.1-or-later',
        "There isn't anything here anymore, but the file must not be empty": 'NONE_BUT_OK',
        'Unsupported proprietary work of Synopsys, Inc.': 'PROPRIETARY:Synopsis',
        'This software may be used and distributed according to the terms of the GNU General Public License (GPL), incorporated herein by reference.': DUBIOUS_GPL_DEFAULT,
        'Alternatively, this software may be distributed under the terms of the GNU General Public License ("GPL") version 2 as published by the Free Software Foundation.': 'BSD-3-Clause OR GPL-2.0',
        'For conditions of distribution and use, see copyright notice in zlib.h': 'Zlib',
        'under the GNU General Public License, Version 2.': 'GPL-2.0',
        ' -- This code is GPL.': DUBIOUS_GPL_DEFAULT,
        'This file is released under the GPL.': DUBIOUS_GPL_DEFAULT,
        'Neither the name of the University nor the names of its contributors': 'BSDCaliforniaCopyright',
        'Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:': 'MIT',
        'Permission to use, copy, modify, and distribute this software and its documentation for any purpose and without fee is hereby granted, provided that the above copyright notice appears in all copies and that both the copyright notice and this permission notice appear in supporting documentation, and that the name University of Delaware not be used in advertising or publicity pertaining to distribution of the software without specific, written prior permission. The University of Delaware makes no representations about the suitability this software for any purpose. It is provided "as is" without express or implied warranty.': 'MIT-CMU',
        'This is free and unencumbered software released into the public domain.': 'PublicDomain',
        'This code is in the public domain': 'PublicDomain',
        'This file has been put into the public domain.': 'PublicDomain',
        'You may choose to be licensed under the terms of the GNU General Public License (GPL) Version 2, available from the file COPYING in the main directory of this source tree, or the OpenIB.org BSD license below': 'GPL-2.0 OR BSD-2-Clause',
        '3. Neither the name of ': 'BSD-3-Clause',
        '3. The names of the above-listed copyright holders may not be used': 'BSD-3-Clause',
        'may be used and distributed according to the terms of the GNU General Public License': DUBIOUS_GPL_DEFAULT,
        'Permission is hereby granted, free of charge, to any person obtaining a': 'MIT',
        'This file is released under the LGPL.': 'LGPL-2.0',
        'under the terms and conditions of the GNU General Public License, version 2, as published by the Free Software Foundation.': 'GPL-2.0',
        'Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met: 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.\n': 'BSD-2-Clause',
        '* Neither the name of Raspberry Pi nor the': 'BSD-3-Clause-RPI',
        'See ../COPYING for licensing terms.': DUBIOUS_GPL_DEFAULT,
        '3. The name of the author may not be used to endorse or promote products derived from this software without specific prior written permission.\nALTERNATIVELY, this product may be distributed under the terms of the GNU General Public License, in which case the provisions of the GPL are required INSTEAD OF the above restrictions.': 'GPL-2.0 OR BSD-3-Clause',
        'under the terms of version 2.1 of the GNU Lesser General Public License': 'LGPL-2.1',

        'See linux/lib/crc32.c for license and changes': DUBIOUS_GPL_DEFAULT,
        'For licencing details see kernel-base/COPYING': DUBIOUS_GPL_DEFAULT,
        'it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.': 'GPL-2.0-or-later',
        'Redistribution of this file is permitted under the terms of the GNU Public License (GPL)': DUBIOUS_GPL_DEFAULT,
        'This file is provided under a dual BSD/GPLv2 license.': 'BSD-3-Clause OR GPL-2.0',
        'Adapted from MIT Kerberos': 'BSD-2-Clause',
        'See the GNU General Public License for more details.': DUBIOUS_GPL_DEFAULT,
        'This software is licensed under the GNU General License Version 2': 'GPL-2.0',
        'BSD 2 - Clause License (http://www.opensource.org/licenses/bsd - license.php)': 'BSD-2-Clause',
        'it under the terms of the GNU Library General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.': 'GPL-2.0-or-later',
        'Released under the General Public License (GPL).': DUBIOUS_GPL_DEFAULT,
        'License: GPL': DUBIOUS_GPL_DEFAULT,

    }

    # Spelling variations
    comments = comments.replace('licence', 'license')

    for pattern, license in patterns.items():
        if pattern.lower() in comments.lower(): # "License" vs "license"
            print(f'Matched {filename} as {license} ("{pattern}")')
            return license
    
    if open(filename, 'r').read().count('\n') < 10:
        return 'SmallFileUnder10Lines'

    return 'Unknown#TODO'

licenses = defaultdict(lambda:[])

with open(argv[1], 'r') as fs:
    filenames = set()
    for i, filename in enumerate(fs):
        filename = filename.strip()

        # Filter out non-source files
        if filename not in source_files:
            continue

        filename = filename.strip()

        # Don't repeat files
        if filename in filenames:
            continue

        # Filter out binaries
        if 'application/x-' in magic.from_file('linux/' + filename, mime=True):
            raise Exception('binary file passed through the cracks?!: ' + filename)

        filenames.add(filename)

        license = licenseof('linux/' + filename)
        licenses[license].append(filename)
        print(i, filename, license)

print('=== LICENSES ===')
print(f'Got {len(licenses)} different licenses:')

for license in sorted(licenses, key=lambda license: -len(licenses[license])):
    print(f'{license}: {len(licenses[license])} files (e.g. {" ".join(licenses[license][:5])})')

print('')
print('')
print('')
print('')
print('Unknown:')
print(' '.join(licenses['Unknown#TODO']))

print(len(licenses['Unknown#TODO']))

print('Writing to ' + argv[1] + '-licenses.yaml')
with open(argv[1] + '-licenses.yaml', 'w') as f:
    yaml.dump(licenses, f)
