from Crypto.Cipher import AES, DES
import hashlib
import sys
import binascii
import Padding
import argparse
import base64

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", "--plaintext", help="the plaintext to be encrypted")
parser.add_argument("-k", "--key", help="the key used to encrypt the plaintext", required=True)
parser.add_argument("-c", "--ciphertext", help="the cipher text to be decoded")
parser.add_argument("-b64", "--base64", help="decodes a base 64 string because decrypting",action="store_true")
args = parser.parse_args()

val=args.plaintext
key=args.key
plaintext=args.plaintext
ciphertextinput=args.ciphertext

def encrypt(plaintext,key, mode):
	encobj = AES.new(key,mode)
	return(encobj.encrypt(plaintext))

def decrypt(ciphertext,key, mode):
	encobj = AES.new(key,mode)
	return(encobj.decrypt(ciphertext))

key = hashlib.sha256(args.key.encode()).digest()

if(plaintext):
	print(f"Encrypting plaintext: {args.plaintext} \nWith key: {args.key}")
	plaintext = Padding.appendPadding(plaintext, blocksize=Padding.AES_blocksize,mode='CMS').encode()
	print(f"After padding (CMS): {binascii.hexlify(bytearray(plaintext))}")
	ciphertext = encrypt(plaintext, key,AES.MODE_ECB)
	print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")
else:
	print(f"Decrypting ciphertext: {args.ciphertext} \nWith key: {args.key}")
	ciphertext=ciphertextinput.encode()
	if(args.base64):
		ciphertext=base64.b64decode(ciphertext)
	else:
		ciphertext=binascii.unhexlify(ciphertext)
	print(f"Ciphertext {ciphertext}")
	plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
	print(plaintext)
	plaintext = Padding.removePadding(plaintext.decode(),mode='CMS')
	print(f"Plaintext: {plaintext}")
