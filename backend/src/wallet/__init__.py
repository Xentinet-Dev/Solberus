"""
Wallet management modules.
"""

try:
    from wallet.wallet_manager import MultiWalletManager

    __all__ = ["MultiWalletManager"]
except ImportError:
    # Allow partial imports during development
    __all__ = []

