import tkinter as tk
from tkinter import ttk


def main() -> None:
    root = tk.Tk()
    root.title("PortablePipeTools")
    root.geometry("300x140")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    label = ttk.Label(frame, text="Hello World")
    label.pack(pady=(0, 16))

    ok_button = ttk.Button(frame, text="OK", command=root.destroy)
    ok_button.pack()

    root.mainloop()


if __name__ == "__main__":
    main()
