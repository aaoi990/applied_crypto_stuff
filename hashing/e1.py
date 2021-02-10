import passlib.hash


def hash(salt, passwd):
	print(f"APR1 Hash of {passwd} with salt {salt} : {passlib.hash.apr_md5_crypt.encrypt(passwd, salt=salt)}")


salt = "PkWj6gM4"
word_list = ["changeme","123456","password"]

for password in word_list:
	hash(salt, password)
