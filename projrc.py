# projrc.py - .hg/projrc handling
#
# Copyright 2010, 2011 aragost Trifork
# Copyright 2011, 2012 Angel Ezquerra <angel.ezquerra@gmail.com>
#
# This software may be used and distributed according to the terms of
# the GNU General Public License version 2 or any later version.

"""distribute and parse project specific settings

This extension makes Mercurial parse a ``.hg/projrc`` file (if it
exists) for additional configuration settings.

The file is transferred unconditionally on clone and on pull (but
never on push). This makes it very easy for an administrator to
distribute an up-to-date set of configuration settings from a central
repository.
"""

import os, sys, fnmatch
from operator import itemgetter
from mercurial import hg, extensions, pushkey, config, util, error
from mercurial import commands, dispatch, cmdutil, localrepo, exchange
from mercurial.i18n import _

# Compatibility import to handle API changes between 1.8 and 1.9
try:
    from mercurial.scmutil import systemrcpath
    from mercurial.scmutil import userrcpath
except ImportError:
    from mercurial.util import system_rcpath as systemrcpath
    from mercurial.util import user_rcpath as userrcpath

# To handle different encoding with pushkey between Mercurial 1.7 and
# 1.8 the server will send a line beginning with '#\\ ' as the first
# line. This is the default value, and is used if projrc doesn't have
# such a line.
ENCODING_CHECK = "#\\ projrc encoding check, line must begin with '#\\ '\n"

SYSTEMRC = 1
PROJRC = 2
USERRC = 3
HGRC = 4

def classifycfgpath(path):
    """assign sort order to configuration file in path

    >>> classifycfgpath("/etc/mercurial/hgrc")
    1
    >>> classifycfgpath("repo/.hg/projrc")
    2
    >>> classifycfgpath(util.expandpath("~/.hgrc"))
    3
    >>> classifycfgpath("repo/.hg/hgrc")
    4
    """
    path = path.rsplit(":", 1)[0]
    if path in classifycfgpath.systemrcpath:
        return SYSTEMRC
    if util.pconvert(path).endswith(".hg/projrc"):
        return PROJRC
    if path in userrcpath():
        return USERRC
    # .hg/hgrc, file in $HGRCPATH, or an included file
    return HGRC
# Use a function attribute to compute this value only once.
classifycfgpath.systemrcpath = systemrcpath()

def isfilepath(pth):
    """True if a path is not an http, https or ssh path"""
    return (pth[1:2] == ':') or (pth[0:1] in '\\/')

def islocalpath(pth):
    """Return true for local paths

    A local path is a file path that is not a network path or a URL address whose server is locahost or 127.0.0.1
    """
    if isfilepath(pth):
        return (pth[1:2] not in '\\/')
    else:
        try:
            protocol, pth = pth.split('//')
            return pth.split('/')[0] in ('localhost', '127.0.0.1')
        except ValueError:
            return False
    return False

def findpatternmatch(searchtext, patternlist):
    """Find whether a string matches any of the glob patterns on a pattern list

    This function returns 3 values:
        patmatch: True if there is a match
        exactmatch: True if the match is exact (i.e. one of the "patterns"
                    is identical to the the search text)
        matchedpattern: The first pattern that matched the search text

    Note that the function searches for exact matches first, and if no exact
    match is found it searches for pattern matches.

    Also note that the matches are not case sensitive.
    """
    patmatch = False
    exactmatch = False
    matchedpattern = None

    searchtext = searchtext.lower()

    # Search for exact maches first
    for pat in patternlist:
        if searchtext == pat.lower():
            return True, True, pat

    # No exact match was found
    for pat in patternlist:
        if fnmatch.fnmatch(searchtext, pat.lower()):
            patmatch = True
            matchedpattern = pat
            break

    return patmatch, exactmatch, matchedpattern

def serializeconfig(conf, includedkeys='*', excludedkeys=''):
    """turn a config object into a string

    It is possible to optionally filter the configuration to only include
    or exclude some of the keys or sections.

    Note that if that an exclusion list is set but the inclusion list is empty
    all non excluded keys will be included.

    If both an inclusion and an exclusion lists are provided,
    priority is given to the most explicit match. That is,
    full key, exact matches are more explicit than pattern (glob) matches;
    the longest pattern match is considered more explicit;
    pattern matches are more explicit than section level matches; and
    section level matches are more explicit than global ("*") matches.

    If a key is found both on the include and the exclude list with
    the same level of "explicitness", the key is _included_
    (i.e. inclusion takes precedence over exclusion)

    >>> conf = config.config()
    >>> data = '''
    ... [foo]
    ... x = y
    ... z = w
    ... # a comment
    ... %unset x
    ... [bar]
    ... a = 10
    ... b = multi
    ...     line
    ...     value!
    ... [foo]
    ... x = xxx
    ... '''
    >>> conf = config.config()
    >>> conf.parse('projrc', data)
    >>> data2 = serializeconfig(conf)
    >>> print data2
    [bar]
    a = 10
    b = multi
      line
      value!
    <BLANKLINE>
    [foo]
    z = w
    x = xxx
    <BLANKLINE>
    >>> conf2 = config.config()
    >>> conf2.parse('projrc', data2)
    >>> conf2.sections()
    ['bar', 'foo']
    >>> conf2.items('bar')
    [('a', '10'), ('b', 'multi\\nline\\nvalue!')]
    >>> conf2.items('foo')
    [('z', 'w'), ('x', 'xxx')]
    """

    if excludedkeys and not includedkeys:
        # If the excluded keys are specified but the allowed ones are not,
        # assume that all non excluded keys are allowed
        includedkeys = '*'

    includeall = '*' in includedkeys or '*.*' in includedkeys
    # We don't need to define an equivalent "excludeall" because we exclude
    # all keys by default

    lines = []
    for section in conf:
        foundsectionkey = False
        includesection = (section + '.*').lower() in includedkeys
        excludesection = (section + '.*').lower() in excludedkeys

        for key, val in conf.items(section):
            fullkey = '%s.%s' % (section.lower(), key.lower())
            includekey, exactinclude, matchedinclude = findpatternmatch(fullkey, includedkeys)
            excludekey, exactexclude, matchedexclude = findpatternmatch(fullkey, excludedkeys)

            # Should we include the setting?
            # In particular, should we include a setting if it matches both
            # an include and an exclude pattern?:
            # 1. Priority is given to the most explicit match:
            #    Full key, exact matches are more explicit than
            #    pattern (glob) matches.
            #    The longest pattern match is considered more explicit.
            #    Pattern matches are more explicit than section level matches.
            #    Section level matches are more explicit than global ("*") matches
            # 2. If a key is found both on the include and the exclude list with
            #    the same level of "explicitness", the key is _included_
            #    (i.e. inclusion takes precedence over exclusion)
            if includekey and excludekey:
                # Either make includekey true and excludekey false,
                # or make includekey false and excludekey true
                if exactinclude == exactexclude:
                    # if both matches are exact or both are inexact,
                    # include the key unless its match is shorter
                    includekey = (matchedinclude >= matchedexclude)
                else:
                    includekey = exactinclude
                excludekey = not includekey

            if includekey or \
                    (not excludekey and \
                        (includesection or \
                            (not excludesection and includeall)
                        )
                    ):
                if not foundsectionkey:
                    lines.append("[%s]" % section)
                    foundsectionkey = True
                lines.append("%s = %s" % (key, val.replace('\n', '\n  ')))

        if foundsectionkey:
            lines.append('')

    # for final newline
    if not lines:
        lines.append('')

    return "\n".join(lines)

def getallowedkeys(ui):
    """Get a set of the keys that we are allowed to get from the remote projrc file"""
    def parsekeylist(configlist):
        keyset = set()
        for config in set(configlist):
            fullkey = config.strip().lower()
            section = fullkey.split('.')[0]
            if section == fullkey:
                # The whole section is allowed
                fullkey = fullkey + '.*'
            keyset.add(fullkey)
        return keyset

    configlist = ui.configlist('projrc', 'include')
    includedkeys = parsekeylist(configlist)

    configlist = ui.configlist('projrc', 'exclude')
    # By default we exclude all projrc related settings
    # This makes it impossible for a rogue admin to modify the projrc settings
    # (such as the include and exclude lists), which has serious safety implications
    configlist += ['projrc.*']
    excludedkeys = parsekeylist(configlist)

    return includedkeys, excludedkeys

def loadprojrc(ui, projrc, root):
    if not os.path.exists(projrc):
        return
	
    cfg = ui._data(untrusted=False)

    pui = ui.copy()
    pui.readconfig(projrc, root)
    pcfg = pui._data(untrusted=False)

    # Add settings from projrc file if the key is not already loaded
    # by a later file.
    for section in pcfg:
        for key, value in pcfg.items(section):
            src = pcfg.source(section, key)
            if key not in cfg[section] or classifycfgpath(src) < PROJRC:
                cfg.set(section, key, value, src)

    # Sort settings to simulate correct load order. ui.walkconfig is
    # almost what we want, but it runs str on all values and replaces
    # \n with \\n for some reason.
    for section in cfg:
        items = []
        for key, value in cfg.items(section):
            src = cfg.source(section, key)
            items.append((classifycfgpath(src), key, value, src))
        # sort the config items according to their cfg file priority
        items.sort(key=itemgetter(0)) # list.sort implements a stable sort
        for order, key, value, src in items:
            cfg.set(section, key, value, src)

def readcurrentprojrc(repo):
    """Return the contents of the current projrc file"""
    try:
        fp = repo.opener('projrc', 'r')
        data = fp.read()
        fp.close()
    except IOError:
        data = ""
    return data

def readprojrc(ui, rpath):
    # Modelled after dispatch._getlocal but reads the projrc settings
    # directly into the ui object.
    try:
        wd = os.getcwd()
    except OSError, e:
        raise util.Abort(_("error getting current working directory: %s") %
                         e.strerror)
    path = cmdutil.findrepo(wd) or ""
    if path:
        loadprojrc(ui, os.path.join(path, ".hg", "projrc"), path)

    if rpath:
        path = ui.expandpath(rpath[-1])
        loadprojrc(ui, os.path.join(path, ".hg", "projrc"), path)

def getprojrcserverset(ui):
    """Get the list of projrc servers, normalizing paths and character cases"""
    serverlist = ui.configlist('projrc', 'servers')

    for n, server in enumerate(serverlist):
        server = ui.expandpath(server)
        filepath = isfilepath(server)
        if filepath:
            serverlist[n] = os.path.normcase(util.normpath(server))
        else:
            serverlist[n] = server.lower()
    return set(serverlist)

def getremoteprojrc(ui, repo, other):
    """
    Get the contents of a remote projrc and check that they are valid
    
    This function returns a 2-element tuple:
    - The projrc contents as a string (or None if no projrc was found)
    - A boolean indicating whether the data is valid.
    
    Note that it is possible to return (None, True), which simply means
    that no data matching the projrc filter settings was found.
    """
    if not repo.local():
        return None, True

    # Get the list of repos that we are supposed to get a projrc file from
    # (i.e. the projrc "servers")
    projrcserverset = getprojrcserverset(ui)

    try:
        remotepath = other.root
        remotepath = os.path.normcase(util.normpath(remotepath))
    except:
        # Non local repos have no root property
        remotepath = other.url()
        if remotepath.startswith('file:'):
            remotepath = remotepath[5:]

    if '*' not in projrcserverset and \
            not findpatternmatch(remotepath, projrcserverset)[0] and \
            not ("localhost" in projrcserverset and islocalpath(remotepath)):
        # The pull source is not on the projrc server list
        # Note that we keep any existing local projrc file, which may have been
        # transferred from another valid server
        return None, True

    # Get the list of remote keys that we must load from the remote projrc file
    includedkeys, excludedkeys = getallowedkeys(ui)
    if includedkeys or excludedkeys:
        projrc = other.listkeys('projrc')
    else:
        # There are no remote keys to load
        projrc = {} # This ensures that any existing projrc file will be deleted

    data = None
    valid = True
    if 'data' in projrc:
        data = projrc['data'].decode('string-escape')
        if data.startswith("#\\\\ "):
            data = data.decode('string-escape')
        # verify that we can parse the file we got, and filter it according
        # to the local projrc extension settings
        try:
            c = config.config()
            c.parse('projrc', data)
            # Filter the received config, only allowing the sections that
            # the user has specified in any of its hgrc files
            data = ENCODING_CHECK + \
                serializeconfig(c, includedkeys, excludedkeys)
        except error.ParseError, e:
                ui.warn(_("not saving retrieved projrc file: "
                          "parse error at '%s' on %s\n") % e.args)
                valid = False
    return data, valid

def transferprojrc(ui, repo, other, confirmupdate=None):
    data, valid = getremoteprojrc(ui, repo, other)
    if not valid or data is None:
        return

    if data != "":
        # Compare the old projrc with the new one
        try:
            if hasattr(localrepo, 'localpeer'):
                # hg >= 2.3
                repo = repo.local()
            olddata = readcurrentprojrc(repo)

            if olddata != data:
                def mustconfirm(projrcexists):
                    """Read the projrc.confirm setting.

                    Valid values are:
                    - true: Always ask for confirmation
                    - first: Ask for confirmation when the projrc file
                             is transferred for the first time
                    - false: Do not ask for confirmation
                             (i.e. accept all projrc changes)

                    Note that you can use any valid 'boolean' value
                    instead of true and false (i.e. always, yes, on or 1
                    instead of true and never, no, off or 0 instead of false)
                    """
                    confirmchanges = ui.config(
                        'projrc', 'confirm', default=True)

                    if isinstance(confirmchanges, bool):
                        return confirmchanges
                    confirm = util.parsebool(confirmchanges)
                    if not confirm is None:
                        return confirm
                    confirmchanges = confirmchanges.lower()
                    if projrcexists and confirmchanges == "first":
                        return False
                    return True

                if confirmupdate is None:
                    confirmupdate = mustconfirm(olddata != "")
                acceptnewconfig = True
                if confirmupdate:
                    confirmmsg = \
                        _("The project settings file (projrc) has changed.\n"
                        "Do you want to update it? (y/n)")
                    YES = _('&Yes')
                    NO = _('&No')
                    try:
                        # hg < 2.7
                        action = ui.promptchoice(confirmmsg,
                            (YES, NO), default=0)
                    except TypeError, ex:
                        # hg >= 2.7+
                        action = ui.promptchoice(confirmmsg \
                            + _(" $$ %s $$ %s") % (YES, NO), default=0)
                    acceptnewconfig = (action == 0)
                if acceptnewconfig:
                    # If there are changes and the user accepts them, save the new projrc
                    fp = repo.opener('projrc', 'w')
                    fp.write(data)
                    fp.close()

                    # and take any transferred settings into account
                    try:
                        loadprojrc(repo.ui, repo.join('projrc'), repo.root)
                        extensions.loadall(repo.ui)
                        ui.status(_("projrc settings file updated and applied\n"))
                    except IOError:
                        ui.warn(_("projrc settings file updated but could not be applied\n"))

        except error.ParseError, e:
            ui.warn(_("not saving retrieved projrc file: "
                      "parse error at '%s' on %s\n") % e.args)
    else:
        if os.path.exists(repo.join('projrc')):
            os.unlink(repo.join('projrc'))

def clone(orig, ui, *args, **kwargs):
    # hg.clone calls hg._update as the very last thing. We need to
    # transfer the .hg/projrc file before this happens in order for it
    # to take effect for things like subrepos. We do this by wrapping
    # hg._update in our own function that just stores the target
    # revision for later.

    uprev = [None]
    def update(orig, repo, node):
        uprev[0] = node

    origupdate = extensions.wrapfunction(hg, 'update', update)
    hg._update = hg.update
    src, dst = orig(ui, *args, **kwargs)
    hg.update = origupdate
    hg._update = hg.update

    transferprojrc(ui, dst, src)

    # We then do the update, if necessary.
    if uprev[0]:
        dstrepo = dst
        if hasattr(localrepo, 'localpeer'):
            # hg >= 2.3
            dstrepo = dst.local()
        origupdate(dstrepo, uprev[0])
    return src, dst

def incoming(orig, ui, repo, srcpath, *args, **kwargs):
    """
    execute the regular hg.incoming, and then read
    the projrc.updateonincoming setting. Depending on its
    value the behavior will be different:
    
    - false / never: Show whether the remote projrc file
          has changed, but do not upate (nor ask to update)
          the local projrc file.
          This is the default.
    - prompt: Look for changes to the projrc file.
          If there are changes _always_ show a confirmation
          prompt, asking the user if it wants to update its
          local projrc file.
    - auto: Look for changes to the projrc file.
          Use the value of the 'projrc.confirm' configuration
          key to determine whether to show a confirmation
          dialog or not before updating the local projrc file.

    Note that if the field is set but empty the extension
    will behave as if it was set to 'prompt'.
    """

    res = orig(ui, repo, srcpath, *args, **kwargs)

    expandedpath = ui.expandpath(srcpath)

    if hasattr(localrepo, 'localpeer'):
        # hg >= 2.3
        other = hg.peer(repo, {}, expandedpath)
        localother = other.local()
        if localother is not None:
            other = localother
    else:
        # hg < 2.3
        other = hg.repository(ui, expandedpath)

    def mustupdateonincoming():
        default = 'false'
        updateonincoming = ui.config('projrc', 'updateonincoming',
            default=default)
        if (updateonincoming == ''):
            # prompt for confirmation when the field is set but empty
            # The reason is that it is reasonable for a user to expect
            # to be ableto update the projrc file when it sets
            # a field called 'updateonincoming'
            return 'prompt'
        if util.parsebool(updateonincoming) == False:
            # we don't want to get here when None!
            return 'false'
        updateonincoming = updateonincoming.lower()
        if not updateonincoming in ('auto', 'prompt'):
             ui.warn(_('invalid projrc.updateonincoming value (%s).\n'
                'using default projrc.updateonincoming value instead '
                '(%s)\n' % (updateonincoming, default)))
             return default
        return updateonincoming

    updateonincoming = mustupdateonincoming()
    if updateonincoming == 'false':
        # Show whether the projrc file has changed, but do not
        # update nor prompt the user to update the local projrc file
        olddata = readcurrentprojrc(repo)
        if olddata:
            ui.note(_('searching for changes to the projrc file\n'))
        else:
            ui.note(_('looking for remote projrc file\n'))

        data, valid = getremoteprojrc(ui, repo, other)
        if valid:
            # If not valid we will already have shown a warning message
            if olddata:
                if olddata != data:
                    ui.status(_('remote and local projrc files are different\n'))
                else:
                    ui.note(_('no changes found to projrc file\n'))
            elif data:
                ui.status(_('new remote projrc file found\n'))
    else:
        confirmupdate = True
        if updateonincoming == 'auto':
            confirmupdate = None
        transferprojrc(ui, repo, other, confirmupdate=confirmupdate)

    return res

def pull(orig, repo, remote, *args, **kwargs):
    transferprojrc(repo.ui, repo, remote)
    return orig(repo, remote, *args, **kwargs)
    
def pushprojrc(repo, key, old, new):
    return False

def listprojrc(repo):
    if os.path.exists(repo.join('projrc')):
        try:
            conf = config.config()
            conf.read(repo.join('projrc'))
            data = ENCODING_CHECK + serializeconfig(conf)
        except error.ParseError, e:
            # Send broken file to client so that it can detect and
            # report the error there.
            print "error"
            data = repo.opener('projrc').read()
        return {'data': data.encode('string-escape')}
    else:
        return {}

def extsetup(ui):

    # Modelled after dispatch._dispatch. We have to re-parse the
    # arguments to find the path to the repository since there is no
    # repo object yet.
    args = sys.argv[1:]
    rpath = dispatch._earlygetopt(["-R", "--repository", "--repo"], args)
    readprojrc(ui, rpath)
    extensions.loadall(ui)
    for name, module in extensions.extensions():
        if name in dispatch._loaded:
            continue
        cmdtable = getattr(module, 'cmdtable', {})
        overrides = [cmd for cmd in cmdtable if cmd in commands.table]
        if overrides:
            ui.warn(_("extension '%s' overrides commands: %s\n")
                    % (name, " ".join(overrides)))
        commands.table.update(cmdtable)
        dispatch._loaded.add(name)

    extensions.wrapfunction(hg, 'clone', clone)
    extensions.wrapfunction(hg, 'incoming', incoming)
    extensions.wrapfunction(exchange, 'pull', pull)
    pushkey.register('projrc', pushprojrc, listprojrc)
