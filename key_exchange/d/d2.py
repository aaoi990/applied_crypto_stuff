import os
import binascii
from x25519 import base_point_mult,multscalar

a = os.urandom(32)
b = os.urandom(32)


a_pub = base_point_mult(a)
b_pub = base_point_mult(b)

x = os.urandom(32)
y = os.urandom(32)

Bob_send = multscalar(y, a_pub) # (y) aG
Bob_send = multscalar(b, Bob_send) # (yb) aG


Alice_send = multscalar(x, b_pub) # (x) bG
Alice_send = multscalar(a, Alice_send) # (xa) bG


k_a = multscalar(x, Bob_send) # x (yb) aG
k_b = multscalar(y, Alice_send) # y ( xa) bG


print ("Bob private:\t",binascii.hexlify(a))
print ("Alice private:\t",binascii.hexlify(b))

print ("\n\nBob public:\t",binascii.hexlify(b_pub.encode()))
print ("Alice public:\t",binascii.hexlify(a_pub.encode()))

print ("\nBob x value:\t",binascii.hexlify(x))
print ("Alice y value:\t",binascii.hexlify(y))

print ("\n\nBob send:\t",binascii.hexlify(Bob_send.encode()))
print ("Alice send:\t",binascii.hexlify(Alice_send.encode()))

print ("\n\nBob shared:\t",binascii.hexlify(k_b.encode()))
print ("Alice shared:\t",binascii.hexlify(k_a.encode()))

# res=bytes_to_int(a)*bytes_to_int(y)*bytes_to_int(b)*bytes_to_int(x)

# k = base_point_mult(int_to_bytes(res,32))
# print ("\n\nChecking shared:\t",binascii.hexlify(k.encode()))
