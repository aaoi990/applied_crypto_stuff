import passlib.hash


def hash(salt, passwd):
	print(f"PBKDF2 (SHA1) Hash of {passwd} with salt {salt} : {passlib.hash.pbkdf2_sha1.encrypt(passwd, salt=salt)}")
	print(f"PBKDF2 (SHA256) Hash of {passwd} with salt {salt} : {passlib.hash.pbkdf2_sha256.encrypt(passwd, salt=salt)}")


salt = ("ZDzPE45C").encode()
word_list = ["changeme","123456","password"]

for password in word_list:
	hash(salt, password)
