# projrc
A utility to parse .hg/projrc (initially forked from aragost)

The below readme is taken from the Aragost site and used under GNU v2

projrc extension
================

This extension makes Mercurial parse ".hg/projrc" for additional
project-specific configuration settings. The file is transferred
on clone and on pull (but never on push), after confirmation by the
user, from a list of servers that must be configured by the user.
For security reasons the user must also select which projrc
configuration settings will be transferred (i.e. no settings are
transferred from any servers by default). The user can also
configure the extension to automatically accept all changes to the
".hg/projrc" file.

This is useful for centralized setups where you want to distribute
configuration settings to all repositories with a minimum amount of
setup. See also the `subrepository remapping plan`__ for a situation
where you can use this.

.. __: http://mercurial.selenic.com/wiki/SubrepoRemappingPlan

The extensions uses the pushkey protocol to transfer the projrc file.
Mercurial changed the encoding of pushkeys between version 1.7 and
1.8. There is support for pre-1.8 server with post-1.8 clients, but
not pre-1.8 clients with post-1.8 servers. If both server and client
are pre-1.8 it is working fine, and also if they both are post-1.8.


Configuration
=============

By default the extension does *not* load the remote projrc file from
*any* server. For security reasons, the user must manually select
which keys of the remote projrc file will be automatically transferred
from the remote repository on clone or on each pull. The user must
also select from which servers the projrc file must be pulled.

The reason for not accepting all remote projrc settings automatically
is that it would be possible to create a malicious projrc file that
would automatically set a hook that would be executed on any mercurial
operation and which would execute any command on the local machine.

Therefore, in order to actually enable the extension you must
configure it to select the servers and the configuration keys that
must be received from those servers. This is done by adding a
"[projrc]" section to one of your local hgrc files, and in that
section configuring the following configuration keys:

* "projrc.servers": Servers to Pull From
* "projrc.include": Included Sections
* "projrc.exclude": Excluded Sections
* "projrc.confirm": Confirmation Settings
* "projrc.updateonincoming": Confirmation Settings for incoming command

These are explained in the following sections.

Servers to Pull From
--------------------

The "projrc.servers" setting lets you control from which servers the
projrc file must be pulled. This setting is a comma separated list of
glob patterns matching the server names of the servers that the projrc
file must be pulled from. Unless the "projrc.servers" key is set,
the projrc file will not be pulled from any server.

To pull the projrc file from all servers, you can set::

  [projrc]
  servers = *

To pull the projrc file from any repo hosted on server
"http://example.com", set::

  [projrc]
  servers = http://example.com/*

Note that the server pattern match considers forward and backward
slashes as different characters.

The patterns in the server list are "expanded" using the local
mercurial "paths" configuration. That is, before matching them against
the pull or clone source, they will be compared to the repository
"paths" that are defined on the "[paths]" section of the local hgrc
files (such as default, default-push, or any other such path). If they
match the pull source will be matched against the corresponding path,
not against the actual path name.

The path name expansion is useful if you want to allow the transfer of
projrc files from clones of clones. Simply add "default" to your
server list and the extension will always update the projrc file when
pulling from the default repository source. Note that you will not get
the projrc file when cloning. Instead you'll get it when you first
pull into the clone. This is a known issue.

There is an additional "especial server" that you can add to your
server list, which is "localhost". If you add localhost to the server
list, you will always get the projrc file when cloning or pulling from
any local repo (where a "local repo" is one that is on the local
machine, whether it is accessed directly through the file system or
through http, https or ssh access to the localhost)

Included Sections
-----------------

The "projrc.include" configuration key lets you control which
sections and which keys must be accepted from the remote projrc files.
The projrc.include key is a comma separated list of glob patterns that
match the section or key names that must be included. Keys names must
be specified with their section name followed by a "." followed by
the key name (e.g. "diff.git").

To allow all sections and all keys you can set::

  [projrc]
  include = *

Using globs it would be possible to receive all the authorization keys
for the bitbucket.com server, for example, by setting::

  [projrc]
  include = auth.bitbucket.com.*

Excluded Sections
-----------------

The "projrc.exclude" setting is similar to the "projrc.include"
setting but it has the opposity effect. It sets an "exclude list" of
settings that must not be transferred from the common projrc files.

The exclude list has the same syntax as the include list. If an
exclusion list is set but the inclusion list is empty or not set all
non excluded keys will be included.

If both an include and an exclude lists are set, and a key matches
both the include and the exclude list, priority is given to the most
explicit key match, in the following order:

- full key, exact matches are considered the most explicit (e.g.
  ui.merge);
- pattern (glob) matches are considered next (e.g.
  "auth.bitbucket.*"), with the longest matching pattern being the
  most explicit;
- section level matches (e.g. "ui");
- global ("*") matches.

If a key matches both an include and an exclude (glob) pattern of the
same length, the key is *included* (i.e. inclusion takes precedence
over exclusion).

The extension excludes the "[projrc]" section by default. This
ensures that a malicious user cannot add a "[projrc]" section to
the remote "projrc" file to override the user's global projrc
settings (e.g. to enable the transfer of the "[hooks]" section).

Confirmation Settings
---------------------

There are two settings that control how and if the user must
confirm updates to the local projrc file:

1. "confirm":

The "projrc.confirm" configuration key controls whether the user
must confirm the transfer of new projr settings.

Valid values are:

:"always" / "True": Always ask for confirmation (this is the
                        default).

:"first": Ask for confirmation when the projrc file is transferred
            for the first time (e.g. on clone).

:"never" / "False": Never ask for confirmation (accept all projrc
                        changes).

Note that you can use any valid mercurial configuration 'boolean'
value in addition to "always" and "never" (i.e. you can use
"yes", "on", "1", "no", "off" and "0").

Also note that if this key is not set, the user will have to confirm all
changes (i.e. "always" is the default setting)

Set this key to "never" if you want to automatically accept all
changes to the project configuration.

Set this key to "first" if you want to only ask for confirmation
when you clone a repo that has a projrc file, or when you pull for the
first time from a repo to which a projrc file has been is added.

Note that if you do not confirm the transfer of the new projrc file
you will be prompted again when you next pull from the same source
(i.e. the extension does not remember your previous answer to the
confirmation prompt).

2. "updateonincoming":

The "projrc.updateonincoming" configuration key controls whether
the user gets a prompt to update the projrc file when it runs the
incoming mercurial command.

Valid values for the "projrc.updateonincoming" configuration key are:

:"never" / "False": Show whether the remote projrc file has changed, 
                        but do not upate (nor ask to update) the local
                        projrc file. This is the default behavior.

:"prompt": Look for changes to the projrc file.
          If there are changes _always_ show a confirmation prompt,
          asking the user if it wants to update its local projrc file.

:"auto": Look for changes to the projrc file.
          Use the value of the 'projrc.confirm' configuration key to
          determine whether to show a confirmation dialog or not
          before updating the local projrc file.

Note that if the field is set but empty the extension will behave as
if it was set to 'prompt'. That is::

  [projrc]
  incoming =

is equivalent to::

  [projrc]
  incoming = prompt


Configuration Examples
----------------------

The following are several configuration examples that will show how to
configure this extension.

Pay especial attention to configuration #3 below , which is probably
the most useful base configuration on a typical corporate environment:

1. Accept all project configurations from all servers, without
   confirmation::

     servers = *
     include = *
     confirm = False

   The least safe configuration for this extension is one that accepts
   all project settings from all servers without any confirmation
   prompt.

2. Accept all project configurations from a central repository
   server::

     servers = http://mycentralserver/*
     include = *
     confirm = False

   Note that with this configuration clones of local clones will *not*
   get the projrc file!

3. Accept all project configurations from a central repo and from
   local repositories::

     servers = http://mycentralserver/*, localhost
     include = *
     confirm = False

   This is probably the most useful base configuration of this
   extension. It ensures that you'll only get the projrc file from a
   central server (e.g. your company's mercurial server) but that you
   will also propagate it to clones of local clones.

4. Accept all project configurations from a central repo and from
   local repositories, but prompt to accept configuration changes::

     servers = http://mycentralserver/*, localhost
     include = *

   This is a safer variation of the previous configuration. The
   difference is that the user will get a confirmation prompt whenever
   the projrc file changes.
   
   You can also configure the incoming command to prompt for changes
   by adding::

     updateonincoming = prompt

5. Accept all project configurations from a central repo and from
   local repositories, but prompt the first time that a projrc file is
   detected::

     servers = http://mycentralserver/*, localhost
     include = *
     confirm = first

   This configuration is not as safe as #4, but is a safer than #3.

6. Accept all project configurations from the default pull sources::

     servers = default
     include = *
     confirm = False

   This makes sure that the projrc file is transferred when pulling
   from the default path, which is usually the one that we cloned
   from. Note that you won't get the projrc file when cloning. You'll
   get it when pulling for the first time.

7. Accept all project configurations except the [hooks] section from
   the default pull sources::

     servers = default
     exclude = hooks
     confirm = False

8. Only get the commit hook from the project configuration file, from
   the central repository, but prompt to accept configuration
   changes::

     servers = http://mycentralserver/*
     include = hooks.commit


Detecting changes to the projrc file
------------------------------------

The extension checks for changes to the remote "projrc" file when
you run the mercurial incoming command, and shows a message if a
change is found.

Security Implications of Using this Extension
=============================================

Although the extension has been designed to be as safe as possible,
enabling and configuring this extension has security implications.

The extension is secure by default, because in order to start
receiving and updating your ".hg/projrc" files you must first
whitelist the servers to transfer the file from and which settings
to transfer.

However you must be careful when including settings from untrusted
sources because some mercurial settings allow a malicious user to
configure mercurial to execute arbitrary code on your machine or
change your local mercurial configuration.

This means that you should only add servers you trust to your
server list, and only include those settings that are strictly
necessary. If you are a system administrator of a central repo that
is meant to distribute a projrc file you should be extra careful
to ensure that nobody modifies the projrc file without your
permission.

Sponsoring
==========

This extension was written by `aragost Trifork`_ for a client. Feel
free to contact `aragost Trifork`_ to discuss any further improvements
to the extension.

Contact
=======

https://bitbucket.org/aragost/projrc



