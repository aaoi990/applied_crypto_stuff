import argparse
import base64
import libnum

parser = argparse.ArgumentParser(description='Do some crypt magic...')
parser.add_argument("-p", help="value of p")
parser.add_argument("-q", help="value of q")
parser.add_argument("-e", help="value of e")
args = parser.parse_args()

p=int(args.p)
e=int(args.e)
q=int(args.q)

N=p*q
PHI=(p-1)*(q-1)
d=libnum.invmod(e, PHI)
print(list(filter(lambda x: (x*e)%PHI == 1, range(1, PHI))))
print(f"(e,N) : ({e},{N})")
print(f"(d,N) : ({d},{N})")

#confirm
M = 7
print(f"message: {M}")
cipher=M**e%N
print(f"cipher: {cipher}")
message=cipher**d%N
print(f"decrypted message: {message}")
