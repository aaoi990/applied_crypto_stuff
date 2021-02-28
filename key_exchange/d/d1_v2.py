from tinyec import registry
import secrets

def compress(pubKey):
    return hex(pubKey.x) + hex(pubKey.y % 2)[2:]


# chose from predefined list
curve = registry.get_curve('secp256r1')

alicePrivKey = secrets.randbelow(curve.field.n) # this is n in P = nG
alicePubKey = alicePrivKey * curve.g # This is P = n * G
print("Alice public key:", compress(alicePubKey)) # compressed - prefix 02
print("Uncompressed", alicePubKey) # uncompressed - prefox 04

bobPrivKey = secrets.randbelow(curve.field.n)
bobPubKey = bobPrivKey * curve.g
print("Bob public key:", compress(bobPubKey))


aliceSharedKey = alicePrivKey * bobPubKey
print("Alice shared key:", compress(aliceSharedKey))

bobSharedKey = bobPrivKey * alicePubKey
print("Bob shared key:", compress(bobSharedKey))

print("Equal shared keys:", aliceSharedKey == bobSharedKey)


# Note tiny ec does not support curve 25519, since it's a montgomery curve
# By^2 = x^3 + Ax^2 + x not a weierstrass curve y^2 = x^3 + ax + b
# but as an example, this will 'work'
