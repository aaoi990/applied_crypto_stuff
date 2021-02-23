import argparse
import base64
import libnum
from Crypto.Util.number import long_to_bytes

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", help="value of p")
parser.add_argument("-q", help="value of q")
parser.add_argument("-e", help="value of e")
args = parser.parse_args()

p=int(args.p)
#e=int(args.e)
q=int(args.q)

N=p*q
PHI=(p-1)*(q-1)
e=65537
d=(libnum.invmod(e, PHI))
#d=pow(e, -1, PHI)
c=67340510464226661815115118309943778

res=pow(c,d,N)


print(f"(e,N) : ({e},{N})")
print(f"(d,N) : ({d},{N})")

#confirm
print("\n-------  Confirm  --------------")
print(long_to_bytes(res))

#M = 7
#print(f"message: {M}")
#cipher=M**e%N
#print(f"cipher: {cipher}")
#message=cipher**d%N
#print(f"decrypted message: {message}")
