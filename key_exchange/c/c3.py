import random
import base64
import hashlib
import sys

g=5
p=467

a=random.randint(5, 10)

b=random.randint(10,20)

A = (g**a) % p
B = (g**b) % p

print(f"g = {g} (a shared value), n = {p} (a prime number)")
print(f"Alice calculates:")
print(f"a (Alice random): {a}")
print(f"Alice value (A): {A} = (g^a) mod p")

print(f"\nBob calculates:")
print(f"b (Bob random): {b}")
print(F"Bob value (B): {B} = (g^b) mod p")

print("\nAlice calculates:")
keyA=(B**a) % p
print(f"Key: {keyA} = (B^a) mod p")
print(f"Key: {hashlib.sha256(str(keyA).encode()).hexdigest()}")

print(f"\nBob calculates:")
keyB=(A**b) % p
print(f"Key: {keyB} = (A^b) mod p")
print(f"Key: {hashlib.sha256(str(keyB).encode()).hexdigest()}")
