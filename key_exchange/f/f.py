import random
import base64
import hashlib
import sys
import argparse

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-g", help="value of g")
parser.add_argument("-p", help="value of p")
parser.add_argument("-A", help="value of A")
parser.add_argument("-B", help="value of B")
args = parser.parse_args()

p=int(args.p)
g=int(args.g)

B = int(args.B)
A = int(args.A)

def find_secret(passed_value):
	for x in range(0, p):
		if((g**x) % p == passed_value):
			print("secret: ", x, (g**x)%p)
			return x
a = find_secret(A)
b = find_secret(B)

print("Testing")
print(f"g = {g} (a shared value), n = {p} (a prime number)")
print(f"Alice calculates:")
print(f"a (Alices discovered secret): {a}")
print(f"Alice value (A): {A} = (g^a) mod p")

print(f"\nBob calculates:")
print(f"b (Bobs discovered secret): {b}")
print(F"Bob value (B): {B} = (g^b) mod p")

print("\nAlice calculates:")
keyA=(B**a) % p
print(f"Key: {keyA} = (B^a) mod p")

print(f"\nBob calculates:")
keyB=(A**b) % p
print(f"Key: {keyB} = (A^b) mod p")
#print(f"Key: {hashlib.sha256(str(keyB).encode()).hexdigest()}")

#Aa = (g**a) % p
#Bb = (g**b) % p
#keyA=(B**a) % p
#keyB=(A**b) % p

print(keyA, keyB)
