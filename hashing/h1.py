import hashlib;
import passlib.hash;
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

salt="ZDzPE45C"
string="hello"
salt2="1111111111111111111111"

md5 = hashlib.md5(string.encode()).hexdigest()
print(f"MD5: {md5} {len(md5)}")

sha1 = hashlib.sha1(string.encode()).hexdigest()
print(f"SHA1: {sha1} {len(sha1)}")

sha256 = hashlib.sha256(string.encode()).hexdigest()
print(f"SHA256: {sha256} {len(sha256)}")

sha512 = hashlib.sha512(string.encode()).hexdigest()
print(f"SHA512: {sha512} {len(sha512)}")

des = passlib.hash.des_crypt.encrypt(string, salt=salt[:2])
print(f"DES: {des} {len(des)}")

md5s = passlib.hash.md5_crypt.encrypt(string, salt=salt)
print(f"MD5: {md5s} {len(md5s)}")

sunmd5 = passlib.hash.sun_md5_crypt.encrypt(string, salt=salt)
print(f"Sun MD5: {sunmd5} {len(sunmd5)}")

sha1s = passlib.hash.sha1_crypt.encrypt(string, salt=salt)
print(f"SHA1: {sha1s} {len(sha1s)}")

sha256s = passlib.hash.sha256_crypt.encrypt(string, salt=salt)
print(f"SHA256: {sha256s} {len(sha256s)}")

sha512s = passlib.hash.sha512_crypt.encrypt(string, salt=salt)
print(f"SHA512: {sha512s} {len(sha512s)}")

bcrypt = passlib.hash.bcrypt.encrypt(string, salt=salt2[:22])
print(f"Bcrypt: {bcrypt} {len(bcrypt)}")
