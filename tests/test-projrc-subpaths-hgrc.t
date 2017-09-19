explicitly test how ~/.hgrc interacts with .hg/projrc in the context
of remapping subrepository paths

setup HOME, unset HGRCPATH

  $ HOME=$TESTTMP
  $ export HOME
  $ unset HGRCPATH

load extension

  $ echo "[extensions]" >> $HOME/.hgrc
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HOME/.hgrc

  $ echo "[projrc]" >> $HOME/.hgrc
  $ echo "include = *" >> $HOME/.hgrc
  $ echo "servers = *" >> $HOME/.hgrc
  $ echo "confirm = False" >> $HOME/.hgrc

setup repository

  $ hg init repo
  $ cd repo

  $ hg init inner
  $ cd inner
  $ touch inner
  $ hg add inner
  $ hg commit -m inner
  $ cd ..

  $ echo "inner = inner" > .hgsub
  $ hg add .hgsub
  $ hg commit -m outer
  committing subrepository inner
  $ cd ..

clone without any remapping -- works:

  $ hg clone repo repo1
  updating to branch default
  cloning subrepo inner from $TESTTMP/repo/inner
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved

clone with bad .hg/projrc -- this does not work and confirms that the
[subpaths] settings in the .hg/projrc file affect the paths in .hgsub:

  $ echo "[subpaths]" >> repo/.hg/projrc
  $ echo "inner = no-such-path" >> repo/.hg/projrc
  $ hg clone repo repo2
  updating to branch default
  projrc settings file updated and applied
  abort: repository $TESTTMP/repo/no-such-path not found!
  [255]

clone with ~/.hgrc -- this also fails and shows that the settings in
~/.hgrc are loaded after the settings from .hg/projrc and that the
path is rewritten 'inner' -> 'no-such-path' -> 'some-such-path':

  $ echo "[subpaths]" >> $HOME/.hgrc
  $ echo "^no-such = some-such" >> $HOME/.hgrc
  $ hg clone repo repo3
  updating to branch default
  projrc settings file updated and applied
  abort: repository $TESTTMP/repo/no-such-path not found!
  [255]
