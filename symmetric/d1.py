from Crypto.Cipher import AES
import hashlib
import sys
import binascii
import Padding
from Crypto.Util.Padding import pad, unpad

val='hello'
password='hello'

plaintext=val

def encrypt(plaintext,key, mode):
	encobj = AES.new(key,mode)
	return(encobj.encrypt(plaintext))

def decrypt(ciphertext,key, mode):
	encobj = AES.new(key,mode)
	return(encobj.decrypt(ciphertext))

key = hashlib.sha256(password.encode()).digest()

plaintext = Padding.appendPadding(plaintext, blocksize=Padding.AES_blocksize,mode='CMS').encode()
print(f"After padding (CMS): {binascii.hexlify(bytearray(plaintext))}")

ciphertext = encrypt(plaintext, key,AES.MODE_ECB)
print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
plaintext = Padding.removePadding(plaintext.decode(), mode='CMS')
print(f"decrypt: {plaintext}")

plaintext=val

plaintext = Padding.appendPadding(plaintext,blocksize=Padding.AES_blocksize,mode='ZeroLen').encode()
print(f"After padding (Bit): {binascii.hexlify(bytearray(plaintext))}")

ciphertext = encrypt(plaintext,key,AES.MODE_ECB)
print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
plaintext = Padding.removePadding(plaintext.decode(),blocksize=Padding.AES_blocksize,mode='ZeroLen')
print(f"decrypt: {plaintext}")

plaintext=val

plaintext = Padding.appendPadding(plaintext,blocksize=Padding.AES_blocksize,mode='Space').encode()
print(f"After padding (Null): {binascii.hexlify(bytearray(plaintext))}")

ciphertext = encrypt(plaintext,key,AES.MODE_ECB)
print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
plaintext = Padding.removePadding(plaintext.decode(),blocksize=Padding.AES_blocksize,mode='Space')
print(f"decrypt: {plaintext}")


plaintext=val

plaintext = Padding.appendPadding(plaintext,blocksize=Padding.AES_blocksize,mode='Random').encode()
print(f"After padding (Random): {binascii.hexlify(bytearray(plaintext))}")

ciphertext = encrypt(plaintext,key,AES.MODE_ECB)
print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
plaintext = Padding.removePadding(plaintext.decode(),mode='Random')
print(f"decrypt: {plaintext}")
