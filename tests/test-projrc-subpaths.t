test interaction of projrc with subrepositories that need remappings
via the subpaths section

load extension

  $ echo "[extensions]" >> $HGRCPATH
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HGRCPATH
  $ echo "[projrc]" >> $HGRCPATH
  $ echo "include = *" >> $HGRCPATH
  $ echo "servers = *" >> $HGRCPATH
  $ echo "confirm = False" >> $HGRCPATH

create repository

  $ hg init outer
  $ cd outer

add subrepository

  $ echo 'inner = http://example.net/libfoo' > .hgsub
  $ hg add .hgsub
  $ hg debugsub
  path inner
   source   http://example.net/libfoo
   revision 

hg debugsub with remapping

  $ echo '[subpaths]' > .hg/projrc
  $ printf 'http://example.net/lib(.*) = C:\\libs\\\\1-lib\\\n' >> .hg/projrc
  $ hg debugsub
  path inner
   source   C:\libs\foo-lib\
   revision 

test propagation of .hg/projrc file on clone

  $ hg commit -m checkin
  committing subrepository inner
  $ cd ..
  $ hg clone outer outer2
  updating to branch default
  projrc settings file updated and applied
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd outer2
  $ hg debugsub
  path inner
   source   C:\libs\foo-lib\
   revision 0000000000000000000000000000000000000000

change .hg/projrc file and test pull:

  $ echo '# empty' > ../outer/.hg/projrc
  $ hg pull --traceback
  pulling from $TESTTMP/outer
  projrc settings file updated and applied
  searching for changes
  no changes found
  $ hg debugsub
  path inner
   source   http://example.net/libfoo
   revision 0000000000000000000000000000000000000000

provoke exception in clone

  $ cd ..
  $ hg clone outer outer
  abort: destination 'outer' is not empty
  [255]

test clone with necessary remapping from outer/inner to ../inner

  $ hg init inner
  $ cd inner
  $ touch inner.txt
  $ hg commit --addremove -m 'Inner commit'
  adding inner.txt
  $ cd ../outer
  $ echo 'inner = inner' > .hgsub
  $ echo '[subpaths]' > .hg/projrc
  $ echo "^inner = $TESTTMP/inner" >> .hg/projrc
  $ rm -r inner
  $ hg clone ../inner
  destination directory: inner
  updating to branch default
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg commit -m 'Outer commit'
  committing subrepository inner
  $ cat .hgsubstate
  528388ae73d7807689b94703a1806f0bacf353bc inner

clear out outer repo

  $ hg update null
  0 files updated, 0 files merged, 2 files removed, 0 files unresolved
  $ rm -r inner

clone outer repo, inner is found via .hg/projrc remapping

  $ cd ..
  $ hg clone outer outer3
  updating to branch default
  projrc settings file updated and applied
  cloning subrepo inner from $TESTTMP/inner
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cat outer3/.hg/projrc
  #\ projrc encoding check, line must begin with '#\ '
  [subpaths]
  ^inner = $TESTTMP/inner

clone with no update

  $ hg clone -U outer outer4
  projrc settings file updated and applied
  $ cd outer4
  $ hg update
  cloning subrepo inner from $TESTTMP/inner
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cat .hg/projrc
  #\ projrc encoding check, line must begin with '#\ '
  [subpaths]
  ^inner = $TESTTMP/inner

The following is not active since the .hgsubstate file cannot contain
blank or malformed lines, at least not when Mercurial edits it.

| check for edited lines in .hgsubstate
|
|   $ echo "foo" >> .hgsubstate
|   $ hg ci -m "Edited .hgsubstate"
|   hg: parse error at .hgsubstate:2: foo
|   [255]
|
| requires this patch:
|
| diff --git a/mercurial/subrepo.py b/mercurial/subrepo.py
| --- a/mercurial/subrepo.py
| +++ b/mercurial/subrepo.py
| @@ -42,9 +42,12 @@
|      rev = {}
|      if '.hgsubstate' in ctx:
|          try:
| -            for l in ctx['.hgsubstate'].data().splitlines():
| -                revision, path = l.split(" ", 1)
| -                rev[path] = revision
| +            for i, l in enumerate(ctx['.hgsubstate'].data().splitlines()):
| +                try:
| +                    revision, path = l.split(" ", 1)
| +                    rev[path] = revision
| +                except ValueError:
| +                    raise error.ParseError(l, ".hgsubstate:%d" % (i + 1))
|          except IOError, err:
|              if err.errno != errno.ENOENT:
|                  raise

test propagation of .hg/projrc file on clone with nested subrepos

  $ cd ..
  $ hg init newouter
  $ cd newouter
  $ echo 'outer = http://example.net/bar' > .hgsub
  $ hg add .hgsub
  $ hg debugsub
  path outer
   source   http://example.net/bar
   revision 
  $ echo '[subpaths]' > .hg/projrc
  $ echo "http://example.net/bar = $TESTTMP/outer" >> .hg/projrc
  $ hg debugsub
  path outer
   source   $TESTTMP/outer
   revision 

  $ hg clone ../outer
  destination directory: outer
  updating to branch default
  projrc settings file updated and applied
  cloning subrepo inner from $TESTTMP/inner
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg commit -m 'Outer commit'
  committing subrepository outer
  $ cat .hgsubstate
  7068a10601482aa6952dbbd410897b1a60ce5449 outer

  $ cd ..
  $ hg clone newouter outer5
  updating to branch default
  projrc settings file updated and applied
  cloning subrepo outer from $TESTTMP/outer
  projrc settings file updated and applied
  cloning subrepo outer/inner from $TESTTMP/inner
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
