"""Minimal client for IonQ's v0.4 REST API, used for the QCUP emulator runs.

The key is read from the environment variable IONQ_API_KEY (or IONQ_KEY, which the wrapper ionq.sh sets from it) and is
never printed or written. Every response is written raw to the evidence folder given as RAW.

Usage (through ionq.sh, which sets IONQ_KEY):
  ionq_api.py get PATH NAME              GET PATH, save as RAW/NAME.json, print a short status line
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = "https://api.ionq.co/v0.4"
RAW = os.environ.get("RAW", os.path.expanduser("~/wai-ci-tools/qcup-emulators/ionq/raw"))


def call(method, path, body=None, timeout=120):
    key = os.environ.get("IONQ_API_KEY") or os.environ["IONQ_KEY"]
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(path if path.startswith("http") else BASE + path, data=data, method=method)
    req.add_header("Authorization", "apiKey " + key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "qcup-emulator-client/1")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                try:
                    return r.status, json.loads(raw or b"null")
                except ValueError:
                    return r.status, {"text": raw.decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            if e.code in (429, 502, 503, 504) and attempt < 4:
                time.sleep(5 * (attempt + 1)); continue
            try:
                return e.code, json.loads(text)
            except ValueError:
                return e.code, {"text": text[:2000]}
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 4:
                time.sleep(5 * (attempt + 1)); continue
            return 0, {"error": str(e)}


def save(name, status, answer, sub=""):
    d = os.path.join(RAW, sub) if sub else RAW
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + ".json")
    with open(p, "w") as f:
        json.dump({"status": status, "answer": answer, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=1)
        f.write("\n")
    os.chmod(p, 0o600)
    return p


if __name__ == "__main__":
    if sys.argv[1] == "get":
        s, a = call("GET", sys.argv[2])
        save(sys.argv[3], s, a)
        print(sys.argv[2], "->", s, (list(a.keys())[:12] if isinstance(a, dict) else type(a).__name__))
