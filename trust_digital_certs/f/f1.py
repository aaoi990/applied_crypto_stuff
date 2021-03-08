import OpenSSL 
import os
import argparse
from cryptography import x509
from cryptography.hazmat.backends import default_backend

certs = os.listdir("pfx/")
certs.sort()

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-f", "--file", help="use a file as the key input")
args = parser.parse_args()

with open(args.file) as f:
	content = f.readlines()
	key = [x.strip().lower() for x in content]
	temp = key
	passwords = key



def check_password(str):
	for password in passwords:
		try:
			pfx = open(str, 'rb').read()
			p12 = OpenSSL.crypto.load_pkcs12(pfx, password.encode())
			print(f"Found: {password} {str}")
			break
			#privkey=OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, p12.get_privatekey())
			#cert=OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, p12.get_certificate())
			#cert = x509.load_pem_x509_certificate(cert, default_backend())
			#print (" Issuer: ",cert.issuer)
			#print (" Subect: ",cert.subject)
			#print (" Serial number: ",cert.serial_number)
			#print (" Hash: ",cert.signature_hash_algorithm.name)
			#print (privkey)

		except:
			pass


for i in certs:
	check_password("pfx/" + i)
