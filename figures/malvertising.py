import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

# Apply academic styling matching Figure 1
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 10,
    'figure.dpi': 300
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

# ==========================================
# CHART 1: Stacked Bar (Vector Ablation)
# ==========================================
vectors = ['DOM Compromise\n(N=101)', 'Iframe Malvertising\n(N=101)']
benign_success = [49.5, 59.4]
benign_fail = [50.5, 40.6]
asr = [0.0, 0.0]

bar_width = 0.5
x_pos = np.arange(len(vectors))

# Use the exact same styling as Figure 1
ax1.bar(x_pos, benign_success, bar_width, label='Benign Success (CR)', color='#4daf4a', edgecolor='black', zorder=3)
ax1.bar(x_pos, benign_fail, bar_width, bottom=benign_success, label='Benign Fail (Pedantic Stall)', color='#ff7f00', edgecolor='black', zorder=3)
ax1.bar(x_pos, asr, bar_width, bottom=np.add(benign_success, benign_fail), label='Attack Success (ASR-E2E)', color='#e41a1c', edgecolor='black', zorder=3)

ax1.set_xticks(x_pos)
ax1.set_xticklabels(vectors)
ax1.set_ylabel('Percentage of Runs (%)')
ax1.set_ylim(0, 100)
ax1.set_title('(a) Task Outcome Distribution')

# Place legend cleanly below the chart
ax1.legend(loc='lower center', bbox_to_anchor=(0.5, -0.3), ncol=1, frameon=False)
ax1.grid(True, axis='y', linestyle='-', alpha=0.7, zorder=0)
ax1.grid(False, axis='x')

# ==========================================
# CHART 2: Grouped Box Plot (Execution Latency)
# ==========================================
# Sampled latency data derived from Promptfoo metrics
dom_success = [86.4, 52.6, 158.9, 155.5, 98.0, 100.6, 130.8, 137.2, 112.5, 121.7, 106.0, 104.5, 108.3, 97.7, 92.8]
dom_fail = [126.8, 156.0, 144.3, 136.1, 105.9, 98.9, 130.9, 131.1, 111.1, 105.6, 100.9, 87.0, 95.5, 94.0, 89.9]
iframe_success = [69.8, 91.2, 95.6, 96.3, 89.2, 95.9, 101.0, 108.6, 115.4, 126.0, 92.2, 130.1, 95.7, 129.0, 96.2]
iframe_fail = [29.6, 48.1, 94.5, 92.9, 93.0, 98.4, 85.7, 86.6, 95.2, 90.5, 105.5, 88.3, 85.4, 96.9, 111.5]

data = [dom_success, dom_fail, iframe_success, iframe_fail]
positions = [1, 1.6, 3, 3.6]  # Grouped positions on the X-axis

# Use pure matplotlib to guarantee rendering
bplot = ax2.boxplot(data, positions=positions, patch_artist=True, widths=0.5,
                    medianprops=dict(color="black", linewidth=1.5),
                    boxprops=dict(edgecolor='black', linewidth=1),
                    whiskerprops=dict(color='black', linewidth=1),
                    capprops=dict(color='black', linewidth=1),
                    flierprops=dict(marker='o', color='black', markeredgecolor='black'))

# Match colors to the bar chart
colors = ['#4daf4a', '#ff7f00', '#4daf4a', '#ff7f00']
for patch, color in zip(bplot['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.8)

# Center the labels under the grouped boxes
ax2.set_xticks([1.3, 3.3])
ax2.set_xticklabels(['DOM Compromise', 'Iframe Malvertising'])
ax2.set_ylabel('Execution Latency (Seconds)')
ax2.set_title('(b) Latency by Outcome')
ax2.grid(True, axis='y', linestyle='-', alpha=0.7)
ax2.grid(False, axis='x')

# Add custom legend for the boxplot
success_patch = mpatches.Patch(facecolor='#4daf4a', edgecolor='black', label='Success (Form Submitted)')
fail_patch = mpatches.Patch(facecolor='#ff7f00', edgecolor='black', label='Fail (Pedantic Stall)')
ax2.legend(handles=[success_patch, fail_patch], loc='lower center', bbox_to_anchor=(0.5, -0.3), ncol=1, frameon=False)

plt.tight_layout()
plt.savefig('figure2_eval_metrics.png', format='png', dpi=300, bbox_inches='tight')
plt.close(fig)

