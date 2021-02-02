from Crypto.Cipher import AES, DES
import hashlib
import sys
import binascii
import Padding
import argparse


parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", "--plaintext", help="the plaintext to be encrypted", required=True)
parser.add_argument("-k", "--key", help="the key used to encrypt the plaintext", required=True)
parser.add_argument("-c", "--cipher", help="Cipher to be used, either AES or DES", required=True)
args = parser.parse_args()

if(args.cipher not in ["AES","DES"]):
	print('Not a compatible cipher')
	sys.exit()

val=args.plaintext
password=args.key
plaintext=args.plaintext
cipher=args.cipher

def des_encrypt(plaintext,key, mode):
	encobj = DES.new(key,mode)
	return(encobj.encrypt(plaintext))

def des_decrypt(ciphertext,key, mode):
	encobj = DES.new(key,mode)
	return(encobj.decrypt(ciphertext))

def aes_encrypt(plaintext,key, mode):
        encobj = AES.new(key,mode)
        return(encobj.encrypt(plaintext))

def aes_decrypt(ciphertext,key, mode):
        encobj = AES.new(key,mode)
        return(encobj.decrypt(ciphertext))

if(cipher == "DES"):
	key = hashlib.sha256(password.encode()).digest()[:8]
	plaintext = Padding.appendPadding(plaintext, blocksize=Padding.DES_blocksize,mode='CMS').encode()
	ciphertext = des_encrypt(plaintext, key, DES.MODE_ECB)
	print(f"Plaintext: {val} \nKey: {password} \nCipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")
else:
	key = hashlib.sha256(password.encode()).digest()
	plaintext = Padding.appendPadding(plaintext, blocksize=Padding.AES_blocksize,mode='CMS').encode()
	ciphertext = aes_encrypt(plaintext, key, AES.MODE_ECB)
	print(f"Plaintext: {val} \nKey: {password} \nCipher (ECB): {binascii.hexlify(bytearray(ciphertext))}")

