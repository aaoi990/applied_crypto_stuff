from Crypto.Cipher import AES, DES
import hashlib
import sys
import binascii
import Padding
import argparse
import base64
from termcolor import colored

# usage python3 e1.py -c 5I71KpfT6RdM/xhUJ5IKCQ==  -k 123456 -b64
# can accept plaintext and key for encrypt, or cipher text and key for decrypt
# can accept a file for multiple key attempts with -f, or multiple keys
# specified on cmd line -k password1 password2
# who needs error handling?

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", "--plaintext", help="the plaintext to be encrypted")
parser.add_argument("-k", "--key", nargs='+', help="the key used to encrypt the plaintext")
parser.add_argument("-c", "--ciphertext", help="the cipher text to be decoded")
parser.add_argument("-b64", "--base64", help="decodes a base 64 string because decrypting",action="store_true")
parser.add_argument("-f", "--file", help="use a file as the key input")
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
	"""Checks argparse for base64 before attempting the decrypt and depad"""
	ciphertext=ciphertextinput.encode()
	if(args.base64):
		ciphertext=base64.b64decode(ciphertext)
	else:
		ciphertext=binascii.unhexlify(ciphertext)
	plaintext = decrypt(ciphertext,key,AES.MODE_ECB)

	try:
		plaintext = Padding.removePadding(plaintext.decode(),mode='CMS')
		print(f"Decrypting ciphertext: {args.ciphertext} \nWith key: {key}")
		print(colored(f"Plaintext: {plaintext}", "green"))

	except:
		pass


def encrypt_and_pad(key):
	print(f"Encrypting plaintext: {args.plaintext} \nWith key: {args.key}")
	plaintext = Padding.appendPadding(plaintext, blocksize=Padding.AES_blocksize,mode='CMS').encode()
	print(f"After padding (CMS): {binascii.hexlify(bytearray(plaintext))}")
	ciphertext = encrypt(plaintext, key,AES.MODE_ECB)
	print(f"Cipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")


def sort_keys():
	"""If the arg.parse is a file, sort the file into a list with no \n
	Loop through list of keys and format.

	returns list of hashed keys"""
	if(args.file):
		with open(args.file) as f:
			content = f.readlines()
			key = [x.strip() for x in content]

	else:
		key = args.key

	keys = []
	for i, k in enumerate(key):
		keys.append(hashlib.sha256(key[i].encode()).digest())
	return keys


key = sort_keys()

if(plaintext):
	encrypt_and_pad(key)
else:
	for k in key:
		decrypt_and_depad(k)
