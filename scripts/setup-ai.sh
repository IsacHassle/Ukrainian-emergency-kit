#!/bin/bash
# Sets up the local AI (nothing leaves the Mac):
#   1. Ollama: downloads the two base models and bge-m3, and builds the country config's two models
#      (ai.models) with the instructions in config/AI-PROMPT.txt
#   2. AnythingLLM: uses Ollama, and gets the Book index workspace named in the country config (ai.workspace)
#      that answers from the books
#   3. Loads every document in documents/ into that workspace (scripts/embed-documents.sh)
# Safe to re-run: finished steps are skipped.
set -eu
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT="$KIT/config/AI-PROMPT.txt"
# shellcheck source=country.sh
. "$KIT/scripts/country.sh"   # the country's facts (config/country.json)
MODEL_MAIN=$(country ai.models.main); MODEL_SMALL=$(country ai.models.small)
BASE_MAIN=$(country ai.base_models.main); BASE_SMALL=$(country ai.base_models.small)
WORKSPACE=$(country ai.workspace); WORKSPACE_NAME=$(country ai.workspace_name)
A=http://localhost:3001/api
OLLAMA=$(command -v ollama || echo /Applications/Ollama.app/Contents/Resources/ollama)

wait_for() {   # url, seconds, what
  for _ in $(seq 1 "$2"); do curl -fs -o /dev/null "$1" && return 0; sleep 1; done
  echo "$3 startade inte. Öppna appen en gång själv och kör sedan installationen igen."; exit 1
}

# 1. Ollama and the models.
open -g -a Ollama
wait_for http://127.0.0.1:11434/api/version 60 "Ollama"
for m in "$BASE_MAIN" "$BASE_SMALL" bge-m3; do
  "$OLLAMA" show "$m" >/dev/null 2>&1 || { echo "Hämtar AI-modellen $m"; "$OLLAMA" pull "$m"; }
done
tmp=$(mktemp -d)
for pair in "$MODEL_MAIN|$BASE_MAIN" "$MODEL_SMALL|$BASE_SMALL"; do
  name=${pair%%|*}; base=${pair#*|}
  printf 'FROM %s\nSYSTEM """\n%s\n"""\nPARAMETER temperature 0.3\n' "$base" "$(cat "$PROMPT")" > "$tmp/Modelfile"
  "$OLLAMA" create "$name" -f "$tmp/Modelfile" >/dev/null 2>&1 && echo "Modellen $name är klar"
done
rm -rf "$tmp"

# 2. AnythingLLM.
open -g -a AnythingLLM
wait_for "$A/ping" 180 "AnythingLLM"
post() { curl -fsS -X POST "$A$1" -H 'Content-Type: application/json' -d "$2" >/dev/null; }
post /system/update-env '{"LLMProvider":"ollama","OllamaLLMBasePath":"http://127.0.0.1:11434","OllamaLLMModelPref":"'"$BASE_MAIN"'","OllamaLLMTokenLimit":"16384","DisableTelemetry":"true"}'
post /system/update-env '{"EmbeddingEngine":"ollama","EmbeddingBasePath":"http://127.0.0.1:11434","EmbeddingModelPref":"bge-m3:latest","EmbeddingModelMaxChunkLength":"8192","OllamaEmbeddingBatchSize":"32","TextSplitterChunkSize":"1200","TextSplitterChunkOverlap":"120"}'
if ! curl -fs "$A/workspace/$WORKSPACE" | grep -q "\"slug\":\"$WORKSPACE\""; then
  post /workspace/new "{\"name\":\"$WORKSPACE_NAME\"}"
fi
python3 - "$A" "$PROMPT" "$WORKSPACE" "$BASE_MAIN" "$WORKSPACE_NAME" <<'PY'
import json, sys, urllib.request
api, prompt, slug, base, name = sys.argv[1], open(sys.argv[2]).read(), sys.argv[3], sys.argv[4], sys.argv[5]
body = {"chatProvider": "ollama", "chatModel": base, "topN": 6, "similarityThreshold": 0.25, "openAiPrompt": prompt}
req = urllib.request.Request(api + "/workspace/" + slug + "/update", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
urllib.request.urlopen(req, timeout=30)
print("AnythingLLM: arbetsytan " + name + " är klar")
PY

# 3. The books.
echo "Läser in dokumenten i AI:n (cirka 40 minuter första gången, förlopp i logs/embed.log)"
bash "$KIT/scripts/embed-documents.sh"
grep -E "embedded|to embed" "$KIT/logs/embed.log" | tail -1
echo "AI:n är klar."
