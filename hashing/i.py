import hmac
import base64

password = ("qwerty123").encode()
message = ("Hello").encode()

hmacmd5 = hmac.new(password, message, 'MD5')
print(f"HMAC: {hmacmd5.hexdigest()}")
print(f"HMAC base64: {base64.b64encode(hmacmd5.digest()).decode()}\n")

hmac256 = hmac.new(password, message, 'SHA256')
print(f"HMAC sha256: {hmac256.hexdigest()}")
print(f"HMAC base64: {base64.b64encode(hmac256.digest()).decode()}")
