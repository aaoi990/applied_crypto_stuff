import passlib.hash


def hash(string):
	print(f"LM Hash of {string} : {passlib.hash.lmhash.encrypt(string)}")
	print(f"NT Hash of {string} : {passlib.hash.nthash.encrypt(string)}")

word_list = ["Napier","Foxtrot"]

for word in word_list:
	hash(word)
