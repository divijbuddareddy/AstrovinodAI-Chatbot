"""Build app/places_india.tsv.gz from GeoNames IN.txt (CC BY 4.0). Run: python -I build_places.py IN.txt out.tsv.gz"""
import csv, gzip, re, sys
src, out = sys.argv[1], sys.argv[2]
ok = re.compile(r"^[a-z][a-z .'-]{1,60}$")
rows, n_alt = [], 0
with open(src, encoding="utf-8") as f:
    for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
        if r[6] != "P" or r[7] in ("PPLH", "PPLQ", "PPLW"):  # populated places; skip historical/abandoned/destroyed
            continue
        name = r[2].strip() or r[1].strip()
        if not name:
            continue
        alts = sorted({a.strip().lower() for a in r[3].split(",") if ok.match(a.strip().lower() or "")} - {name.lower()})
        n_alt += len(alts)
        rows.append((name, r[10], f"{float(r[4]):.4f}", f"{float(r[5]):.4f}", r[14] or "0", "|".join(alts)))
with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as g:
    for row in rows:
        g.write("\t".join(row) + "\n")
print(len(rows), "places,", n_alt, "alternate names")
