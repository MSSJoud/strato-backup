# Let's define the structure of a single Swin Transformer Block in pseudocode.
# This will help explain what each block does during each of the 6/10/8 repetitions.

import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_swin_block_diagram():
    fig, ax = plt.subplots(figsize=(10, 4))

    # Add Swin block layers
    ax.add_patch(patches.Rectangle((0.2, 0.6), 0.6, 0.3, facecolor='lightblue', label='Input Z^l'))
    ax.text(0.5, 0.73, "Input Zᶫ", ha='center', va='center', fontsize=10)

    ax.arrow(0.8, 0.75, 0.4, 0, head_width=0.05, head_length=0.05, fc='black', ec='black')

    # LayerNorm + QKV
    ax.add_patch(patches.Rectangle((1.2, 0.6), 0.6, 0.3, facecolor='orange'))
    ax.text(1.5, 0.73, "LayerNorm + QKV", ha='center', va='center', fontsize=9)

    ax.arrow(1.8, 0.75, 0.4, 0, head_width=0.05, head_length=0.05, fc='black', ec='black')

    # Window Attention
    ax.add_patch(patches.Rectangle((2.2, 0.6), 0.6, 0.3, facecolor='lightgreen'))
    ax.text(2.5, 0.73, "Window\nAttention", ha='center', va='center', fontsize=9)

    ax.arrow(2.8, 0.75, 0.4, 0, head_width=0.05, head_length=0.05, fc='black', ec='black')

    # MLP
    ax.add_patch(patches.Rectangle((3.2, 0.6), 0.6, 0.3, facecolor='plum'))
    ax.text(3.5, 0.73, "MLP", ha='center', va='center', fontsize=10)

    ax.arrow(3.8, 0.75, 0.4, 0, head_width=0.05, head_length=0.05, fc='black', ec='black')

    # Output
    ax.add_patch(patches.Rectangle((4.2, 0.6), 0.6, 0.3, facecolor='lightblue'))
    ax.text(4.5, 0.73, "Output Zᶫ⁺¹", ha='center', va='center', fontsize=10)

    ax.set_xlim(0, 5.2)
    ax.set_ylim(0, 1.2)
    ax.axis('off')
    plt.title("Single Swin Transformer Block (3D)")
    plt.tight_layout()
    plt.show()

draw_swin_block_diagram()
