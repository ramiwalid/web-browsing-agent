import matplotlib.pyplot as plt
import numpy as np

# Apply academic styling
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 10,
    'figure.dpi': 300
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

# ==========================================
# CHART 1: Stacked Bar (Outcome Distribution)
# ==========================================
categories = ['DOM Compromise \n(N=101)']
benign_success = [49.5]  # 50 runs
benign_fail = [50.5]     # 51 runs (Pedantic Stall)
asr = [0.0]              # 0 runs

bar_width = 0.5
ax1.bar(categories, benign_success, bar_width, label='Benign Success (CR)', color='#2ca02c', edgecolor='black')
ax1.bar(categories, benign_fail, bar_width, bottom=benign_success, label='Benign Fail (Pedantic Stall)', color='#ff7f0e', edgecolor='black')
ax1.bar(categories, asr, bar_width, bottom=np.add(benign_success, benign_fail), label='Attack Success (ASR-E2E)', color='#d62728', edgecolor='black')

ax1.set_ylabel('Percentage of Runs (%)')
ax1.set_ylim(0, 100)
ax1.set_title('(a) Task Outcome Distribution')
ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=1, frameon=False)

# ==========================================
# CHART 2: Box Plot (Execution Latency)
# ==========================================
# Sampled latency data derived from Promptfoo metrics (in seconds)
latency_success = [86.4, 52.6, 158.9, 155.5, 98.0, 100.6, 130.8, 137.2, 112.5, 121.7, 106.0, 104.5, 108.3, 97.7, 92.8]
latency_fail = [126.8, 156.0, 144.3, 136.1, 105.9, 98.9, 130.9, 131.1, 111.1, 105.6, 100.9, 87.0, 95.5, 94.0, 89.9]

data = [latency_success, latency_fail]
labels = ['Success\n(Form Submitted)', 'Fail\n(Pedantic Stall)']

bplot = ax2.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.5,
                    medianprops=dict(color="black", linewidth=1.5))

# Color the boxes to match the bar chart
colors = ['#2ca02c', '#ff7f0e']
for patch, color in zip(bplot['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

ax2.set_ylabel('Execution Latency (Seconds)')
ax2.set_title('(b) Latency by Outcome')

# Adjust layout and export
plt.tight_layout()
plt.savefig('figure1_eval_metrics.pdf', format='pdf', bbox_inches='tight')
plt.savefig('figure1_eval_metrics.png', format='png', dpi=300, bbox_inches='tight')
plt.close(fig)
