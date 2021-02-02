from Crypto.Cipher import AES, DES
import hashlib
import sys
import binascii
import Padding
import argparse


parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", "--plaintext", help="the plaintext to be encrypted", required=True)
parser.add_argument("-k", "--key", help="the key used to encrypt the plaintext", required=True)
args = parser.parse_args()

val=args.plaintext
password=args.key
plaintext=args.plaintext

def encrypt(plaintext,key, mode):
	encobj = DES.new(key,mode)
	return(encobj.encrypt(plaintext))

def decrypt(ciphertext,key, mode):
	encobj = DES.new(key,mode)
	return(encobj.decrypt(ciphertext))

key = hashlib.sha256(password.encode()).digest()[:8]

plaintext = Padding.appendPadding(plaintext, blocksize=Padding.DES_blocksize,mode='CMS').encode()
ciphertext = encrypt(plaintext, key, DES.MODE_ECB)
print(f"Plaintext: {val} \nKey: {password} \nCipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

