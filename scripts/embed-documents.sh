#!/bin/bash
# Loads everything in documents/ into the AnythingLLM Book index workspace named in the country config
# (ai.workspace), so the AI can search it and cite its sources.
# Safe to re-run: files already uploaded are skipped, so add new files to
# documents/ (any subfolder) and run this again.
# AnythingLLM keeps every uploaded file in one store shared by all its workspaces (another kit's, on a Mac that has
# two). So this script remembers where AnythingLLM put each file it uploaded (logs/embed-uploaded.txt, one
# "file<TAB>location<TAB>checksum" line each) and embeds only those, never whatever else is in the store.
# The checksum is how a Book that changed is found (Update): it is uploaded again, and the old copy is taken out of
# this kit's workspace (only the locations this script itself recorded, never another kit's documents).
#
# Needs AnythingLLM and Ollama running.
# Run:   bash scripts/embed-documents.sh
# Watch: tail -f logs/embed.log

A=http://${EK_ANYTHINGLLM:-localhost:3001}/api   # EK_ANYTHINGLLM: where the tests put a stand-in
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the kit folder (where this repo is)
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
WORKSPACE=$(country ai.workspace)
DOCS="$KIT/documents"
DONE="$KIT/logs/embed-uploaded.txt"
LOG="$KIT/logs/embed.log"
mkdir -p "$KIT/logs"
touch "$DONE"
exec >>"$LOG" 2>&1
echo "=== START $(date)"

curl -sf "$A/ping" >/dev/null || { echo "AnythingLLM is not running. Open it and try again."; exit 1; }

# 1. Upload (parse) every document not uploaded before. Kit guide and brochures first.
find "$DOCS" -maxdepth 1 -type f \( -name '*.pdf' -o -name '*.md' \) > /tmp/embed-order.$$
find "$DOCS"/library/{"Medical Library","Military Medicine","Water Treatment","Food for Preppers","Knots","NHS Medicines","Post Disaster"} -type f 2>/dev/null >> /tmp/embed-order.$$
find "$DOCS" -mindepth 1 -type f \( -name '*.pdf' -o -name '*.md' -o -name '*.txt' -o -name '*.docx' \) >> /tmp/embed-order.$$
# Only Ukrainian Official Guides go into the index: the guides of another language are saved in a subfolder named by
# the language code (scripts/fetch-pages.py, "indexed: false" in its saved.json), and are left out here.
GUIDES="$DOCS/$(country official_guides.folder)"
# AnythingLLM's document store (where it keeps what is uploaded)
STORE=$(curl -s "$A/setup-complete" | python3 -c 'import json,sys; print(json.load(sys.stdin)["results"]["StorageDir"])')/documents/custom-documents
awk '!seen[$0]++' /tmp/embed-order.$$ | while IFS= read -r f; do
  case "$f" in "$GUIDES"/?*/*) continue ;; esac   # a guide in a language subfolder (en/): for reading only
  hash=$(shasum -a 256 "$f" | awk '{print $1}')
  oldloc=$(EK_F=$f awk -F'\t' '$1 == ENVIRON["EK_F"] {print $2; exit}' "$DONE")
  oldhash=$(EK_F=$f awk -F'\t' '$1 == ENVIRON["EK_F"] {print $3; exit}' "$DONE")
  replaced=""
  if [ -n "$oldloc" ]; then
    if [ -z "$oldhash" ]; then   # a line from before checksums: take the file as it is now to be the uploaded one
      EK_F=$f EK_H=$hash awk -F'\t' -v OFS='\t' '$1 == ENVIRON["EK_F"] {$3 = ENVIRON["EK_H"]} {print}' "$DONE" > "$DONE.new" && mv "$DONE.new" "$DONE"
      continue
    fi
    [ "$oldhash" = "$hash" ] && continue
    # The Book changed: forget the old upload (its location is taken out of the workspace below) and upload it again.
    EK_F=$f awk -F'\t' '$1 != ENVIRON["EK_F"]' "$DONE" > "$DONE.new" && mv "$DONE.new" "$DONE"
    echo "$oldloc" >> /tmp/embed-deletes.$$
    replaced=1
  fi
  # Quote the name: curl treats commas and semicolons in a bare file name as separators.
  q=${f//\\/\\\\}; q=${q//\"/\\\"}
  # The reply says only "success", so find the file in the store: the one just written there.
  mark=$(python3 -c 'import time; print(time.time())')
  curl -sf -X POST "$A/workspace/$WORKSPACE/upload" -F "file=@\"$q\"" | grep -q '"success":true' || { echo "UPLOAD FAILED $(basename "$f")"; continue; }
  loc=$(python3 - "$STORE" "$mark" <<'PY'
import os, sys
folder, mark = sys.argv[1], float(sys.argv[2])
new = [(os.path.getmtime(os.path.join(folder, n)), n) for n in os.listdir(folder) if n.endswith(".json")]
new = [x for x in new if x[0] >= mark - 1]
print("custom-documents/" + max(new)[1] if new else "")
PY
)
  if [ -n "$loc" ]; then
    printf '%s\t%s\t%s\n' "$f" "$loc" "$hash" >> "$DONE"; echo "$([ -n "$replaced" ] && echo REPLACED || echo UPLOADED) $(basename "$f")"
  else
    echo "UPLOAD FAILED $(basename "$f")"
  fi
done
rm -f /tmp/embed-order.$$
touch /tmp/embed-deletes.$$

# 2. Embed every uploaded document that is not yet in the workspace, in small batches.
python3 - "$A" "$WORKSPACE" "$DONE" /tmp/embed-deletes.$$ <<'PY'
import json, sys, time, urllib.request
A, WS, DONE, DELETES = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def get(p): return json.load(urllib.request.urlopen(A + p, timeout=120))
def post(p, body):
    req = urllib.request.Request(A + p, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3600))
def all_docs():
    # Only the files this kit uploaded (the store may hold another kit's files too).
    with open(DONE, encoding="utf-8") as f:
        return sorted({l.rstrip("\n").split("\t")[1] for l in f if "\t" in l})
in_ws = {d["docpath"] for d in get("/workspace/" + WS)["workspace"].get("documents", [])}
# Old copies of Books that changed: taken out of this kit's workspace first, only those this script uploaded.
with open(DELETES, encoding="utf-8") as f:
    old = sorted({l.strip() for l in f if l.strip()} & in_ws)
if old:
    try:
        post("/workspace/" + WS + "/update-embeddings", {"adds": [], "deletes": old})
    except Exception as e:
        print("delete error:", e, flush=True)
    for _ in range(120):
        in_ws = {d["docpath"] for d in get("/workspace/" + WS)["workspace"].get("documents", [])}
        if not set(old) & in_ws: break
        time.sleep(5)
    print(f"taken out (changed Books): {len(old)}", flush=True)
todo = [d for d in all_docs() if d not in in_ws]
print(f"to embed: {len(todo)} (already embedded: {len(in_ws)})", flush=True)
for i in range(0, len(todo), 20):
    batch = todo[i:i + 20]
    try:
        post("/workspace/" + WS + "/update-embeddings", {"adds": batch, "deletes": []})
    except Exception as e:
        print("batch error:", e, flush=True)
    for _ in range(120):  # wait for the batch to land before sending the next
        n = len(get("/workspace/" + WS)["workspace"].get("documents", []))
        if n >= len(in_ws) + i + len(batch): break
        time.sleep(5)
    print(f"embedded {min(i + 20, len(todo))}/{len(todo)} (workspace now {n})", flush=True)
PY
rm -f /tmp/embed-deletes.$$
echo "=== DONE $(date)"
