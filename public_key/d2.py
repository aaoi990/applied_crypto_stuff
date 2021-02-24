import math
import sys

p=89
startval=1
a=0
b=7

def findpoints(p,a,b):
  found=0
  for x in range(1,2*p):
    val=((x*x*x) + a*x+ b) % p
    res = math.sqrt(val)

    if (found>19 or x>p): return

    if (abs(res-int(res))<0.0001):
      print("(",x,int(res),")",end=''),
      found=found+1

print ("A: ",a)
print ("B: ",b)
print ("Prime number:\t\t",p)
if (a==0):
  print ("Elliptic curve is:\t\ty^2=x^3+",b)
else:
  print ("Elliptic curve is:\t\ty^2=x^3+",a,"x+",b)
print ("Finding the first 20 points")

print
findpoints(p,a,b)

