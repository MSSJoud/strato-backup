import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

def draw_slide(title, steps, filename):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    
    # Title
    ax.text(5, 4.6, title, fontsize=16, fontweight="bold", ha="center", va="center")
    
    # Draw boxes with arrows
    x_positions = [2, 5, 8]
    colors = ["#8ecae6", "#219ebc", "#023047"]
    text_colors = ["black", "white", "white"]
    
    for i, (pos, step, c, tc) in enumerate(zip(x_positions, steps, colors, text_colors)):
        box = FancyBboxPatch((pos-1.2, 2), 2.4, 1, boxstyle="round,pad=0.2", fc=c, ec="black")
        ax.add_patch(box)
        ax.text(pos, 2.5, step, ha="center", va="center", fontsize=12, color=tc, wrap=True)
        
        if i < len(x_positions)-1:
            ax.annotate("", xy=(x_positions[i+1]-1.2, 2.5), xytext=(pos+1.2, 2.5),
                        arrowprops=dict(arrowstyle="->", lw=2))
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()

# Slide 11: Physics-Based Inversion
steps_physics = ["Input:\nInSAR deformation u(x,y,t)",
                 "Process:\nGreen’s function inversion",
                 "Output:\nGroundwater storage Δp, Sg"]
draw_slide("Physics-Based Inversion:\nFrom Deformation to Groundwater", steps_physics, "slide11_physics.png")

# Slide 12: AI-Based Inversion
steps_ai = ["Input:\nInSAR + auxiliary data (S0)",
            "Training:\nSupervised with W3RA Sg, GRACE TWS",
            "Output:\nPredicted groundwater storage Ŝg"]
draw_slide("AI-Based Inversion:\nLearning Groundwater from InSAR", steps_ai, "slide12_ai.png")

