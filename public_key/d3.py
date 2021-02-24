from ecdsa import SigningKey,NIST192p,NIST224p,NIST256p,NIST384p,NIST521p,SECP256k1
import base64
import sys

msg=b"Hello"
type = 1
curves=[SECP256k1, NIST192p, NIST521p, SECP256k1]

for c in curves:
	sk = SigningKey.generate(curve=c)
	vk = sk.get_verifying_key()
	signature = sk.sign(msg)

	print("Message:\t",msg)
	print("Type:\t\t",c.name)
	print("Signature:\t",base64.b64encode(signature))
	print("Signatures match:\t",vk.verify(signature, msg))
