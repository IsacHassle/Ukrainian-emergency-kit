#!/bin/bash
# The parts of the install that read from a Kit Drive (see scripts/make-kit-drive.sh for its layout). install.sh
# calls this when it runs from a Kit Drive: it finds ../kit-drive.json next to the kit/ folder it is in.
#
#   bash scripts/install-from-drive.sh verify <drive folder>        every file against checksums.sha256
#   bash scripts/install-from-drive.sh copy <drive folder> <kit>    the kit and the app installers into <kit>
#   bash scripts/install-from-drive.sh models <drive folder>        the AI models into Ollama's model folder
#
# Nothing here uses the internet. For tests, OLLAMA_MODELS (as Ollama itself reads it) is another model folder than
# ~/.ollama/models, and EK_OLLAMA is where the stand-in Ollama listens.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=say.sh
. "$KIT/scripts/say.sh"
cmd="${1:-}"; DRIVE="${2:-}"

verify() {
  # Checked before anything is copied. The first problem stops it with one line naming the file: a changed file
  # (the sum differs), a missing one (listed, not on the drive) or an extra one (on the drive, not listed).
  # .DS_Store and "._" files are Finder's own and the maker leaves them out of the list too.
  [ -f "$DRIVE/checksums.sha256" ] || { say "Немає файла контрольних сум: checksums.sha256. Диск пошкоджений" "The checksum list is missing: checksums.sha256. The drive is damaged"; exit 1; }
  /usr/bin/python3 - "$DRIVE" <<'PY'
import hashlib, os, re, sys
drive = sys.argv[1]
def stop(uk, en, path):
    print("%s: %s / %s: %s" % (uk, path, en, path))
    sys.exit(1)
listed = {}
with open(os.path.join(drive, "checksums.sha256"), encoding="utf-8") as f:
    for line in f:
        m = re.match(r"([0-9a-f]{64})  (.+?)\n?$", line)
        if m:
            listed[m.group(2)] = m.group(1)
on_drive = set()
for base, _, names in os.walk(drive):
    for n in names:
        rel = os.path.relpath(os.path.join(base, n), drive)
        if rel != "checksums.sha256" and n != ".DS_Store" and not n.startswith("._"):
            on_drive.add(rel)
for rel in sorted(on_drive - set(listed)):
    stop("Зайвий файл на диску", "Extra file on the drive", rel)
for rel in sorted(listed):
    if rel not in on_drive:
        stop("Немає файла", "File missing", rel)
for rel in sorted(listed):
    h = hashlib.sha256()
    with open(os.path.join(drive, rel), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != listed[rel]:
        stop("Файл змінено або пошкоджено", "File changed or damaged", rel)
print("Усі %d файлів у порядку / All %d files are fine" % (len(listed), len(listed)))
PY
}

case "$cmd" in
  verify) verify ;;
  copy)
    # rsync, not cp: exFAT keeps no permissions and times only to 2 seconds, and a second run only fills what is missing.
    mkdir -p "$3" "$3/installers"
    rsync -rt --modify-window=2 "$DRIVE/kit/" "$3/"
    [ -d "$DRIVE/installers" ] && rsync -rt --modify-window=2 "$DRIVE/installers/" "$3/installers/"
    ;;
  models)
    # Without overwriting or removing anything: a model the Mac already has (even one named like ours) stays as it is.
    store="${OLLAMA_MODELS:-$HOME/.ollama/models}"
    mkdir -p "$store"
    rsync -rt --ignore-existing "$DRIVE/models/" "$store/"
    # Ollama reads its folder when asked. Start it if it is not running, then ask it what it has.
    ollama_cmd=$(command -v ollama || echo /Applications/Ollama.app/Contents/Resources/ollama)
    addr=${EK_OLLAMA:-127.0.0.1:11434}
    if ! curl -fs -o /dev/null "http://$addr/api/version"; then
      open -g -a Ollama
      for _ in $(seq 1 60); do curl -fs -o /dev/null "http://$addr/api/version" && break; sleep 1; done
    fi
    listed=$("$ollama_cmd" list 2>/dev/null || true)
    for m in $(/usr/bin/python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["models"]))' "$DRIVE/kit-drive.json"); do
      if ! printf '%s\n' "$listed" | grep -q "^$m"; then
        say "Модель $m не з'явилась у списку Ollama. Відкрийте Ollama і запустіть встановлення знову" "The model $m is not in Ollama's list. Open Ollama and run the installation again"; exit 1
      fi
    done
    say "Моделі ШІ на місці (ollama list)" "The AI models are in place (ollama list)"
    ;;
  *) echo "usage: install-from-drive.sh verify|copy|models <drive folder>" >&2; exit 2 ;;
esac
