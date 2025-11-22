"""
Login screen for wallet connection and token verification.
"""

import asyncio
import logging
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from typing import Callable, Optional

from auth.wallet_connector import WalletConnector
from core.client import SolanaClient
from core.wallet import Wallet

logger = logging.getLogger(__name__)


class LoginScreen:
    """Login screen for wallet connection with token gating."""

    def __init__(
        self,
        root: tk.Tk,
        client: SolanaClient,
        access_token_mint: Optional[str] = None,
        min_token_balance: int = 1,
        on_success: Optional[Callable[[Wallet], None]] = None,
    ):
        """Initialize login screen.

        Args:
            root: Tkinter root window
            client: Solana client for RPC calls
            access_token_mint: Optional token mint address for access control
            min_token_balance: Minimum token balance required
            on_success: Callback when login succeeds (receives Wallet)
        """
        self.root = root
        self.client = client
        self.on_success = on_success
        self.connected_wallet: Optional[Wallet] = None

        # Initialize wallet connector
        self.connector = WalletConnector(
            client=client,
            access_token_mint=access_token_mint,
            min_token_balance=min_token_balance,
        )

        # Xentinet Labs Color Scheme
        self.colors = {
            "bg_primary": "#0a0a0f",
            "bg_secondary": "#12121a",
            "bg_tertiary": "#1a1a24",
            "accent_primary": "#00d4ff",
            "accent_success": "#00ff88",
            "accent_danger": "#ff3366",
            "accent_warning": "#ffb800",
            "text_primary": "#ffffff",
            "text_secondary": "#b0b0b0",
            "text_muted": "#6b6b7a",
            "border": "#2a2a3a",
        }

        self.setup_ui()

    def setup_ui(self):
        """Set up the login UI."""
        # Configure root window
        self.root.title("XENTINET LABS | Wallet Connection")
        self.root.geometry("600x700")
        self.root.configure(bg=self.colors["bg_primary"])

        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Main container
        main_frame = tk.Frame(self.root, bg=self.colors["bg_primary"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        # Header
        header_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        header_frame.pack(fill=tk.X, pady=(0, 30))

        title = tk.Label(
            header_frame,
            text="XENTINET",
            font=("Segoe UI", 32, "bold"),
            bg=self.colors["bg_primary"],
            fg=self.colors["accent_primary"],
        )
        title.pack()

        subtitle = tk.Label(
            header_frame,
            text="Trading Bot Control Center",
            font=("Segoe UI", 12),
            bg=self.colors["bg_primary"],
            fg=self.colors["text_secondary"],
        )
        subtitle.pack(pady=(5, 0))

        # Login card
        login_card = tk.Frame(
            main_frame,
            bg=self.colors["bg_tertiary"],
            relief=tk.FLAT,
            bd=1,
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        login_card.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Card header
        card_header = tk.Frame(login_card, bg=self.colors["bg_tertiary"])
        card_header.pack(fill=tk.X, padx=30, pady=(30, 20))

        card_title = tk.Label(
            card_header,
            text="Connect Wallet",
            font=("Segoe UI", 18, "bold"),
            bg=self.colors["bg_tertiary"],
            fg=self.colors["text_primary"],
        )
        card_title.pack(anchor=tk.W)

        if self.connector.is_token_gated():
            token_info = tk.Label(
                card_header,
                text="Token-gated access enabled",
                font=("Segoe UI", 10),
                bg=self.colors["bg_tertiary"],
                fg=self.colors["accent_warning"],
            )
            token_info.pack(anchor=tk.W, pady=(5, 0))

        # Private key input
        input_frame = tk.Frame(login_card, bg=self.colors["bg_tertiary"])
        input_frame.pack(fill=tk.X, padx=30, pady=20)

        key_label = tk.Label(
            input_frame,
            text="Private Key (Base58)",
            font=("Segoe UI", 11),
            bg=self.colors["bg_tertiary"],
            fg=self.colors["text_secondary"],
        )
        key_label.pack(anchor=tk.W, pady=(0, 8))

        self.private_key_entry = tk.Entry(
            input_frame,
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
            font=("Consolas", 10),
            insertbackground=self.colors["accent_primary"],
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent_primary"],
            show="*",  # Hide private key
        )
        self.private_key_entry.pack(fill=tk.X, pady=(0, 5))
        self.private_key_entry.bind("<Return>", lambda e: self.connect_wallet())

        # Show/Hide toggle
        self.show_key = tk.BooleanVar(value=False)
        show_toggle = tk.Checkbutton(
            input_frame,
            text="Show private key",
            variable=self.show_key,
            command=self.toggle_key_visibility,
            bg=self.colors["bg_tertiary"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 9),
            selectcolor=self.colors["bg_secondary"],
            activebackground=self.colors["bg_tertiary"],
            activeforeground=self.colors["text_secondary"],
        )
        show_toggle.pack(anchor=tk.W)

        # Status/Message area
        self.status_text = scrolledtext.ScrolledText(
            login_card,
            height=6,
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_secondary"],
            font=("Consolas", 9),
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))

        # Connect button
        button_frame = tk.Frame(login_card, bg=self.colors["bg_tertiary"])
        button_frame.pack(fill=tk.X, padx=30, pady=(0, 30))

        self.connect_btn = tk.Button(
            button_frame,
            text="CONNECT WALLET",
            command=self.connect_wallet,
            bg=self.colors["accent_primary"],
            fg="#000000",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#00b8e6",
            activeforeground="#000000",
            bd=0,
            padx=20,
            pady=12,
        )
        self.connect_btn.pack(fill=tk.X)

        # Footer info
        footer = tk.Label(
            main_frame,
            text="Your private key is never stored or transmitted.\nAll operations happen locally.",
            font=("Segoe UI", 9),
            bg=self.colors["bg_primary"],
            fg=self.colors["text_muted"],
            justify=tk.CENTER,
        )
        footer.pack(pady=(10, 0))

    def toggle_key_visibility(self):
        """Toggle private key visibility."""
        if self.show_key.get():
            self.private_key_entry.config(show="")
        else:
            self.private_key_entry.config(show="*")

    def log_status(self, message: str, level: str = "INFO"):
        """Log status message."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"[{level}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def connect_wallet(self):
        """Connect wallet and verify access."""
        private_key = self.private_key_entry.get().strip()

        if not private_key:
            messagebox.showerror("Error", "Please enter your private key")
            return

        # Disable button during connection
        self.connect_btn.config(state=tk.DISABLED, text="CONNECTING...")
        self.log_status("Connecting wallet...", "INFO")

        # Run async connection in thread
        def run_connection():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, wallet, message = loop.run_until_complete(
                    self.connector.connect_wallet(private_key)
                )
                loop.close()

                # Update UI in main thread
                self.root.after(0, self._handle_connection_result, success, wallet, message)

            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.root.after(
                    0,
                    self._handle_connection_result,
                    False,
                    None,
                    f"Connection failed: {str(e)}",
                )

        thread = threading.Thread(target=run_connection, daemon=True)
        thread.start()

    def _handle_connection_result(
        self, success: bool, wallet: Optional[Wallet], message: str
    ):
        """Handle connection result in main thread."""
        self.connect_btn.config(state=tk.NORMAL, text="CONNECT WALLET")

        if success and wallet:
            self.log_status(message, "SUCCESS")
            self.connected_wallet = wallet

            # Call success callback
            if self.on_success:
                self.on_success(wallet)

            # Close login screen after short delay
            self.root.after(1000, self.close_login)
        else:
            self.log_status(message, "ERROR")
            messagebox.showerror("Access Denied", message)

    def close_login(self):
        """Close login screen."""
        self.root.destroy()

    def get_wallet(self) -> Optional[Wallet]:
        """Get connected wallet."""
        return self.connected_wallet

