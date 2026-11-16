"""Print the shape of a JSON data file (keys, types, sizes) without interpreting it. python3 -I inspect_json.py FILE [depth]"""
import json, sys
def show(x, depth, ind=""):
    if isinstance(x, dict):
        print(f"{ind}dict[{len(x)}]")
        if depth <= 0: return
        for i, (k, v) in enumerate(x.items()):
            if i >= 6: print(f"{ind}  ... ({len(x)-6} more keys: {list(x)[6:12]})"); break
            print(f"{ind}  {k!r}:", end=" "); show(v, depth - 1, ind + "    ")
    elif isinstance(x, list):
        print(f"{ind}list[{len(x)}]" + (f" e.g. {json.dumps(x[:4])[:160]}" if x and not isinstance(x[0], (dict, list)) else ""))
        if x and isinstance(x[0], (dict, list)) and depth > 0: show(x[0], depth - 1, ind + "    ")
    else:
        print(f"{ind}{type(x).__name__}: {str(x)[:120]}")
show(json.load(open(sys.argv[1])), int(sys.argv[2]) if len(sys.argv) > 2 else 4)
