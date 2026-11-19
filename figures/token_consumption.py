import matplotlib.pyplot as plt
import numpy as np

# Apply academic styling matching Figures 1 & 2
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 9.5,
    'figure.dpi': 300
})

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.8))

# ==========================================================
# PANEL (a): Economic DoS — Billable vs. Cached Tokens
# ==========================================================
conditions = [
    'Baseline\n(N=0)',
    'Sidebar\n(N=500)',
    'Sidebar\n(N=1000)',
    'Top-of-Body\n(N=2000)'
]

# Values in thousands of tokens (k) per run
uncached_k = [50.514, 85.263, 117.064, 393.267]
cached_k = [58.205, 58.205, 58.205, 190.431]
# Sample SD across the 10 Top-of-Body runs (33.7k)
uncached_err = [0, 0, 0, 33.695]
multipliers = ['1.0x', '1.7x', '2.3x', '7.8x']

x = np.arange(len(conditions))
bar_w = 0.55

ax1.bar(
    x, uncached_k, bar_w, yerr=uncached_err, capsize=4,
    label='Billable (Uncached) Tokens', color='#e41a1c',
    edgecolor='black', alpha=0.85, zorder=3
)
ax1.bar(
    x, cached_k, bar_w, bottom=uncached_k,
    label='Cached Prompt Tokens', color='#377eb8',
    edgecolor='black', alpha=0.75, zorder=3
)

# Annotate billable token multiplier above each stacked bar
for i, (u, c, mult) in enumerate(zip(uncached_k, cached_k, multipliers)):
    y_top = u + c + 16
    ax1.text(
        x[i], y_top, f'{mult}\nbillable',
        ha='center', va='bottom', fontsize=9, fontweight='bold', color='#b30000'
    )

ax1.set_xticks(x)
ax1.set_xticklabels(conditions, fontsize=9)
ax1.set_ylabel('Mean Tokens per Run (Thousands)')
ax1.set_ylim(0, 720)
ax1.set_title('(a) Token Amplification (Economic DoS)')
ax1.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#cccccc')
ax1.grid(True, axis='y', linestyle='-', alpha=0.7, zorder=0)
ax1.grid(False, axis='x')

# ==========================================================
# PANEL (b): Execution Latency & Step Inflation
# ==========================================================
side500_lat = [71.986, 22.599, 49.130, 94.795, 90.480]
top2000_lat = [
    73.715, 284.861, 148.703, 216.554, 277.582,
    275.004, 283.925, 292.275, 297.419, 296.069
]

# showfliers=False avoids double-plotting the 73.7s outlier next to the scatter overlay
bplot = ax2.boxplot(
    [side500_lat, top2000_lat],
    positions=[1, 2],
    widths=0.45,
    patch_artist=True,
    showfliers=False,
    medianprops=dict(color='black', linewidth=1.8),
    boxprops=dict(edgecolor='black', linewidth=1),
    whiskerprops=dict(color='black', linewidth=1),
    capprops=dict(color='black', linewidth=1),
    zorder=2
)

for patch, color in zip(bplot['boxes'], ['#4daf4a', '#ff7f00']):
    patch.set_facecolor(color)
    patch.set_alpha(0.75)

# Overlay individual trial latencies with light jitter
rng = np.random.default_rng(42)
ax2.scatter(1 + rng.normal(0, 0.04, len(side500_lat)), side500_lat,
            color='black', s=24, alpha=0.75, zorder=4)
ax2.scatter(2 + rng.normal(0, 0.04, len(top2000_lat)), top2000_lat,
            color='black', s=24, alpha=0.75, zorder=4)

ax2.text(1, max(side500_lat) + 18, 'Mean: 65.8s\n(5.6 steps)',
         ha='center', va='bottom', fontsize=9, fontweight='bold')
ax2.text(2, max(top2000_lat) + 14, 'Mean: 244.6s\n(15.2 steps)',
         ha='center', va='bottom', fontsize=9, fontweight='bold')

ax2.set_xticks([1, 2])
ax2.set_xticklabels(['Sidebar\n(N=500, n=5)', 'Top-of-Body\n(N=2000, n=10)'])
ax2.set_ylabel('Execution Latency (Seconds)')
ax2.set_ylim(0, 360)
ax2.set_title('(b) Latency & Step Inflation')
ax2.grid(True, axis='y', linestyle='-', alpha=0.7, zorder=0)
ax2.grid(False, axis='x')

# ==========================================================
# PANEL (c): Verification Blindness (Double-Booking Hazard)
# ==========================================================
rel_labels = ['Sidebar\n(N=500, n=5)', 'Top-of-Body\n(N=2000, n=10)']
confirmed_pct = [100.0, 80.0]   # task_verified=True & goal_status='completed'
blind_pct = [0.0, 20.0]         # task_verified=True & goal_status='failed' (Rows #7, #10)

x3 = np.arange(len(rel_labels))
ax3.bar(
    x3, confirmed_pct, 0.5,
    label='Booked & Confirmed', color='#4daf4a',
    edgecolor='black', alpha=0.85, zorder=3
)
ax3.bar(
    x3, blind_pct, 0.5, bottom=confirmed_pct,
    label='Booked but Reported Failed\n(Double-Booking Risk)', color='#984ea3',
    edgecolor='black', alpha=0.85, zorder=3
)

ax3.text(0, 50, '100%\n(5/5)', ha='center', va='center', color='white', fontweight='bold', fontsize=10)
ax3.text(1, 40, '80%\n(8/10)', ha='center', va='center', color='white', fontweight='bold', fontsize=10)
ax3.text(1, 90, '20%\n(2/10)', ha='center', va='center', color='white', fontweight='bold', fontsize=10)

ax3.set_xticks(x3)
ax3.set_xticklabels(rel_labels)
ax3.set_ylabel('Percentage of Runs (%)')
ax3.set_ylim(0, 115)
ax3.set_title('(c) Verification Blindness Rate')
ax3.legend(loc='lower center', bbox_to_anchor=(0.5, -0.32), ncol=1, frameon=False)
ax3.grid(True, axis='y', linestyle='-', alpha=0.7, zorder=0)
ax3.grid(False, axis='x')

plt.tight_layout()
plt.savefig('figure3_dom_bloat_dos.png', format='png', bbox_inches='tight')
plt.show()
