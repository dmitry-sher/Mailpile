import getopt
import gettext
import locale
import os
import sys
import traceback

import mailpile.util
import mailpile.config.defaults
from mailpile.commands import COMMANDS, Command, Action
from mailpile.config.manager import ConfigManager
from mailpile.conn_brokers import DisableUnbrokeredConnections
from mailpile.i18n import gettext as _
from mailpile.i18n import ngettext as _n
from mailpile.plugins import PluginManager
from mailpile.plugins.core import Help, HelpSplash, HealthCheck
from mailpile.plugins.core import Load, Rescan, Quit
from mailpile.plugins.motd import MessageOfTheDay
from mailpile.ui import ANSIColors, Session, UserInteraction, Completer
from mailpile.util import *
from time import sleep

_plugins = PluginManager(builtin=__file__)

# This makes sure mailbox "plugins" get loaded... has to go somewhere?
from mailpile.mailboxes import *

# This is also a bit silly, should be somewhere else?
Help.ABOUT = mailpile.config.defaults.ABOUT

# We may try to load readline later on... maybe?
readline = None


##[ Main ]####################################################################


def CatchUnixSignals(session):
    def quit_app(sig, stack):
        Quit(session, 'quit').run()

    def reload_app(sig, stack):
        pass

    try:
        import signal
        if os.name != 'nt':
            signal.signal(signal.SIGTERM, quit_app)
            signal.signal(signal.SIGQUIT, quit_app)
            signal.signal(signal.SIGUSR1, reload_app)
        else:
            signal.signal(signal.SIGTERM, quit_app)
    except ImportError:
        pass


def Interact(session):
    global readline
    is_sandstorm = bool(os.getenv('SANDSTORM', False))
    try:
        import readline as rl  # Unix-only
        readline = rl
    except ImportError:
        pass

    try:
        if readline:
            readline.read_history_file(session.config.history_file())
            readline.set_completer_delims(Completer.DELIMS)
            readline.set_completer(Completer(session).get_completer())
            for opt in ["tab: complete", "set show-all-if-ambiguous on"]:
                readline.parse_and_bind(opt)
    except IOError:
        pass

    # Negative history means no saving state to disk.
    history_length = session.config.sys.history_length
    if readline is None:
        pass  # history currently not supported under Windows / Mac
    elif history_length >= 0:
        readline.set_history_length(history_length)
    else:
        readline.set_history_length(-history_length)

    try:
        prompt = session.ui.term.color('mailpile> ',
                                       color=session.ui.term.BLACK,
                                       weight=session.ui.term.BOLD,
                                       readline=(readline is not None))
        while not mailpile.util.QUITTING:
            try:
                if is_sandstorm:
                    while True:
                        sleep(10)
                        pass
                else:
                    with session.ui.term:
                        session.ui.block()
                        opt = raw_input(prompt).decode('utf-8').strip()
            except KeyboardInterrupt:
                session.ui.unblock(force=True)
                session.ui.notify(_('Interrupted. '
                                    'Press CTRL-D or type `quit` to quit.'))
                continue
            session.ui.term.check_max_width()
            session.ui.unblock(force=True)
            if opt:
                if ' ' in opt:
                    opt, arg = opt.split(' ', 1)
                else:
                    arg = ''
                try:
                    result = Action(session, opt, arg)
                    session.ui.block()
                    session.ui.display_result(result)
                except UsageError, e:
                    session.fatal_error(unicode(e))
                except UrlRedirectException, e:
                    session.fatal_error('Tried to redirect to: %s' % e.url)
    except EOFError:
        print
    finally:
        session.ui.unblock(force=True)

    try:
        if session.config.sys.history_length > 0:
            readline.write_history_file(session.config.history_file())
        else:
            safe_remove(session.config.history_file())
    except (OSError, AttributeError):
        pass


class InteractCommand(Command):
    SYNOPSIS = (None, 'interact', None, None)
    ORDER = ('Internals', 2)
    CONFIG_REQUIRED = False
    RAISES = (KeyboardInterrupt,)

    def command(self):
        session, config = self.session, self.session.config

        session.interactive = True
        if sys.stdout.isatty() and sys.platform[:3] != "win":
            session.ui.term = ANSIColors()

        # Ensure we have a working GnuPG
        self._gnupg().common_args(will_send_passphrase=True)

        # Create and start the rest of the threads, load the index.
        if config.loaded_config:
            Load(session, '').run(quiet=True)
        else:
            config.prepare_workers(session, daemons=True)

        # Note: We do *not* update the MOTD on startup, to keep things
        #       fast, and to avoid leaking our IP on setup, before Tor
        #       has been configured.
        splash = HelpSplash(session, 'help', []).run()
        motd = MessageOfTheDay(session, 'motd', ['--noupdate']).run()
        session.ui.display_result(splash)
        print  # FIXME: This is a hack!
        session.ui.display_result(motd)

        Interact(session)

        return self._success(_('Ran interactive shell'))


class WaitCommand(Command):
    SYNOPSIS = (None, 'wait', None, None)
    ORDER = ('Internals', 2)
    CONFIG_REQUIRED = False
    RAISES = (KeyboardInterrupt,)

    def command(self):
        self.session.ui.display_result(HelpSplash(self.session, 'help', []
                                                  ).run(interactive=False))
        while not mailpile.util.QUITTING:
            time.sleep(1)
        return self._success(_('Did nothing much for a while'))


def Main(args):
    DisableUnbrokeredConnections()

    # Bootstrap translations until we've loaded everything else
    mailpile.i18n.ActivateTranslation(None, ConfigManager, None)
    try:
        # Create our global config manager and the default (CLI) session
        config = ConfigManager(rules=mailpile.config.defaults.CONFIG_RULES)
        session = Session(config)
        cli_ui = session.ui = UserInteraction(config)
        session.main = True
        try:
            CatchUnixSignals(session)
            config.clean_tempfile_dir()
            config.load(session)
        except IOError:
            if config.sys.debug:
                session.ui.error(_('Failed to decrypt configuration, '
                                   'please log in!'))
        HealthCheck(session, None, []).run()
        config.prepare_workers(session)
    except AccessError, e:
        session.ui.error('Access denied: %s\n' % e)
        sys.exit(1)

    try:
        try:
            if '--login' in args:
                a1 = args[:args.index('--login') + 1]
                a2 = args[len(a1):]
            else:
                a1, a2 = args, []

            allopts = []
            for argset in (a1, a2):
                shorta, longa = '', []
                for cls in COMMANDS:
                    shortn, longn, urlpath, arglist = cls.SYNOPSIS[:4]
                    if arglist:
                        if shortn:
                            shortn += ':'
                        if longn:
                            longn += '='
                    if shortn:
                        shorta += shortn
                    if longn:
                        longa.append(longn.replace(' ', '_'))

                opts, args = getopt.getopt(argset, shorta, longa)
                allopts.extend(opts)
                for opt, arg in opts:
                    session.ui.display_result(Action(
                        session, opt.replace('-', ''), arg.decode('utf-8')))
                if args:
                    session.ui.display_result(Action(
                        session, args[0], ' '.join(args[1:]).decode('utf-8')))

        except (getopt.GetoptError, UsageError), e:
            session.fatal_error(unicode(e))

        if (not allopts) and (not a1) and (not a2):
            InteractCommand(session).run()

    except KeyboardInterrupt:
        pass

    except:
        traceback.print_exc()

    finally:
        if readline is not None:
            readline.write_history_file(session.config.history_file())

        # Make everything in the background quit ASAP...
        mailpile.util.LAST_USER_ACTIVITY = 0
        mailpile.util.QUITTING = mailpile.util.QUITTING or True

        if config.plugins:
            config.plugins.process_shutdown_hooks()

        config.stop_workers()
        if config.index:
            config.index.save_changes()
        if config.event_log:
            config.event_log.close()

        session.ui.display_result(Action(session, 'cleanup', ''))

        if session.interactive and config.sys.debug:
            session.ui.display_result(Action(session, 'ps', ''))

        # Remove anything that we couldn't remove before
        safe_remove()

        # Restart the app if that's what was requested
        if mailpile.util.QUITTING == 'restart':
            os.execv(sys.argv[0], sys.argv)


_plugins.register_commands(InteractCommand, WaitCommand)

if __name__ == "__main__":
    Main(sys.argv[1:])
