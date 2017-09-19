load extension

  $ echo "[extensions]" >> $HGRCPATH
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HGRCPATH

create extentions

  $ cat > x.py <<EOF
  > import os
  > name = os.path.basename(__file__).rsplit('.', 1)[0]
  > print "1) %s imported" % name
  > def uisetup(ui):
  >     print "2) %s uisetup" % name
  > def extsetup():
  >     print "3) %s extsetup" % name
  > def reposetup(ui, repo):
  >    print "4) %s reposetup" % name
  > EOF

  $ cp x.py y.py
  $ cp x.py z.py

make repository

  $ hg init a
  $ cd a

test overwriting of values

  $ echo "[section]" >> $HGRCPATH
  $ echo "key = HGRCPATH" >> $HGRCPATH
  $ echo "[section]" >> .hg/hgrc
  $ echo "key = .hg/hgrc" >> .hg/hgrc
  $ echo "[section]" >> .hg/projrc
  $ echo "key = .hg/projrc" >> .hg/projrc
  $ hg showconfig section
  section.key=.hg/hgrc

test extension initialization

  $ echo "[extensions]" >> $HGRCPATH
  $ echo "x = $TESTTMP/x.py" >> $HGRCPATH
  $ echo "[extensions]" >> .hg/hgrc
  $ echo "y = $TESTTMP/y.py" >> .hg/hgrc
  $ echo "[extensions]" >> .hg/projrc
  $ echo "z = $TESTTMP/z.py" >> .hg/projrc
  $ hg showconfig extensions
  1) x imported
  1) y imported
  2) x uisetup
  2) y uisetup
  1) z imported
  2) z uisetup
  3) z extsetup
  3) x extsetup
  3) y extsetup
  4) x reposetup
  4) y reposetup
  4) z reposetup
  extensions.z=$TESTTMP/z.py
  extensions.projrc=*/projrc.py (glob)
  extensions.x=$TESTTMP/x.py
  extensions.y=$TESTTMP/y.py

test with ~/.hgrc -- set HOME, unset HGRCPATH

  $ cd ..
  $ HOME=$TESTTMP
  $ export HOME
  $ unset HGRCPATH

load extension

  $ echo "[extensions]" >> $HOME/.hgrc
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HOME/.hgrc
  $ echo "children = " >> $HOME/.hgrc

disable extension in .hg/projrc

  $ hg init b
  $ cd b
  $ echo "[extensions]" > .hg/projrc
  $ echo "children = !" >> .hg/projrc

the ~/.hgrc file overrides the .hg/projrc file, the children extension
is still loaded:

  $ hg showconfig extensions
  extensions.projrc=*/projrc.py (glob)
  extensions.children=
