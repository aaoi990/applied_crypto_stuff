p=11
q=3
N=p*q
PHI=(p-1)*(q-1)
e=3
for d in range(1,N):
        if ((e*d % PHI)==1): break

print(f"encryption: {e},{N}")
print(f"decryption: {d},{N}")
M=4
cipher = M**e % N
print(f"ciphertext {cipher}")
message = cipher**d % N
print(f"messgage: {message}")
