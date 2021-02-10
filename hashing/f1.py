import passlib.hash


def hash(salt, passwd):
	print(f"SHA1 Hash of {passwd} with salt {salt} : {passlib.hash.sha1_crypt.encrypt(passwd, salt=salt)}")
	print(f"SHA256 Hash of {passwd} with salt {salt} : {passlib.hash.sha256_crypt.encrypt(passwd, salt=salt)}")
	print(f"SHA512 Hash of {passwd} with salt {salt} : {passlib.hash.sha512_crypt.encrypt(passwd, salt=salt)}\n")


salt = "8sFt66rZ"
word_list = ["changeme","123456","password"]

for password in word_list:
	hash(salt, password)
