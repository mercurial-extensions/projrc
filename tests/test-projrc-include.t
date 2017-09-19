
  $ echo "[extensions]" >> $HGRCPATH
  $ echo "projrc = $TESTDIR/../projrc.py" >> $HGRCPATH
  $ echo "[projrc]" >> $HGRCPATH
  $ echo "include = *" >> $HGRCPATH
  $ echo "servers = *" >> $HGRCPATH
  $ echo "confirm = False" >> $HGRCPATH

make initial repository

  $ hg init a
  $ cd a
  $ touch a.txt
  $ hg add a.txt
  $ hg commit -m a

create .hg/projrc file

  $ cat - >> .hg/projrc <<EOM
  > [foo]
  > a = 10
  > b = 100
  > # a small comment
  > %include more-settings
  > [foo]
  > c = 1000
  > a = 10000
  > EOM

  $ cat - >> .hg/more-settings <<EOM
  > [bar]
  > x = Hello
  > y = World
  > [foo]
  > b = Hello
  >     World!
  > EOM
  $ hg showconfig foo
  foo.c=1000
  foo.a=10000
  foo.b=Hello\nWorld!
  $ hg showconfig bar
  bar.x=Hello
  bar.y=World

create clone

  $ cd ..
  $ hg clone a b -q
  $ cd b

  $ cat .hg/projrc
  #\ projrc encoding check, line must begin with '#\ '
  [bar]
  x = Hello
  y = World
  
  [foo]
  b = Hello
    World!
  c = 1000
  a = 10000

  $ hg showconfig foo
  foo.b=Hello\nWorld!
  foo.c=1000
  foo.a=10000
  $ hg showconfig bar
  bar.x=Hello
  bar.y=World

