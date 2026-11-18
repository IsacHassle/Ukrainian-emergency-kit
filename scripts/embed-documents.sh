#!/bin/bash
# Loads everything in documents/ into the AnythingLLM "Crisis" workspace,
# so the AI can search it (in Swedish or English) and cite its sources.
# Safe to re-run: files already uploaded are skipped, so add new files to
# documents/ (any subfolder) and run this again.
#
# Needs AnythingLLM and Ollama running.
# Run:   bash scripts/embed-documents.sh
# Watch: tail -f logs/embed.log

A=http://localhost:3001/api
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the kit folder (where this repo is)
DOCS="$KIT/documents"
DONE="$KIT/logs/embed-uploaded.txt"
LOG="$KIT/logs/embed.log"
mkdir -p "$KIT/logs"
touch "$DONE"
exec >>"$LOG" 2>&1
echo "=== START $(date)"

curl -sf "$A/ping" >/dev/null || { echo "AnythingLLM is not running. Open it and try again."; exit 1; }

# 1. Upload (parse) every document not uploaded before. Kit guide and brochures first.
find "$DOCS" -maxdepth 1 -type f \( -name '*.pdf' -o -name '*.md' \) > /tmp/crisis-embed-order.$$
find "$DOCS"/library/{"Medical Library","Military Medicine","Water Treatment","Food for Preppers","Knots","NHS Medicines","Post Disaster"} -type f 2>/dev/null >> /tmp/crisis-embed-order.$$
find "$DOCS" -mindepth 1 -type f \( -name '*.pdf' -o -name '*.md' -o -name '*.txt' -o -name '*.docx' \) >> /tmp/crisis-embed-order.$$
awk '!seen[$0]++' /tmp/crisis-embed-order.$$ | while IFS= read -r f; do
  grep -qxF "$f" "$DONE" && continue
  # Quote the name: curl treats commas and semicolons in a bare file name as separators.
  q=${f//\\/\\\\}; q=${q//\"/\\\"}
  if curl -sf -X POST "$A/workspace/crisis/upload" -F "file=@\"$q\"" | grep -q '"success":true'; then
    echo "$f" >> "$DONE"; echo "UPLOADED $(basename "$f")"
  else
    echo "UPLOAD FAILED $(basename "$f")"
  fi
done
rm -f /tmp/crisis-embed-order.$$

# 2. Embed every uploaded document that is not yet in the workspace, in small batches.
python3 - "$A" <<'PY'
import json, sys, time, urllib.request
A = sys.argv[1]
def get(p): return json.load(urllib.request.urlopen(A + p, timeout=120))
def post(p, body):
    req = urllib.request.Request(A + p, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3600))
def all_docs():
    # The API only reports a file count per folder, so list AnythingLLM's storage directly.
    import os
    storage = get("/setup-complete")["results"]["StorageDir"]
    folder = os.path.join(storage, "documents", "custom-documents")
    return sorted("custom-documents/" + n for n in os.listdir(folder) if n.endswith(".json"))
in_ws = {d["docpath"] for d in get("/workspace/crisis")["workspace"].get("documents", [])}
todo = [d for d in all_docs() if d not in in_ws]
print(f"to embed: {len(todo)} (already embedded: {len(in_ws)})", flush=True)
for i in range(0, len(todo), 20):
    batch = todo[i:i + 20]
    try:
        post("/workspace/crisis/update-embeddings", {"adds": batch, "deletes": []})
    except Exception as e:
        print("batch error:", e, flush=True)
    for _ in range(120):  # wait for the batch to land before sending the next
        n = len(get("/workspace/crisis")["workspace"].get("documents", []))
        if n >= len(in_ws) + i + len(batch): break
        time.sleep(5)
    print(f"embedded {min(i + 20, len(todo))}/{len(todo)} (workspace now {n})", flush=True)
PY
echo "=== DONE $(date)"
