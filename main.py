import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from gui import ThreadsBotGUI

def main():
    """Точка входу в програму."""
    root = ctk.CTk()
    app = ThreadsBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()