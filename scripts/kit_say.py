"""One line in both languages for the kit's Python scripts, the same as scripts/say.sh does for shell:
Ukrainian first, then English, separated by " / ". A volunteer who reads either language can follow it.

    from kit_say import say
    say("Завантажую бібліотеки", "Downloading libraries")

Stdlib only; works on the system python3 3.9.
"""
import sys


def line(first, second):
    return "%s / %s" % (first, second)


def say(first, second, file=None, **kw):
    """Prints the two texts as one line (to `file`, stdout unless told)."""
    print(line(first, second), file=file or sys.stdout, **kw)


def die(first, second, code=1):
    """Prints the two texts to stderr and exits with `code`."""
    say(first, second, file=sys.stderr)
    sys.exit(code)
