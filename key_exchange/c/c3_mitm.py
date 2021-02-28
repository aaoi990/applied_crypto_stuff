import random
import base64
import hashlib
import sys

g=15
N=1011
a= 5
b = 9
eve = 7
message=21

alice_and_eve=(g**a) % N
eve_and_alice = (g**eve) % N
alice_and_eve_key = (eve_and_alice**a) % N
eve_and_alice_key = (alice_and_eve**eve) % N
print ('g: ',g,' (a shared value), n: ',N, ' (a prime number)')
print ('Alice value (A): ',alice_and_eve,' (g**a) mod p')

print ('\n==Alice sends value to Eve ===')
print ('Alice gets Eve\'s value and calculates key of: ',alice_and_eve_key)
print(f"Eve has the same key of {eve_and_alice_key}")

bob_and_eve=(g**b) % N
eve_and_bob = (g**eve) % N
bob_and_eve_key = (eve_and_bob**b) % N
eve_and_bob_key = (bob_and_eve**eve) % N

print ('\nBob value (B): ',bob_and_eve,' (g^b) mod p')
print ('\n==Bob sends value to Eve ===')
print ('Eve takes Bob\'s value and calculates: ',eve_and_bob)
print ('Bob gets Eve\'s value and calculates key of: ',eve_and_bob_key)
print(f"Eve has the same key of {eve_and_bob_key}")
