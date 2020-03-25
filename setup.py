import os
import re
import sys
from os import getcwd
from os.path import splitext, dirname, basename, isdir, isfile, abspath, join as pathjoin
from glob import glob
from setuptools import find_namespace_packages, setup

top_dir = dirname(abspath(sys.argv[0]))
while not isdir(pathjoin(top_dir, '.git')) and not isfile(pathjoin(top_dir, 'PACKAGE.ini')):
    top_dir = dirname(top_dir)
    if top_dir is '':
        raise Exception('Could not find top dir')


full_name = basename(top_dir)
if 'JOB_NAME' in os.environ:
    full_name = re.sub(r'/.*', '', os.environ['JOB_NAME'])

name = re.sub(r'.*python3?-', '', full_name) + "-dbc"
github = 'https://github.com/DBCDK/' + full_name

# Pull [segment] text from '{TOPDIR}/PACKAGE.ini'
def desc_part(segment):
    with open(pathjoin(top_dir, 'PACKAGE.ini'), 'r') as stream:
        matcher = re.compile(r'^\[(.*)\]$')
        include = False
        result = []
        for line in stream.readlines():
            m = matcher.match(line)
            if m is not None:
                include = m.group(1) == segment
            elif include:
                result.append(line)
        return ''.join(result)

# Extract form PACKAGE.ini
version = desc_part('version').strip()
dependencies = [ d for d in re.split(r'\s+', desc_part('dependencies'), re.MULTILINE|re.DOTALL) if d != '' ]
debian_depends = ", ".join(dependencies)
description = desc_part('description').strip()
long_description = desc_part('long_description').strip()

# Make copyright.txt with correct urls
for copyright in glob('copyright.txt.in'):
    with open(splitext(copyright)[0], 'w') as ostream:
        print("Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/", file=ostream)
        print("Upstream-Name: %s" % name, file=ostream)
        print("Source: <%s>" % github, file=ostream)
        print("", file=ostream)
        with open(copyright, 'r') as istream:
            ostream.write(istream.read())

setup(
    name=name,
    version=version,    
    packages=find_namespace_packages('src', exclude=['tests', 'tests.*', '*.tests', '*.tests.*']),
    package_dir={'' : 'src'},
    options={
        'build_exe': {
            'packages': find_namespace_packages('src', exclude=['tests', 'tests.*', '*.tests', '*.tests.*'])
        }
    },
    scripts=[str(g) for g in glob('bin/*')],
    requires=[s.replace('python3-', '') for s in dependencies if s.startswith('python3-')],
    provides=[name.replace('-', '_')],
    data_files=[('share/man/man1', [str(g) for g in glob('man/*')])],
    url=github,
    license='gpl3',
    author='DBC',
    author_email='dbc@dbc.dk',
    description=description,
    long_description=long_description
)

# Add dependencies in debian/rules build step
for rules in glob('deb_dist/*/debian/rules'):
    with open(rules, 'a') as stream:
        print("override_dh_python3:", file=stream)
        print("\tdh_python3 -O--buildsystem=pybuild", file=stream)
        print("\tperl -pi -e 's{$$}{, %s} if m{^python3:Depends=}' debian/*.substvars" % debian_depends, file=stream)

