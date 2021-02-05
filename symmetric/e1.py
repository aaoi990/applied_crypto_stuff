from Crypto.Cipher import AES, DES
import hashlib
import sys
import binascii
import Padding
import argparse
import base64

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", "--plaintext", help="the plaintext to be encrypted")
parser.add_argument("-k", "--key", nargs='+', help="the key used to encrypt the plaintext", required=True)
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


def decrypt_and_depad(key):
	print(f"Decrypting ciphertext: {args.ciphertext} \nWith key: {key}")
	ciphertext=ciphertextinput.encode()
	if(args.base64):
		ciphertext=base64.b64decode(ciphertext)
	else:
		ciphertext=binascii.unhexlify(ciphertext)
#	print(f"Ciphertext {ciphertext}")
	plaintext = decrypt(ciphertext,key,AES.MODE_ECB)
#	print(plaintext)

	try:
		plaintext = Padding.removePadding(plaintext.decode(),mode='CMS')
		print(f"Plaintext: {plaintext}")
	except:
		print(f"Error decrypting, probably wrong key supplied")


def encrypt_and_pad(key):
	print(f"Encrypting plaintext: {args.plaintext} \nWith key: {args.key}")
	plaintext = Padding.appendPadding(plaintext, blocksize=Padding.AES_blocksize,mode='CMS').encode()
	print(f"After padding (CMS): {binascii.hexlify(bytearray(plaintext))}")
	ciphertext = encrypt(plaintext, key,AES.MODE_ECB)
	print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")


def sort_keys():
	keys = []
	for i, k in enumerate(args.key):
		keys.append(hashlib.sha256(args.key[i].encode()).digest())
	return keys


key = sort_keys()
print(key)
if(plaintext):
	encrypt_and_pad(key)
else:
	for k in key:
		decrypt_and_depad(k)
