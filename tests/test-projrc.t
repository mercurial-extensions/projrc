run doctests

  $ python -m doctest $TESTDIR/../projrc.py

load extension

  $ echo "[extensions]" >> $HGRCPATH
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HGRCPATH
  $ echo "[projrc]" >> $HGRCPATH
  $ echo "include = *" >> $HGRCPATH
  $ echo "servers = *" >> $HGRCPATH
  $ echo "confirm = False" >> $HGRCPATH

test clone with no projrc

  $ hg init empty
  $ hg clone empty also-empty
  updating to branch default
  0 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cat also-empty/.hg/projrc
  cat: also-empty/.hg/projrc: No such file or directory
  [1]

make initial repository

  $ hg init a
  $ cd a
  $ touch a.txt
  $ hg add a.txt
  $ hg commit -m a

create .hg/projrc file

  $ echo "[extensions]" > .hg/projrc
  $ echo "children =" >> .hg/projrc

test reading of .hg/projrc file

  $ hg showconfig extensions
  extensions.children=
  extensions.projrc=*/projrc.py (glob)

check that extension is loaded

  $ hg children

test cloning of .hg/projrc file

  $ cd ..
  $ hg clone a b
  updating to branch default
  projrc settings file updated and applied
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd b
  $ hg showconfig extensions
  extensions.children=
  extensions.projrc=*/projrc.py (glob)

test pull of changes into .hg/projrc file

  $ echo "relink =" >> ../a/.hg/projrc
  $ hg pull
  pulling from $TESTTMP/a
  projrc settings file updated and applied
  searching for changes
  no changes found
  $ hg showconfig extensions
  extensions.children=
  extensions.relink=
  extensions.projrc=*/projrc.py (glob)

test pull of deleted .hg/projrc file

  $ rm ../a/.hg/projrc
  $ hg pull
  pulling from $TESTTMP/a
  searching for changes
  no changes found
  $ hg showconfig extensions
  extensions.children=
  extensions.relink=
  extensions.projrc=*/projrc.py (glob)

test pull of .hg/projrc file with special characters over HTTP

  $ cd ../a
  $ printf "[test]\n" > .hg/projrc
  $ printf "a = x\ty\tz\n" >> .hg/projrc
  $ printf "b = bøf\n" >> .hg/projrc
  $ hg serve -p $HGPORT -d --pid-file ../hg.pid -E ../error.log
  $ cat ../hg.pid >> "$DAEMON_PIDS"
  $ cd ../b
  $ hg pull http://localhost:$HGPORT/
  pulling from http://localhost:$HGPORT/
  projrc settings file updated and applied
  searching for changes
  no changes found
  $ cat .hg/projrc
  #\ projrc encoding check, line must begin with '#\ '
  [test]
  a = x	y	z
  b = b\xf8f (esc)

test pull of broken .hg/projrc file over HTTP

  $ echo 'this is broken' > ../a/.hg/projrc
  $ hg pull http://localhost:$HGPORT/
  pulling from http://localhost:$HGPORT/
  not saving retrieved projrc file: parse error at 'this is broken' on projrc:1
  searching for changes
  no changes found

kill hg serve

  $ "$TESTDIR/killdaemons.py"
  $ cat ../error.log
