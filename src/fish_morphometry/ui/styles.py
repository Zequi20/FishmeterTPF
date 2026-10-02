"""Estilos ttk compartidos por la ventana principal."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def configure_styles(root: tk.Misc) -> None:
    """Configura tipografías, colores y espaciado para una pantalla de portátil."""

    style = ttk.Style(root)
    # ``clam`` ofrece un resultado consistente entre Linux y otros temas nativos.
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure("App.TFrame", background="#f4f7fb")
    style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
    style.configure("Header.TFrame", background="#17324d")
    style.configure(
        "Title.TLabel",
        background="#17324d",
        foreground="#ffffff",
        font=("TkDefaultFont", 21, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background="#17324d",
        foreground="#dce8f2",
        font=("TkDefaultFont", 10),
    )
    style.configure(
        "Section.TLabel",
        background="#f4f7fb",
        foreground="#17324d",
        font=("TkDefaultFont", 13, "bold"),
    )
    style.configure(
        "CardTitle.TLabel",
        background="#ffffff",
        foreground="#17324d",
        font=("TkDefaultFont", 12, "bold"),
    )
    style.configure(
        "CardBody.TLabel",
        background="#ffffff",
        foreground="#334e68",
        font=("TkDefaultFont", 9),
    )
    style.configure(
        "Input.TLabel",
        background="#ffffff",
        foreground="#334e68",
        font=("TkDefaultFont", 9),
    )
    style.configure(
        "Muted.TLabel",
        background="#f4f7fb",
        foreground="#627d98",
        font=("TkDefaultFont", 9),
    )
    style.configure(
        "CardMuted.TLabel",
        background="#ffffff",
        foreground="#627d98",
        font=("TkDefaultFont", 9),
    )
    style.configure(
        "Status.TLabel",
        background="#fff5dc",
        foreground="#835b00",
        font=("TkDefaultFont", 9, "bold"),
    )
    style.configure(
        "Footer.TLabel",
        background="#e7eef5",
        foreground="#486581",
        font=("TkDefaultFont", 9),
    )
    style.configure(
        "Action.TButton",
        font=("TkDefaultFont", 9, "bold"),
        padding=(10, 6),
    )
    style.map(
        "Action.TButton",
        foreground=[("disabled", "#7b8794")],
        background=[("disabled", "#edf1f5")],
    )
    style.configure("Treeview.Heading", font=("TkDefaultFont", 9, "bold"))
