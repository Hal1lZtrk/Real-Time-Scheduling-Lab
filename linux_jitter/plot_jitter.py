"""Histogram + time series of one or more jitter.c outputs.

    python plot_jitter.py lat_normal.csv lat_fifo_load.csv -o jitter.png
"""

import argparse
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def read(path):
    with open(path, newline="") as fh:
        return [int(row["latency_us"]) for row in csv.DictReader(fh)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("-o", "--output", default="jitter.png")
    args = ap.parse_args()
    data = {os.path.splitext(os.path.basename(p))[0]: read(p) for p in args.csv}

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.8))
    for name, lat in data.items():
        a.plot(lat, linewidth=0.6, label=f"{name} (max {max(lat)} us)")
        b.hist(lat, bins=60, alpha=0.6, label=name, log=True)
    a.set_xlabel("cycle")
    a.set_ylabel("wake-up latency (us)")
    a.set_title("Latency per cycle", loc="left", fontweight="bold")
    b.set_xlabel("wake-up latency (us)")
    b.set_ylabel("cycles (log scale)")
    b.set_title("Distribution", loc="left", fontweight="bold")
    a.legend(fontsize=8, frameon=False)
    for ax in (a, b):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(args.output, dpi=160)
    print("written", args.output)


if __name__ == "__main__":
    main()
