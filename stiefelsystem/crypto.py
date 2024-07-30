"""
cryptographic helper functions
"""

import os
import hashlib

from Crypto.Cipher import AES

def encrypt(key, plaintext):
    """
    encrypt a given plaintext blob with a key.
    the returned blob is a nonce, the ciphertext and a mac.
    """
    nonce_gen = hashlib.sha256(plaintext)  # recommended by djb lol
    nonce_gen.update(os.urandom(16))
    nonce = nonce_gen.digest()[:16]
    cipher = AES.new(
        key,
        AES.MODE_EAX,
        nonce=nonce,
        mac_len=16
    )
    ciphertext, mac = cipher.encrypt_and_digest(plaintext)
    if len(mac) != 16:
        raise ValueError('bad MAC length')
    return nonce + ciphertext + mac


def decrypt(key, blob):
    """
    decrypt a given blob with a key.
    the blob has to include a nonce, mac and ciphertext.
    """
    nonce = blob[:16]
    ciphertext = blob[16:-16]
    mac = blob[-16:]
    cipher = AES.new(
        key,
        AES.MODE_EAX,
        nonce=nonce,
        mac_len=16
    )
    decrypted_blob = cipher.decrypt_and_verify(ciphertext, mac)
    del nonce, ciphertext, mac
    return decrypted_blob
