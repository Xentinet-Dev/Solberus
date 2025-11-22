"""
Signature verification for wallet authentication.
"""
import logging
import base58
from typing import List

try:
    from verify_crypto_signature.sol import VerifySOL
    VERIFY_SOL_AVAILABLE = True
except ImportError:
    VERIFY_SOL_AVAILABLE = False
    VerifySOL = None

try:
    from nacl.signing import VerifyKey
    from nacl.encoding import RawEncoder
    from solders.pubkey import Pubkey
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    VerifyKey = None
    Pubkey = None

logger = logging.getLogger(__name__)


class SignatureVerifier:
    """Verifies Solana wallet signatures for authentication."""
    
    def __init__(self):
        """Initialize signature verifier."""
        if VERIFY_SOL_AVAILABLE:
            logger.info("Using verify-crypto-signature for Solana signature verification")
        elif NACL_AVAILABLE:
            logger.warning("Using nacl for signature verification (verify-crypto-signature recommended)")
        else:
            logger.error("No signature verification library available! Install: pip install verify-crypto-signature pynacl")
    
    def verify_signature(
        self,
        wallet_address: str,
        message: List[int],
        signature: List[int],
    ) -> tuple[bool, str]:
        """Verify a signature from a wallet.
        
        Args:
            wallet_address: Base58 encoded public key
            message: Original message as list of bytes
            signature: Signature as list of bytes
            
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if not VERIFY_SOL_AVAILABLE and not NACL_AVAILABLE:
            return False, "Signature verification not available. Install: pip install verify-crypto-signature pynacl"
        
        try:
            # Convert lists to bytes
            message_bytes = bytes(message)
            signature_bytes = bytes(signature)
            
            logger.info(f"Verifying signature for wallet: {wallet_address}")
            logger.info(f"Message length: {len(message_bytes)}, Signature length: {len(signature_bytes)}")
            
            # Method 1: Try verify-crypto-signature (Solana-specific, recommended)
            if VERIFY_SOL_AVAILABLE:
                try:
                    # Convert signature to base58 (Solana standard)
                    signature_base58 = base58.b58encode(signature_bytes).decode('utf-8')
                    
                    # VerifySOL expects: wallet_address (str), message (bytes), signature (base58 str)
                    is_valid = VerifySOL.verify_signature(
                        wallet_address,
                        message_bytes,
                        signature_base58
                    )
                    
                    if is_valid:
                        logger.info("✅ Signature verified using verify-crypto-signature")
                        return True, "Signature verified"
                    else:
                        logger.warning("Signature verification failed with verify-crypto-signature, trying nacl fallback")
                except Exception as e:
                    logger.warning(f"verify-crypto-signature failed: {e}, trying nacl fallback")
                    import traceback
                    traceback.print_exc()
            
            # Method 2: Fallback to nacl (manual verification)
            if NACL_AVAILABLE:
                pubkey = Pubkey.from_string(wallet_address)
                pubkey_bytes = bytes(pubkey)
                verify_key = VerifyKey(pubkey_bytes, encoder=RawEncoder())
                
                if len(signature_bytes) != 64:
                    return False, f"Invalid signature length: {len(signature_bytes)} (expected 64)"
                
                # Solana standard message format
                solana_prefix = b"\xffSolana Signed Message:\n"
                message_len = len(message_bytes).to_bytes(4, byteorder='little')
                prefixed_message = solana_prefix + message_len + message_bytes
                
                # nacl's verify expects (message + signature) concatenated
                signed_message = prefixed_message + signature_bytes
                
                try:
                    verify_key.verify(signed_message)
                    logger.info("✅ Signature verified using nacl")
                    return True, "Signature verified"
                except Exception as e:
                    error_msg = f"Signature verification failed: {str(e)}"
                    logger.error(error_msg)
                    logger.error(f"Message (first 50 bytes): {message_bytes[:50]}")
                    logger.error(f"Signature (first 20 bytes): {signature_bytes[:20]}")
                    import traceback
                    traceback.print_exc()
                    return False, error_msg
            else:
                return False, "No signature verification method available"
                
        except Exception as e:
            error_msg = f"Verification error: {str(e)}"
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return False, error_msg
